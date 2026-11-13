"""Lacunas do canal de atualizacao: manifesto, download, estado, instalacao e vigia."""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gaspar import updates


def assinar_payload(payload: dict, privada) -> bytes:
    corpo = json.dumps(payload).encode("utf-8")
    envelope = {
        "key_id": "gaspar-teste",
        "payload": base64.b64encode(corpo).decode("ascii"),
        "signature": base64.b64encode(privada.sign(corpo)).decode("ascii"),
    }
    return json.dumps(envelope).encode("utf-8")


def payload_valido(**campos) -> dict:
    dados = {
        "appId": "gaspar",
        "channel": "stable",
        "version": "1.8.0",
        "mandatory": False,
        "min_supported": "1.7.0",
        "notes_url": "https://exemplo/notas",
        "releaseNotes": "Notas",
        "published_at": "2026-11-12T10:00:00Z",
        "assets": {
            "windows-setup": {"url": "https://exemplo/pkg.exe", "sha256": "a" * 64, "size": 10},
            "linux-deb": {"url": "https://exemplo/pkg.deb", "sha256": "b" * 64, "size": 20},
        },
    }
    dados.update(campos)
    return dados


class ServidorArquivo:
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


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.privada = Ed25519PrivateKey.generate()
        self.publica = self.privada.public_key()

    def test_empty_or_oversized_is_refused(self):
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(b"", self.publica)
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(
                b"x" * (updates.LIMITE_MANIFESTO + 1), self.publica
            )

    def test_non_json_and_non_object_are_refused(self):
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(b"nao e json", self.publica)
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(b"[]", self.publica)

    def test_invalid_base64_fields_are_refused(self):
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(b'{"payload": "!!!", "signature": "!!!"}', self.publica)

    def test_missing_payload_or_signature(self):
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(b'{"payload": "", "signature": ""}', self.publica)

    def test_unsigned_or_non_json_payload_is_refused(self):
        corpo = b"nao-json"
        envelope = {
            "payload": base64.b64encode(corpo).decode("ascii"),
            "signature": base64.b64encode(self.privada.sign(corpo)).decode("ascii"),
        }
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "ilegivel"):
            updates.verificar_envelope(json.dumps(envelope).encode("utf-8"), self.publica)

        corpo = b"[]"
        envelope["payload"] = base64.b64encode(corpo).decode("ascii")
        envelope["signature"] = base64.b64encode(self.privada.sign(corpo)).decode("ascii")
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "fora do formato"):
            updates.verificar_envelope(json.dumps(envelope).encode("utf-8"), self.publica)

    def test_missing_version_and_assets_are_refused(self):
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "sem versao"):
            updates.verificar_envelope(assinar_payload(payload_valido(version=""), self.privada), self.publica)
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "sem assets"):
            updates.verificar_envelope(assinar_payload(payload_valido(assets={}), self.privada), self.publica)

    def test_defaults_are_filled_and_key_id_comes_from_envelope(self):
        manifesto = updates.verificar_envelope(assinar_payload(payload_valido(), self.privada), self.publica)
        self.assertEqual(manifesto.versao, "1.8.0")
        self.assertFalse(manifesto.mandatory)
        self.assertEqual(manifesto.key_id, "gaspar-teste")
        self.assertEqual(manifesto.notas, "Notas")


class AssetTests(unittest.TestCase):
    def manifesto(self, **assets):
        return updates.Manifesto(
            versao="1.8.0",
            mandatory=False,
            min_supported="",
            notes_url="",
            notas="",
            publicado_em="",
            key_id="k",
            assets=assets,
        )

    def test_invalid_entries_are_ignored(self):
        chave = "windows-setup" if sys.platform == "win32" else "linux-deb"
        self.assertIsNone(updates._asset(self.manifesto(**{chave: {"url": "", "sha256": "a" * 64}})))
        self.assertIsNone(updates._asset(self.manifesto(**{chave: {"url": "https://x", "sha256": "curto"}})))
        outro = "linux-deb" if chave == "windows-setup" else "windows-setup"
        self.assertIsNone(updates._asset(self.manifesto(**{outro: {"url": "https://x", "sha256": "a" * 64}})))

    def test_non_numeric_size_becomes_zero(self):
        chave = "windows-setup" if sys.platform == "win32" else "linux-deb"
        dados = updates._asset(
            self.manifesto(**{chave: {"url": "https://x", "sha256": "a" * 64, "size": "abc"}})
        )
        self.assertEqual(dados["size"], 0)


