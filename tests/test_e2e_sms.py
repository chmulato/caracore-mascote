"""Ponta a ponta do SMS: PDV assina, servidor aceita, fila entrega ao celular e recibo volta.

Tudo em processos locais: HTTP real, TCP real e criptografia real; o celular e um
dublê que implementa o mesmo contrato do aplicativo Android.
"""

from __future__ import annotations

import base64
import json
import secrets
import socket
import struct
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

from gaspar.sms import e2e, signing
from gaspar.sms.audit import AuditLog
from gaspar.sms.bridge import SmsBridge
from gaspar.sms.client import PhoneClient
from gaspar.sms.config import load_config
from gaspar.sms.crypto import decrypt, encrypt, key_from_base64
from gaspar.sms.network import lan_ip
from gaspar.sms.protocol import frame
from gaspar.sms.server import SmsHttpServer
from gaspar.sms.store import SmsStore, STATUS_DELIVERED, STATUS_FAILED, STATUS_SENT

TOKEN = "token-e2e"
NUMERO = "5511999999999"


def read_exact(sock: socket.socket, size: int) -> bytes:
    dados = bytearray()
    while len(dados) < size:
        parte = sock.recv(size - len(dados))
        if not parte:
            break
        dados.extend(parte)
    return bytes(dados)


class CelularE2E:
    """Recebe o envelope fechado, guarda o comando e confirma o recebimento."""

    def __init__(self, chave: bytes, privada, ack=True):
        self.chave = chave
        self.privada = privada
        self.comandos: list[dict] = []
        self.erro: Exception | None = None
        self._ack = ack
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
        self._thread.join(timeout=3)

    def _serve(self):
        try:
            conexao, _ = self._sock.accept()
            conexao.settimeout(3)
            with conexao:
                cabecalho = read_exact(conexao, 4)
                if len(cabecalho) != 4:
                    return
                tamanho = struct.unpack(">I", cabecalho)[0]
                comando = json.loads(decrypt(self.chave, read_exact(conexao, tamanho)).decode("utf-8"))
                self.comandos.append(comando)
                if self._ack:
                    conexao.sendall(
                        frame(encrypt(self.chave, json.dumps({"ok": True}).encode("utf-8")))
                    )
        except Exception as exc:
            self.erro = exc

    def abrir(self, comando: dict) -> dict:
        bruto = e2e.open_sealed(self.privada, comando["envelope"], str(comando["id"]).encode("ascii"))
        return json.loads(bruto.decode("utf-8"))


