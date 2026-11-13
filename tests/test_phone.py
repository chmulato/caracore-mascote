"""Testes do lado que fala com o celular: TCP, descoberta na rede, IP local e QR."""

from __future__ import annotations

import json
import socket
import struct
import sys
import threading
import time
import unittest
from unittest import mock

from gaspar.sms import discovery, network, qr
from gaspar.sms.client import PhoneClient, PhoneOffline
from gaspar.sms.crypto import decrypt, encrypt
from gaspar.sms.protocol import DISCOVERY_PORT, MAX_FRAME, frame


def read_exact(sock: socket.socket, size: int) -> bytes:
    dados = bytearray()
    while len(dados) < size:
        parte = sock.recv(size - len(dados))
        if not parte:
            break
        dados.extend(parte)
    return bytes(dados)


class CelularFalso:
    """Celular minimo: le o comando cifrado e responde o que o teste pedir."""

    def __init__(self, chave: bytes, ack=None, ack_bruto: bytes | None = None, silencioso=False):
        self.chave = chave
        self.ack = ack
        self.ack_bruto = ack_bruto
        self.silencioso = silencioso
        self.comandos: list[dict] = []
        self.erro: Exception | None = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_args):
        self._sock.close()
        self._thread.join(timeout=2)

    def _serve(self):
        try:
            conexao, _ = self._sock.accept()
            conexao.settimeout(3)
            with conexao:
                cabecalho = read_exact(conexao, 4)
                if len(cabecalho) == 4:
                    tamanho = struct.unpack(">I", cabecalho)[0]
                    corpo = read_exact(conexao, tamanho)
                    self.comandos.append(json.loads(decrypt(self.chave, corpo).decode("utf-8")))
                if self.silencioso:
                    time.sleep(0.5)
                elif self.ack is not None:
                    conexao.sendall(frame(encrypt(self.chave, json.dumps(self.ack).encode("utf-8"))))
                elif self.ack_bruto is not None:
                    conexao.sendall(self.ack_bruto)
        except Exception as exc:  # guardado para o teste falhar com contexto
            self.erro = exc


def porta_fechada() -> int:
    sonda = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sonda.bind(("127.0.0.1", 0))
    porta = sonda.getsockname()[1]
    sonda.close()
    return porta


class PhoneClientTests(unittest.TestCase):
    def test_sends_encrypted_command_and_reads_ack(self):
        chave = b"k" * 32
        with CelularFalso(chave, ack={"ok": True, "status": "accepted"}) as celular:
            resultado = PhoneClient("127.0.0.1", celular.port, chave, timeout=2, ack_timeout=1).send(
                envelope="envelope-1",
                msg_id="job-1",
                timestamp=123.0,
                base_url="http://192.168.0.10:8766",
                sequence=4,
                number="5511999999999",
                message="Venda 1",
            )
        self.assertIsNone(celular.erro)
        self.assertTrue(resultado.acknowledged)
        self.assertEqual(resultado.ack["status"], "accepted")
        comando = celular.comandos[0]
        self.assertEqual(comando["envelope"], "envelope-1")
        self.assertEqual(comando["id"], "job-1")
        self.assertEqual(comando["base"], "http://192.168.0.10:8766")
        self.assertEqual(comando["seq"], 4)
        self.assertNotIn("number", comando)
        self.assertNotIn("message", comando)

    def test_legacy_mode_carries_number_and_text(self):
        chave = b"k" * 32
        with CelularFalso(chave, ack={"ok": True}) as celular:
            PhoneClient("127.0.0.1", celular.port, chave, timeout=2, ack_timeout=1).send(
                number="5511999999999", message="Venda 1"
            )
        comando = celular.comandos[0]
        self.assertEqual(comando["number"], "5511999999999")
        self.assertEqual(comando["message"], "Venda 1")
        self.assertNotIn("envelope", comando)

    def test_silent_phone_is_still_a_successful_delivery_attempt(self):
        chave = b"k" * 32
        with CelularFalso(chave, silencioso=True) as celular:
            resultado = PhoneClient("127.0.0.1", celular.port, chave, timeout=2, ack_timeout=0.2).send(
                envelope="e", msg_id="j"
            )
        self.assertFalse(resultado.acknowledged)
        self.assertIsNone(resultado.ack)
        self.assertEqual(celular.comandos[0]["id"], "j")

    def test_offline_phone_raises(self):
        with self.assertRaises(PhoneOffline):
            PhoneClient("127.0.0.1", porta_fechada(), b"k" * 32, timeout=0.5).send(envelope="e")

    def test_malformed_ack_is_ignored(self):
        chave = b"k" * 32
        casos = {
            "curto": b"\x00\x00",
            "zero": struct.pack(">I", 0),
            "grande": struct.pack(">I", MAX_FRAME + 1),
            "lixo": frame(b"nao-cifrado"),
            "truncado": struct.pack(">I", 10) + b"abc",
        }
        for nome, bruto in casos.items():
            with self.subTest(nome):
                with CelularFalso(chave, ack_bruto=bruto) as celular:
                    resultado = PhoneClient(
                        "127.0.0.1", celular.port, chave, timeout=2, ack_timeout=0.5
                    ).send(envelope="e")
                self.assertFalse(resultado.acknowledged, nome)
                self.assertIsNone(resultado.ack, nome)