class OrigemTests(unittest.TestCase):
    def test_origins_normalization(self):
        self.assertEqual(updates._origens("https://x"), ("https://x",))
        self.assertEqual(updates._origens(["https://a", "", None]), ("https://a",))
        self.assertEqual(updates._origens([]), updates.CANAL_URLS)

    def test_consultar_requires_the_public_key(self):
        with mock.patch.object(updates, "chave_publica", return_value=None):
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "chave publica"):
                updates.consultar_com_origem("https://x")

    def test_single_origin_failure_keeps_the_reason(self):
        with mock.patch.object(
            updates, "buscar_manifesto", side_effect=updates.FalhaAtualizacao("canal respondeu HTTP 404")
        ):
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "HTTP 404"):
                updates.consultar_com_origem("https://x", chave=mock.Mock())

    def test_two_origin_failures_are_joined(self):
        with mock.patch.object(
            updates,
            "buscar_manifesto",
            side_effect=updates.FalhaAtualizacao("falha"),
        ):
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "canal e reserva falharam"):
                updates.consultar_com_origem(["https://a", "https://b"], chave=mock.Mock())

    def test_consultar_returns_only_the_availability(self):
        disponivel = updates.Disponivel("1.8.0", False, "https://x", "a" * 64, 1, "", "", "")
        with mock.patch.object(
            updates, "consultar_com_origem", return_value=(disponivel, "https://a")
        ):
            self.assertIs(updates.consultar(), disponivel)


class DownloadTests(unittest.TestCase):
    def test_address_rules(self):
        self.assertTrue(updates._permitido("https://qualquer"))
        self.assertTrue(updates._permitido("http://127.0.0.1:8000/x"))
        self.assertTrue(updates._permitido("http://localhost:8000/x"))
        self.assertFalse(updates._permitido("http://exemplo.com/x"))
        self.assertFalse(updates._permitido("ftp://exemplo.com/x"))

    def test_abrir_rejects_large_responses_and_http_errors(self):
        with ServidorArquivo({"/grande": (200, b"12345"), "/erro": (500, b"")}) as servidor:
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "grande demais"):
                updates._abrir(servidor.base + "/grande", 5, 4)
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "HTTP 500"):
                updates._abrir(servidor.base + "/erro", 5, 100)

    def test_abrir_reports_unreachable_host(self):
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "inacessivel"):
            updates._abrir("http://127.0.0.1:1/x", 1, 100)

    def test_download_preconditions(self):
        destino = Path(tempfile.mkdtemp())
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "nao e HTTPS"):
            updates.baixar_instalador("ftp://x/pkg.exe", "a" * 64, destino)
        with self.assertRaisesRegex(updates.FalhaAtualizacao, "sem nome"):
            updates.baixar_instalador("http://127.0.0.1:1/", "a" * 64, destino)
        with mock.patch.object(sys, "platform", "win32"):
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "nao e instalador"):
                updates.baixar_instalador("http://127.0.0.1:1/pkg.deb", "a" * 64, destino)

    def test_download_cleans_partial_files_on_error(self):
        with ServidorArquivo({"/vazio.exe": (200, b""), "/faltando.exe": (404, b"")}) as servidor:
            destino = Path(tempfile.mkdtemp())
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "vazio"):
                updates.baixar_instalador(servidor.base + "/vazio.exe", "a" * 64, destino)
            self.assertEqual(list(destino.iterdir()), [])
            with self.assertRaisesRegex(updates.FalhaAtualizacao, "download do pacote falhou"):
                updates.baixar_instalador(servidor.base + "/faltando.exe", "a" * 64, destino)
            self.assertEqual(list(destino.iterdir()), [])


class EstadoTests(unittest.TestCase):
    def test_state_handles_missing_corrupt_and_bom(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
            self.assertEqual(updates.carregar_estado(), {})
            caminho = updates.estado_path()
            caminho.write_text("{quebrado", encoding="utf-8")
            self.assertEqual(updates.carregar_estado(), {})
            caminho.write_text("\ufeff" + json.dumps({"last_check": 5}), encoding="utf-8")
            self.assertEqual(updates.carregar_estado()["last_check"], 5)
            estado = updates.salvar_estado(skipped_version="1.8.0")
            self.assertEqual(estado["last_check"], 5)
            self.assertEqual(updates.carregar_estado()["skipped_version"], "1.8.0")

    def test_installation_reader(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
            self.assertIsNone(updates.ler_resultado_instalacao())
            marcador = updates.estado_path().with_name("update-result.txt")
            marcador.write_text("version=1.8.0\ncode=0\n", encoding="ascii")
            self.assertEqual(
                updates.ler_resultado_instalacao(), {"version": "1.8.0", "code": 0}
            )
            self.assertFalse(marcador.exists())
            self.assertIsNone(updates.ler_resultado_instalacao())
            marcador.write_text("version=1.8.0\ncode=abc\n", encoding="ascii")
            self.assertEqual(updates.ler_resultado_instalacao()["code"], -1)


class AplicarWindowsTests(unittest.TestCase):
    def test_script_waits_for_pid_and_marks_result(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"GASPAR_HOME": tmp}
        ), mock.patch.object(updates.os, "getpid", return_value=4321), mock.patch.object(
            updates.subprocess, "Popen"
        ) as popen:
            updates.aplicar_windows(
                Path(tmp) / "GasparSetup-1.8.0.exe", Path(tmp) / "gaspar.exe", "1.8.0"
            )
        argumentos = popen.call_args.args[0]
        self.assertEqual(argumentos[0], "powershell")
        self.assertIn("-EncodedCommand", argumentos)
        roteiro = base64.b64decode(argumentos[-1]).decode("utf-16-le")
        self.assertIn("Wait-Process -Id 4321", roteiro)
        self.assertIn("GasparSetup-1.8.0.exe", roteiro)
        self.assertIn("version=1.8.0", roteiro)
        self.assertIn("--minimized", roteiro)
        esperado = 0x08000000 if sys.platform == "win32" else 0
        self.assertEqual(popen.call_args.kwargs["creationflags"], esperado)

    def test_script_without_app_to_reopen(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"GASPAR_HOME": tmp}
        ), mock.patch.object(updates.subprocess, "Popen") as popen:
            updates.aplicar_windows(Path(tmp) / "instalador.exe", None, "1.8.0")
        roteiro = base64.b64decode(popen.call_args.args[0][-1]).decode("utf-16-le")
        self.assertNotIn("--minimized", roteiro)