class FluxoCompletoE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.config = load_config(raiz / "sms.json")
        self.config.api_token = TOKEN
        self.config.phone_host = "127.0.0.1"
        self.privada, self.publica = e2e.generate_keypair()
        self.config.set_phone_public_key(base64.b64encode(self.publica).decode("ascii"))
        self.config.save()
        self.chave = key_from_base64(self.config.shared_secret_b64)
        self.store = SmsStore(raiz / "sms_state.json", AuditLog(raiz / "sms_audit.jsonl"))
        self.celular = None
        self.servidor = None
        self.servidores: list[SmsHttpServer] = []
        self.bridge = None

    def tearDown(self):
        for servidor in self.servidores:
            servidor.stop()
        self.servidores.clear()
        if self.bridge is not None:
            self.bridge.stop()
        if self.celular is not None:
            self.celular.__exit__()
        self.tmp.cleanup()

    def start(self, porta_celular: int, ack=True):
        if porta_celular == 0:
            self.celular = CelularE2E(self.chave, self.privada, ack=ack)
            self.celular.__enter__()
            self.config.phone_port = self.celular.port
        else:
            self.config.phone_port = porta_celular
        self.bridge = SmsBridge(
            self.config,
            self.store,
            client_factory=lambda host, port, key: PhoneClient(host, port, key, timeout=2, ack_timeout=1),
            retry_delay=0.02,
            max_attempts=1,
        )
        self.bridge.start()
        self._abrir_servidor("127.0.0.1")
        self.servidor = self.servidores[0]

    def _abrir_servidor(self, host: str) -> SmsHttpServer:
        servidor = SmsHttpServer(self.bridge, self.config, host=host, port=0)
        servidor.start()
        self.servidores.append(servidor)
        return servidor

    def request(
        self,
        method: str,
        path: str,
        body=None,
        token: str | None = None,
        nonce: str | None = None,
        host: str = "127.0.0.1",
        port: int | None = None,
    ):
        conexao = HTTPConnection(host, port or self.servidor.port, timeout=5)
        cabecalhos = {}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            cabecalhos["Content-Type"] = "application/json"
        if token is not None:
            cabecalhos["X-Api-Token"] = token
        if method == "POST" and path == "/api/sms":
            momento = int(time.time())
            nonce = nonce or secrets.token_hex(8)
            cabecalhos[signing.TIMESTAMP_HEADER] = str(momento)
            cabecalhos[signing.NONCE_HEADER] = nonce
            cabecalhos[signing.SIGNATURE_HEADER] = signing.sign_request(
                TOKEN.encode("utf-8"), method, path, payload or b"", momento, nonce
            )
        conexao.request(method, path, body=payload, headers=cabecalhos)
        resposta = conexao.getresponse()
        dados = json.loads(resposta.read().decode("utf-8"))
        conexao.close()
        return resposta.status, dados

    def wait_for(self, job_id: str, statuses: set[str], timeout: float = 5.0):
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            job = self.store.get(job_id)
            if job is not None and job.status in statuses:
                return job
            time.sleep(0.02)
        return self.store.get(job_id)

    def test_sale_becomes_sms_then_receipt_marks_delivered(self):
        self.start(porta_celular=0)
        codigo, dados = self.request(
            "POST",
            "/api/sms",
            {
                "number": NUMERO,
                "template": "venda_confirmada",
                "variaveis": {"venda": "A-10", "total": "19,90"},
                "venda_id": "venda-e2e",
            },
            token=TOKEN,
        )
        self.assertEqual(codigo, 202, dados)
        self.assertTrue(dados["sealed"])

        job = self.wait_for(dados["id"], {STATUS_SENT})
        self.assertEqual(job.status, STATUS_SENT)
        self.assertTrue(job.confirmed)

        self.assertIsNone(self.celular.erro)
        self.assertEqual(len(self.celular.comandos), 1)
        comando = self.celular.comandos[0]
        self.assertEqual(str(comando["id"]), dados["id"])
        self.assertNotIn("number", comando)
        self.assertNotIn("message", comando)
        conteudo = self.celular.abrir(comando)
        self.assertEqual(conteudo["number"], NUMERO)
        self.assertIn("Venda A-10", conteudo["message"])
        self.assertIn("R$ 19,90", conteudo["message"])

        recibo = base64.b64encode(
            encrypt(
                self.chave,
                json.dumps({"id": dados["id"], "status": "delivered", "detail": "entregue"}).encode("utf-8"),
            )
        ).decode("ascii")
        codigo, resposta = self.request("POST", "/api/mobile/receipt", {"blob": recibo})
        self.assertEqual(codigo, 202, resposta)
        self.assertEqual(self.store.get(dados["id"]).status, STATUS_DELIVERED)

        estado = (Path(self.tmp.name) / "sms_state.json").read_text(encoding="utf-8")
        trilha = (Path(self.tmp.name) / "sms_audit.jsonl").read_text(encoding="utf-8")
        for texto in (estado, trilha):
            self.assertNotIn(NUMERO, texto)
            self.assertNotIn("Venda A-10", texto)

    def test_offline_phone_fails_without_blocking_the_sale(self):
        porta = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        porta.bind(("127.0.0.1", 0))
        porta_livre = porta.getsockname()[1]
        porta.close()
        self.start(porta_celular=porta_livre)

        codigo, dados = self.request(
            "POST",
            "/api/sms",
            {
                "number": NUMERO,
                "template": "venda_confirmada",
                "variaveis": {"venda": "B-20", "total": "5,00"},
                "venda_id": "venda-offline",
            },
            token=TOKEN,
        )
        self.assertEqual(codigo, 202, dados)
        job = self.wait_for(dados["id"], {STATUS_FAILED})
        self.assertEqual(job.status, STATUS_FAILED)
        self.assertTrue(job.error)

    def test_health_and_token_are_enforced(self):
        self.start(porta_celular=0)
        codigo, dados = self.request("GET", "/api/health")
        self.assertEqual(codigo, 200)
        self.assertTrue(dados["ok"])
        codigo, dados = self.request(
            "POST", "/api/sms", {"number": NUMERO, "message": "oi"}, token="errado"
        )
        self.assertEqual(codigo, 401)
        self.assertFalse(dados["ok"])

    def test_free_form_message_is_refused_by_the_model(self):
        self.start(porta_celular=0)
        codigo, dados = self.request(
            "POST",
            "/api/sms",
            {"number": NUMERO, "message": "oi", "venda_id": "venda-livre"},
            token=TOKEN,
        )
        self.assertEqual(codigo, 400, dados)
        self.assertIn("fora do modelo", dados["error"])
        self.assertEqual(self.store.recent(20), [])
        self.assertEqual(self.celular.comandos, [])

    def test_replayed_nonce_is_refused(self):
        self.start(porta_celular=0)
        corpo = {
            "number": NUMERO,
            "template": "venda_confirmada",
            "variaveis": {"venda": "C-30", "total": "7,00"},
            "venda_id": "venda-repetida",
        }
        nonce = secrets.token_hex(8)
        codigo, dados = self.request("POST", "/api/sms", corpo, token=TOKEN, nonce=nonce)
        self.assertEqual(codigo, 202, dados)
        codigo, repetido = self.request("POST", "/api/sms", corpo, token=TOKEN, nonce=nonce)
        self.assertEqual(codigo, 401, repetido)
        self.assertIn("pedido repetido", repetido["error"])
        self.assertEqual(len(self.store.recent(20)), 1)

    def test_request_from_outside_the_computer_is_blocked(self):
        self.start(porta_celular=0)
        endereco = lan_ip()
        if not endereco or endereco.startswith("127."):
            self.skipTest("computador sem endereco de rede local para simular origem externa")
        externo = self._abrir_servidor("0.0.0.0")
        codigo, dados = self.request(
            "POST",
            "/api/sms",
            {
                "number": NUMERO,
                "template": "venda_confirmada",
                "variaveis": {"venda": "D-40", "total": "9,00"},
                "venda_id": "venda-externa",
            },
            token=TOKEN,
            host=endereco,
            port=externo.port,
        )
        self.assertEqual(codigo, 403, dados)
        self.assertIn("proprio computador", dados["error"])
        self.assertEqual(self.store.recent(20), [])
        self.assertEqual(self.celular.comandos, [])


if __name__ == "__main__":
    unittest.main()