class FakeUdp:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.envios: list[tuple[bytes, tuple[str, int]]] = []

    def setsockopt(self, *_args):
        pass

    def bind(self, *_args):
        pass

    def settimeout(self, *_args):
        pass

    def sendto(self, dados, destino):
        self.envios.append((dados, destino))

    def recvfrom(self, _tamanho):
        if self.respostas:
            item = self.respostas.pop(0)
            if isinstance(item, Exception):
                raise item
            return item, ("192.168.0.7", DISCOVERY_PORT)
        raise socket.timeout()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class DiscoveryTests(unittest.TestCase):
    def test_finds_the_phone_and_asks_on_broadcast(self):
        fake = FakeUdp([b"CARACORE-APK|192.168.0.7|49998", socket.timeout()])
        with mock.patch.object(discovery.socket, "socket", return_value=fake):
            achados = discovery.discover(timeout=0.4)
        self.assertEqual(achados, [("192.168.0.7", 49998)])
        destinos = {destino[0] for _dados, destino in fake.envios}
        self.assertIn("255.255.255.255", destinos)
        self.assertTrue(all(destino[1] == DISCOVERY_PORT for _dados, destino in fake.envios))

    def test_bad_datagram_is_ignored_and_send_errors_do_not_stop(self):
        fake = FakeUdp([b"outro|1|2", OSError("sem rede")])
        with mock.patch.object(discovery.socket, "socket", return_value=fake):
            achados = discovery.discover(timeout=0.4)
        self.assertEqual(achados, [])

    def test_broadcast_addresses_always_include_the_global_one(self):
        with mock.patch.dict(sys.modules, {"psutil": None}):
            self.assertIn("255.255.255.255", discovery._broadcast_addresses())


class FakeSock:
    def __init__(self, endereco="192.168.1.5", erro=None):
        self.endereco = endereco
        self.erro = erro

    def connect(self, _alvo):
        if self.erro:
            raise self.erro

    def getsockname(self):
        return (self.endereco, 1234)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class NetworkTests(unittest.TestCase):
    def test_uses_the_route_address(self):
        with mock.patch.object(network.socket, "socket", return_value=FakeSock("192.168.1.5")):
            self.assertEqual(network.lan_ip(), "192.168.1.5")

    def test_skips_loopback_and_falls_back(self):
        with mock.patch.object(network.socket, "socket", return_value=FakeSock("127.0.0.1")), mock.patch.object(
            network.socket, "gethostbyname", return_value="10.0.0.9"
        ):
            self.assertEqual(network.lan_ip(), "10.0.0.9")

    def test_connect_error_falls_back(self):
        with mock.patch.object(
            network.socket, "socket", return_value=FakeSock(erro=OSError("sem rota"))
        ), mock.patch.object(network.socket, "gethostbyname", return_value="10.0.0.9"):
            self.assertEqual(network.lan_ip(), "10.0.0.9")

    def test_no_address_at_all(self):
        with mock.patch.object(
            network.socket, "socket", return_value=FakeSock(erro=OSError("sem rota"))
        ), mock.patch.object(network.socket, "gethostbyname", side_effect=OSError("sem dns")):
            self.assertEqual(network.lan_ip(), "")


class QrTests(unittest.TestCase):
    def test_generates_an_rgb_image(self):
        imagem = qr.make_qr("CARACORE-SETUP|1|2|3|4|5")
        self.assertEqual(imagem.mode, "RGB")
        self.assertGreater(imagem.width, 0)
        self.assertGreater(imagem.height, 0)

    def test_small_box_size_is_clamped(self):
        self.assertEqual(qr.make_qr("x", box_size=0, border=0).mode, "RGB")

    def test_missing_dependency_is_explained(self):
        with mock.patch.dict(sys.modules, {"qrcode": None}):
            with self.assertRaisesRegex(RuntimeError, "qrcode"):
                qr.make_qr("x")


if __name__ == "__main__":
    unittest.main()