class AbrirPaginaTests(unittest.TestCase):
    def test_empty_and_failures(self):
        self.assertFalse(updates.abrir_pagina(""))
        with mock.patch.object(updates.webbrowser, "open", return_value=True):
            self.assertTrue(updates.abrir_pagina("https://x"))
        with mock.patch.object(updates.webbrowser, "open", side_effect=RuntimeError("x")):
            self.assertFalse(updates.abrir_pagina("https://x"))


class AppFalso:
    def __init__(self):
        self.chamadas = []
        self.logs = []

    def ui(self, callback, *args):
        self.chamadas.append((callback, args))

    def log_system(self, mensagem):
        self.logs.append(mensagem)

    def mostrar_atualizacao(self, _info):
        pass


def disponivel(versao="1.8.0", mandatory=False) -> updates.Disponivel:
    return updates.Disponivel(versao, mandatory, "https://x/pkg.exe", "a" * 64, 1, "", "", "")


class VigiaTests(unittest.TestCase):
    def test_reserve_and_return_are_logged_once(self):
        app = AppFalso()
        vigia = updates.Vigia(app, mock.Mock(), url=("https://principal", "https://reserva"))
        with mock.patch.object(
            updates, "consultar_com_origem", return_value=(disponivel(), "https://reserva")
        ):
            self.assertIsNotNone(vigia.verificar_agora())
            vigia.verificar_agora()
        self.assertEqual(len(app.logs), 1)
        self.assertIn("endereco de reserva", app.logs[0])
        with mock.patch.object(
            updates, "consultar_com_origem", return_value=(disponivel(), "https://principal")
        ):
            vigia.verificar_agora()
        self.assertIn("de volta ao endereco principal", app.logs[-1])

    def test_errors_are_deduplicated(self):
        app = AppFalso()
        vigia = updates.Vigia(app, mock.Mock())
        with mock.patch.object(
            updates, "consultar_com_origem", side_effect=updates.FalhaAtualizacao("fora do ar")
        ):
            vigia._consultar()
            vigia._consultar()
        self.assertEqual(len(app.logs), 1)
        with mock.patch.object(
            updates, "consultar_com_origem", side_effect=updates.FalhaAtualizacao("outro erro")
        ):
            vigia._consultar()
        self.assertEqual(len(app.logs), 2)

    def test_unexpected_error_is_not_repeated(self):
        app = AppFalso()
        vigia = updates.Vigia(app, mock.Mock())
        with mock.patch.object(updates, "consultar_com_origem", side_effect=ValueError("x")):
            vigia._consultar()
            vigia._consultar()
        self.assertEqual(len(app.logs), 1)
        self.assertIn("ValueError", app.logs[0])

    def test_success_saves_last_check_and_respects_skip(self):
        app = AppFalso()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
            vigia = updates.Vigia(app, mock.Mock())
            with mock.patch.object(
                updates, "consultar_com_origem", return_value=(disponivel(), updates.CANAL_URLS[0])
            ):
                vigia._consultar()
            self.assertGreater(updates.carregar_estado()["last_check"], 0)
            self.assertTrue(app.chamadas)

            app.chamadas.clear()
            updates.salvar_estado(skipped_version="1.8.0")
            with mock.patch.object(
                updates, "consultar_com_origem", return_value=(disponivel(), updates.CANAL_URLS[0])
            ):
                vigia._consultar()
            self.assertEqual(app.chamadas, [])

            with mock.patch.object(
                updates,
                "consultar_com_origem",
                return_value=(disponivel(mandatory=True), updates.CANAL_URLS[0]),
            ):
                vigia._consultar()
            self.assertTrue(app.chamadas)

    def test_loop_checks_the_channel(self):
        app = AppFalso()
        vigia = updates.Vigia(app, mock.Mock())
        with mock.patch.object(updates, "ESPERA_INICIAL", (0, 0)), mock.patch.object(
            updates, "INTERVALO_MINIMO", 0
        ), mock.patch.object(updates, "INTERVALO_CONSULTA", 0.02), mock.patch.object(
            updates.random, "uniform", return_value=0
        ), mock.patch.object(
            updates, "consultar_com_origem", side_effect=updates.FalhaAtualizacao("fora do ar")
        ):
            vigia.iniciar()
            time.sleep(0.15)
            vigia.parar()
            time.sleep(0.05)
        self.assertTrue(app.logs)


if __name__ == "__main__":
    unittest.main()
