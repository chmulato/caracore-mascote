"""Ciclo completo do canal: manifesto assinado, download conferido e entrega ao instalador."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gaspar import updates


def assinar(payload: dict, privada) -> bytes:
    corpo = json.dumps(payload).encode("utf-8")
    return json.dumps(
        {
            "key_id": "gaspar-e2e",
            "payload": base64.b64encode(corpo).decode("ascii"),
            "signature": base64.b64encode(privada.sign(corpo)).decode("ascii"),
        }
    ).encode("utf-8")


class ServidorCanal:
    """Serve o manifesto e os pacotes como o gateway faria."""

    def __init__(self, rotas: dict[str, tuple[int, bytes]]):
        self.rotas = rotas
        dono = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, corpo = dono.rotas.get(self.path, (404, b""))
                self.send_response(status)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *_args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.httpd.shutdown()
        self.httpd.server_close()


def porta_fechada() -> str:
    import socket

    soquete = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soquete.bind(("127.0.0.1", 0))
    porta = soquete.getsockname()[1]
    soquete.close()
    return f"http://127.0.0.1:{porta}/latest.json"


class CicloDeAtualizacaoE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        ambiente = mock.patch.dict(os.environ, {"GASPAR_HOME": str(self.raiz / "dados")})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        self.addCleanup(self.tmp.cleanup)

        self.privada = Ed25519PrivateKey.generate()
        self.chave_path = self.raiz / "gaspar-update-public.pem"
        self.chave_path.write_bytes(
            self.privada.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
        self.chave = updates.chave_publica(self.chave_path)
        self.assertIsNotNone(self.chave)

        self.pacote = b"MZ" + b"gaspar-instalador" * 512
        self.sha = hashlib.sha256(self.pacote).hexdigest()
        self.servidor = ServidorCanal({})
        self.servidor.__enter__()
        self.addCleanup(self.servidor.__exit__)

    def publicar(self, **campos) -> dict:
        base = self.servidor.base
        payload = {
            "appId": "gaspar",
            "channel": "stable",
            "version": "1.8.0",
            "mandatory": False,
            "min_supported": "1.7.0",
            "notes_url": f"{base}/notas",
            "releaseNotes": "Correcoes da versao nova.",
            "published_at": "2026-11-12T10:00:00Z",
            "assets": {
                "windows-setup": {
                    "url": f"{base}/Gaspar-1.8.0.exe",
                    "sha256": self.sha,
                    "size": len(self.pacote),
                },
                "linux-deb": {
                    "url": f"{base}/gaspar_1.8.0_amd64.deb",
                    "sha256": self.sha,
                    "size": len(self.pacote),
                },
            },
        }
        payload.update(campos)
        self.servidor.rotas["/Gaspar-1.8.0.exe"] = (200, self.pacote)
        self.servidor.rotas["/gaspar_1.8.0_amd64.deb"] = (200, self.pacote)
        self.servidor.rotas["/latest.json"] = (200, assinar(payload, self.privada))
        return payload

    def test_manifesto_assinado_leva_ao_pacote_conferido(self):
        self.publicar()
        disponivel, origem = updates.consultar_com_origem(
            self.servidor.base + "/latest.json", self.chave, local="1.7.3"
        )
        self.assertEqual(origem, self.servidor.base + "/latest.json")
        self.assertEqual(disponivel.versao, "1.8.0")
        self.assertFalse(disponivel.mandatory)
        self.assertEqual(disponivel.sha256, self.sha)
        self.assertEqual(disponivel.notas, "Correcoes da versao nova.")

        destino = self.raiz / "downloads"
        with mock.patch("sys.platform", "win32"):
            arquivo = updates.baixar_instalador(disponivel.url, disponivel.sha256, destino)
        self.assertEqual(arquivo, destino / "Gaspar-1.8.0.exe")
        self.assertEqual(arquivo.read_bytes(), self.pacote)
        self.assertEqual(sorted(p.name for p in destino.iterdir()), ["Gaspar-1.8.0.exe"])

    def test_pacote_adulterado_nao_fica_no_disco(self):
        self.publicar()
        destino = self.raiz / "downloads"
        errado = hashlib.sha256(b"outra coisa").hexdigest()
        with mock.patch("sys.platform", "win32"):
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "SHA-256"):
                updates.baixar_instalador(
                    self.servidor.base + "/Gaspar-1.8.0.exe", errado, destino
                )
        self.assertEqual(list(destino.iterdir()) if destino.exists() else [], [])

    def test_manifesto_adulterado_e_recusado(self):
        payload = self.publicar()
        corpo = json.dumps(payload).encode("utf-8")
        envelope = json.loads(self.servidor.rotas["/latest.json"][1])
        envelope["payload"] = base64.b64encode(corpo + b" ").decode("ascii")
        self.servidor.rotas["/latest.json"] = (200, json.dumps(envelope).encode("utf-8"))
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "assinatura"):
            updates.consultar_com_origem(self.servidor.base + "/latest.json", self.chave, local="1.7.3")

    def test_versao_igual_nao_oferece_nada(self):
        self.publicar()
        disponivel, _ = updates.consultar_com_origem(
            self.servidor.base + "/latest.json", self.chave, local="1.8.0"
        )
        self.assertIsNone(disponivel)

    def test_versao_abaixo_do_minimo_vira_obrigatoria(self):
        self.publicar(min_supported="1.7.0")
        disponivel, _ = updates.consultar_com_origem(
            self.servidor.base + "/latest.json", self.chave, local="1.6.0"
        )
        self.assertTrue(disponivel.mandatory)
        self.assertEqual(disponivel.versao, "1.8.0")

    def test_reserva_responde_quando_o_principal_cai(self):
        self.publicar()
        principal = porta_fechada()
        disponivel, origem = updates.consultar_com_origem(
            (principal, self.servidor.base + "/latest.json"), self.chave, local="1.7.3"
        )
        self.assertEqual(origem, self.servidor.base + "/latest.json")
        self.assertEqual(disponivel.versao, "1.8.0")

    def test_entrega_ao_instalador_e_marcador_do_resultado(self):
        self.publicar()
        disponivel, _ = updates.consultar_com_origem(
            self.servidor.base + "/latest.json", self.chave, local="1.7.3"
        )
        destino = self.raiz / "downloads"
        with mock.patch("sys.platform", "win32"):
            instalador = updates.baixar_instalador(disponivel.url, disponivel.sha256, destino)
            app_exe = self.raiz / "Gaspar" / "Gaspar.exe"
            with mock.patch("sys.platform", "win32"), mock.patch(
                "gaspar.updates.subprocess.Popen"
            ) as popen:
                updates.aplicar_windows(instalador, app_exe, disponivel.versao)

        comando = popen.call_args.args[0]
        self.assertEqual(comando[:5], ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden"])
        roteiro = base64.b64decode(comando[-1]).decode("utf-16-le")
        self.assertIn(f"Wait-Process -Id {os.getpid()}", roteiro)
        self.assertIn(str(instalador), roteiro)
        self.assertIn(f"version={disponivel.versao}", roteiro)
        self.assertIn("--minimized", roteiro)

        marcador = updates.estado_path().with_name("update-result.txt")
        marcador.write_text(f"version={disponivel.versao}\ncode=0\n", encoding="ascii")
        self.assertEqual(
            updates.ler_resultado_instalacao(),
            {"version": disponivel.versao, "code": 0},
        )
        self.assertFalse(marcador.exists())


if __name__ == "__main__":
    unittest.main()
