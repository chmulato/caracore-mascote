"""Testes do canal de atualizacao (sem rede externa e sem chave real)."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import subprocess
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

ROOT = Path(__file__).resolve().parent.parent


def chave_teste():
    privada = Ed25519PrivateKey.generate()
    publica = privada.public_key()
    return privada, publica


def envelope(payload: dict, chave, key_id: str = "gaspar-teste") -> dict:
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    setup = payload["assets"].get("windows-setup") or {}
    return {
        "payload": base64.b64encode(payload_bytes).decode("ascii"),
        "signature": base64.b64encode(chave.sign(payload_bytes)).decode("ascii"),
        "key_id": key_id,
        "appId": payload["appId"],
        "version": payload["version"],
        "downloadUrl": setup.get("url"),
        "sha256": setup.get("sha256"),
        "mandatory": payload.get("mandatory", False),
        "releaseNotes": payload.get("releaseNotes", ""),
        "assets": payload["assets"],
    }


def payload_teste(versao: str = "1.7.1", **campos) -> dict:
    dados = {
        "appId": "gaspar",
        "version": versao,
        "channel": "stable",
        "published_at": "2026-11-12T10:00:00Z",
        "mandatory": False,
        "min_supported": "1.7.0",
        "notes_url": "https://gaspar.caracore.com.br/",
        "releaseNotes": "Correcoes desta versao.",
        "assets": {
            "windows-setup": {
                "url": "https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.1/GasparSetup-1.7.1.exe",
                "sha256": "a" * 64,
                "size": 123,
            },
            "linux-deb": {
                "url": "https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.1/gaspar_1.7.1_amd64.deb",
                "sha256": "b" * 64,
                "size": 456,
            },
        },
    }
    dados.update(campos)
    return dados


class VerificacaoTest(unittest.TestCase):
    def test_envelope_assinado_e_aceito(self):
        privada, publica = chave_teste()
        manifesto = updates.verificar_envelope(
            json.dumps(envelope(payload_teste(), privada)).encode("utf-8"), publica
        )
        self.assertEqual("1.7.1", manifesto.versao)
        self.assertEqual("gaspar-teste", manifesto.key_id)
        self.assertEqual("1.7.0", manifesto.min_supported)
        self.assertIn("windows-setup", manifesto.assets)

    def test_assinatura_adulterada_e_recusada(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(), privada)
        payload = json.loads(base64.b64decode(corpo["payload"]))
        payload["version"] = "9.9.9"
        corpo["payload"] = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(json.dumps(corpo).encode("utf-8"), publica)

    def test_espelho_fora_do_payload_nao_e_usado(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(), privada)
        corpo["downloadUrl"] = "https://exemplo.invalido/malicioso.exe"
        corpo["version"] = "9.9.9"
        manifesto = updates.verificar_envelope(json.dumps(corpo).encode("utf-8"), publica)
        self.assertEqual("1.7.1", manifesto.versao)
        self.assertIn("chmulato/caracore-mascote", manifesto.assets["windows-setup"]["url"])

    def test_manifesto_de_outro_aplicativo_e_recusado(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(appId="outro"), privada)
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(json.dumps(corpo).encode("utf-8"), publica)

    def test_canal_desconhecido_e_recusado(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(channel="beta"), privada)
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(json.dumps(corpo).encode("utf-8"), publica)

    def test_endereco_externo_exige_https(self):
        self.assertTrue(updates._permitido("https://gaspar.caracore.com.br/latest.json"))
        self.assertTrue(updates._permitido("http://127.0.0.1:8000/latest.json"))
        self.assertFalse(updates._permitido("http://gaspar.caracore.com.br/latest.json"))
        self.assertFalse(updates._permitido("ftp://gaspar.caracore.com.br/latest.json"))


class VersaoTest(unittest.TestCase):
    def test_compara_partes_numericas(self):
        self.assertTrue(updates.ha_versao_nova("1.7.1", "1.7.0"))
        self.assertTrue(updates.ha_versao_nova("1.10.0", "1.9.9"))
        self.assertFalse(updates.ha_versao_nova("1.7.0", "1.7.0"))
        self.assertFalse(updates.ha_versao_nova("1.6.9", "1.7.0"))

    def test_aceita_prefixo_v(self):
        self.assertTrue(updates.ha_versao_nova("v1.7.1", "1.7.0"))

    def test_pre_release_e_anterior_a_versao_final(self):
        self.assertTrue(updates.ha_versao_nova("1.7.1", "1.7.1-rc1"))
        self.assertFalse(updates.ha_versao_nova("1.7.1-rc1", "1.7.1"))


class AvaliacaoTest(unittest.TestCase):
    def _manifesto(self, **campos) -> updates.Manifesto:
        dados = payload_teste(**campos)
        return updates.Manifesto(
            versao=dados["version"],
            mandatory=bool(dados.get("mandatory")),
            min_supported=str(dados.get("min_supported") or ""),
            notes_url=str(dados.get("notes_url") or ""),
            notas=str(dados.get("releaseNotes") or ""),
            publicado_em=str(dados.get("published_at") or ""),
            key_id="gaspar-teste",
            assets=dados["assets"],
        )

    @mock.patch.object(updates.sys, "platform", "win32")
    def test_quem_ja_esta_na_versao_nao_recebe_aviso(self):
        self.assertIsNone(updates.avaliar(self._manifesto(), "1.7.1"))

    @mock.patch.object(updates.sys, "platform", "win32")
    def test_versao_mais_nova_aponta_para_o_instalador(self):
        disponivel = updates.avaliar(self._manifesto(), "1.7.0")
        self.assertIsNotNone(disponivel)
        self.assertEqual("1.7.1", disponivel.versao)
        self.assertFalse(disponivel.mandatory)
        self.assertIn("GasparSetup-1.7.1.exe", disponivel.url)

    @mock.patch.object(updates.sys, "platform", "win32")
    def test_abaixo_do_minimo_vira_obrigatoria(self):
        disponivel = updates.avaliar(self._manifesto(min_supported="1.8.0"), "1.7.0")
        self.assertTrue(disponivel.mandatory)

    @mock.patch.object(updates.sys, "platform", "win32")
    def test_corpo_com_mandatory_vira_obrigatoria(self):
        disponivel = updates.avaliar(self._manifesto(mandatory=True), "1.7.0")
        self.assertTrue(disponivel.mandatory)

    @mock.patch.object(updates.sys, "platform", "linux")
    def test_linux_recebe_o_pacote_deb(self):
        disponivel = updates.avaliar(self._manifesto(), "1.7.0")
        self.assertIn("gaspar_1.7.1_amd64.deb", disponivel.url)

    @mock.patch.object(updates.sys, "platform", "win32")
    def test_manifesto_sem_pacote_da_plataforma_falha(self):
        manifesto = self._manifesto()
        sem_setup = updates.Manifesto(
            versao=manifesto.versao,
            mandatory=False,
            min_supported=manifesto.min_supported,
            notes_url=manifesto.notes_url,
            notas="",
            publicado_em="",
            key_id="gaspar-teste",
            assets={"linux-deb": manifesto.assets["linux-deb"]},
        )
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.avaliar(sem_setup, "1.7.0")


class _ServidorArquivo:
    def __init__(self, conteudo: bytes):
        conteudo = conteudo

        class Manipulador(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Length", str(len(conteudo)))
                self.end_headers()
                self.wfile.write(conteudo)

            def log_message(self, *_args):
                pass

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def fechar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


class DownloadTest(unittest.TestCase):
    def test_baixa_e_confere_o_sha256(self):
        conteudo = os.urandom(2048)
        servidor = _ServidorArquivo(conteudo)
        self.addCleanup(servidor.fechar)
        with tempfile.TemporaryDirectory() as tmp:
            alvo = updates.baixar_instalador(
                f"{servidor.url}/GasparSetup-1.7.1.exe",
                hashlib.sha256(conteudo).hexdigest(),
                Path(tmp),
            )
            self.assertTrue(alvo.exists())
            self.assertEqual(conteudo, alvo.read_bytes())

    def test_cria_a_pasta_de_destino(self):
        conteudo = os.urandom(512)
        servidor = _ServidorArquivo(conteudo)
        self.addCleanup(servidor.fechar)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "dados" / "updates"
            alvo = updates.baixar_instalador(
                f"{servidor.url}/GasparSetup-1.7.3.exe",
                hashlib.sha256(conteudo).hexdigest(),
                destino,
            )
            self.assertEqual(destino, alvo.parent)
            self.assertEqual(conteudo, alvo.read_bytes())

    def test_sha_errado_apaga_o_arquivo(self):
        conteudo = os.urandom(1024)
        servidor = _ServidorArquivo(conteudo)
        self.addCleanup(servidor.fechar)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(updates.FalhaAtualizacao):
                updates.baixar_instalador(
                    f"{servidor.url}/GasparSetup-1.7.1.exe", "0" * 64, Path(tmp)
                )
            self.assertEqual([], list(Path(tmp).iterdir()))


class EstadoTest(unittest.TestCase):
    def test_guarda_e_le_a_versao_pulada(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
                updates.salvar_estado(skipped_version="1.7.1")
                self.assertEqual("1.7.1", updates.carregar_estado()["skipped_version"])


class InstalacaoTest(unittest.TestCase):
    def test_aspas_do_powershell_dobram_apostrofo(self):
        self.assertEqual(
            "'C:\\O''Brien\\GasparSetup-1.0.0.exe'",
            updates._ps_aspas("C:\\O'Brien\\GasparSetup-1.0.0.exe"),
        )

    def test_roteiro_espera_o_processo_e_marca_o_resultado(self):
        roteiro = updates._roteiro_windows(
            Path("C:/Temp/GasparSetup-1.0.0.exe"),
            Path("C:/Gaspar/gaspar.exe"),
            "1.0.0",
            4321,
            Path("C:/Dados/update-result.txt"),
        )
        self.assertIn("Wait-Process -Id 4321 -Timeout 60", roteiro)
        self.assertIn("'/SILENT','/SUPPRESSMSGBOXES','/NORESTART'", roteiro)
        self.assertIn("version=1.0.0`ncode=$codigo", roteiro)
        self.assertIn("ArgumentList '--minimized'", roteiro)

    def test_ajudante_sobe_sem_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
                with mock.patch.object(updates.subprocess, "Popen") as popen:
                    updates.aplicar_windows(
                        Path("C:/Temp/GasparSetup-1.7.3.exe"), None, "1.7.3"
                    )
        self.assertEqual(1, popen.call_count)
        flags = popen.call_args.kwargs["creationflags"]
        sem_console = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        destacado = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        if sys.platform == "win32":
            self.assertEqual(sem_console, flags)
        else:
            self.assertEqual(0, flags)
        self.assertFalse(flags & destacado)

    def test_le_marcador_de_instalacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
                marcador = updates.estado_path().with_name("update-result.txt")
                marcador.write_text("version=1.7.1\ncode=0\n", encoding="ascii")
                self.assertEqual(
                    {"version": "1.7.1", "code": 0},
                    updates.ler_resultado_instalacao(),
                )
                self.assertFalse(marcador.exists())


sys.path.insert(0, str(ROOT / "tools"))
import gaspar_channel  # noqa: E402


class FerramentaTest(unittest.TestCase):
    def setUp(self):
        self._sidecar = (
            f"{'a' * 64}  GasparSetup-1.7.1.exe\n"
            f"{'b' * 64}  gaspar_1.7.1_amd64.deb\n"
        ).encode("utf-8")
        patcher = mock.patch.object(
            gaspar_channel, "_baixar_asset", return_value=self._sidecar
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _release(self, **campos) -> dict:
        dados = {
            "tagName": "gaspar-v1.7.1",
            "name": "Gaspar 1.7.1",
            "body": "Correcoes.\nmandatory: true\n",
            "publishedAt": "2026-11-12T10:00:00Z",
            "isDraft": False,
            "isPrerelease": False,
            "assets": [
                {
                    "name": "GasparSetup-1.7.1.exe",
                    "size": 100,
                    "digest": "sha256:" + "a" * 64,
                    "id": 1,
                },
                {
                    "name": "gaspar_1.7.1_amd64.deb",
                    "size": 200,
                    "digest": "sha256:" + "b" * 64,
                    "id": 2,
                },
                {
                    "name": "Gaspar-1.7.1-amd64.AppImage",
                    "size": 300,
                    "digest": "sha256:" + "c" * 64,
                    "id": 3,
                },
                {"name": "SHA256SUMS.txt", "size": 10, "digest": None, "id": 4},
            ],
        }
        dados.update(campos)
        return dados

    def _config(self) -> dict:
        return gaspar_channel.ler_config()

    def test_monta_payload_com_os_dois_pacotes(self):
        versao, payload = gaspar_channel.montar_payload(self._release(), self._config())
        self.assertEqual("1.7.1", versao)
        self.assertEqual("gaspar", payload["appId"])
        self.assertEqual("stable", payload["channel"])
        self.assertTrue(payload["mandatory"])
        self.assertEqual(set(payload["assets"]), {"windows-setup", "linux-deb"})
        self.assertEqual("a" * 64, payload["assets"]["windows-setup"]["sha256"])
        self.assertIn("gaspar-v1.7.1/GasparSetup-1.7.1.exe", payload["assets"]["windows-setup"]["url"])

    def test_manifesto_da_ferramenta_passa_pela_verificacao_do_app(self):
        privada, publica = chave_teste()
        config = self._config()
        _versao, payload = gaspar_channel.montar_payload(self._release(), config)
        corpo = gaspar_channel.assinar(payload, config, privada)
        manifesto = updates.verificar_envelope(corpo, publica)
        self.assertEqual("1.7.1", manifesto.versao)
        self.assertTrue(manifesto.mandatory)

    def test_sha_do_digest_que_diverge_do_sidecar_e_recusado(self):
        dados = self._release()
        dados["assets"][0]["digest"] = "sha256:" + "f" * 64
        with self.assertRaises(gaspar_channel.Falha):
            gaspar_channel.montar_payload(dados, self._config())

    def test_release_rascunho_ou_pre_release_e_recusada(self):
        for campos in ({"isDraft": True}, {"isPrerelease": True}):
            with self.assertRaises(gaspar_channel.Falha):
                gaspar_channel.montar_payload(self._release(**campos), self._config())

    def test_etiqueta_de_outro_produto_e_recusada(self):
        with self.assertRaises(gaspar_channel.Falha):
            gaspar_channel.montar_payload(
                self._release(tagName="android-v1.2"), self._config()
            )

    def test_release_sem_instalador_e_recusada(self):
        dados = self._release()
        dados["assets"] = [a for a in dados["assets"] if not a["name"].endswith(".exe")]
        with self.assertRaises(gaspar_channel.Falha):
            gaspar_channel.montar_payload(dados, self._config())


class CanalTest(unittest.TestCase):
    def _corpo(self, versao: str = "1.8.0", privada=None) -> bytes:
        if privada is None:
            privada, _ = chave_teste()
        return json.dumps(envelope(payload_teste(versao), privada)).encode("utf-8")

    def test_principal_e_o_gateway_e_a_reserva_e_o_dominio_antigo(self):
        self.assertEqual(
            "https://api.caracore.com.br/releases/gaspar/latest.json", updates.CANAL_URL
        )
        self.assertEqual("https://gaspar.caracore.com.br/latest.json", updates.CANAL_RESERVA)
        self.assertEqual((updates.CANAL_URL, updates.CANAL_RESERVA), updates.CANAL_URLS)

    def test_principal_responde_e_a_reserva_nao_e_chamada(self):
        privada, publica = chave_teste()
        corpo = self._corpo(privada=privada)
        chamadas = []

        def buscar(url, timeout=updates.TIMEOUT):
            chamadas.append(url)
            return corpo

        with mock.patch.object(updates, "buscar_manifesto", side_effect=buscar):
            disponivel, origem = updates.consultar_com_origem(chave=publica, local="1.7.0")
        self.assertEqual(updates.CANAL_URL, origem)
        self.assertEqual([updates.CANAL_URL], chamadas)
        self.assertEqual("1.8.0", disponivel.versao)

    def test_reserva_responde_quando_o_principal_esta_fora(self):
        privada, publica = chave_teste()
        corpo = self._corpo(privada=privada)

        def buscar(url, timeout=updates.TIMEOUT):
            if url == updates.CANAL_URL:
                raise updates.FalhaAtualizacao("canal inacessivel (URLError)")
            return corpo

        with mock.patch.object(updates, "buscar_manifesto", side_effect=buscar):
            disponivel, origem = updates.consultar_com_origem(chave=publica, local="1.7.0")
        self.assertEqual(updates.CANAL_RESERVA, origem)
        self.assertEqual("1.8.0", disponivel.versao)

    def test_reserva_nao_aceita_manifesto_de_outra_chave(self):
        privada, _ = chave_teste()
        _, outra_publica = chave_teste()
        corpo = self._corpo(privada=privada)

        def buscar(url, timeout=updates.TIMEOUT):
            if url == updates.CANAL_URL:
                raise updates.FalhaAtualizacao("canal inacessivel (URLError)")
            return corpo

        with mock.patch.object(updates, "buscar_manifesto", side_effect=buscar):
            with self.assertRaises(updates.FalhaAtualizacao) as erro:
                updates.consultar_com_origem(chave=outra_publica)
        self.assertIn("assinatura do manifesto nao confere", str(erro.exception))

    def test_os_dois_enderecos_fora_do_ar_mostram_as_duas_falhas(self):
        _privada, publica = chave_teste()

        def buscar(url, timeout=updates.TIMEOUT):
            raise updates.FalhaAtualizacao(f"sem resposta em {url}")

        with mock.patch.object(updates, "buscar_manifesto", side_effect=buscar):
            with self.assertRaises(updates.FalhaAtualizacao) as erro:
                updates.consultar_com_origem(chave=publica)
        texto = str(erro.exception)
        self.assertIn("canal e reserva falharam", texto)
        self.assertIn(updates.CANAL_URL, texto)
        self.assertIn(updates.CANAL_RESERVA, texto)

    def test_endereco_unico_nao_cai_para_outro(self):
        _privada, publica = chave_teste()
        chamadas = []

        def buscar(url, timeout=updates.TIMEOUT):
            chamadas.append(url)
            raise updates.FalhaAtualizacao("canal inacessivel (URLError)")

        with mock.patch.object(updates, "buscar_manifesto", side_effect=buscar):
            with self.assertRaises(updates.FalhaAtualizacao):
                updates.consultar_com_origem("https://exemplo.invalido/latest.json", chave=publica)
        self.assertEqual(["https://exemplo.invalido/latest.json"], chamadas)


class AppFalso:
    def __init__(self):
        self.logs = []
        self.avisos = []

    def ui(self, funcao, *args):
        funcao(*args)

    def log_system(self, mensagem):
        self.logs.append(mensagem)

    def mostrar_atualizacao(self, info):
        self.avisos.append(info)


class VigiaTest(unittest.TestCase):
    def _vigia(self, app, publica) -> updates.Vigia:
        vigia = updates.Vigia(
            app, publica, url=(updates.CANAL_URL, updates.CANAL_RESERVA), local="1.7.0"
        )
        self.addCleanup(vigia.parar)
        return vigia

    def _rodar(self, vigia, buscar):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
                with mock.patch.object(updates, "buscar_manifesto", side_effect=buscar):
                    vigia._consultar()

    def test_reserva_aparece_no_log_uma_vez_e_a_volta_tambem(self):
        app = AppFalso()
        privada, publica = chave_teste()
        corpo = json.dumps(envelope(payload_teste("1.8.0"), privada)).encode("utf-8")
        vigia = self._vigia(app, publica)
        estado = {"principal": False}

        def buscar(url, timeout=updates.TIMEOUT):
            if url == updates.CANAL_URL and not estado["principal"]:
                raise updates.FalhaAtualizacao("canal inacessivel (URLError)")
            return corpo

        self._rodar(vigia, buscar)
        self._rodar(vigia, buscar)
        self.assertEqual(
            1,
            sum("endereco de reserva" in linha for linha in app.logs),
            app.logs,
        )
        estado["principal"] = True
        self._rodar(vigia, buscar)
        self.assertIn(
            "Canal de atualizacao: de volta ao endereco principal.", app.logs
        )


def _capturar(funcao, *args) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        funcao(*args)
    return buffer.getvalue()


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.privada, self.publica = chave_teste()
        self.config = gaspar_channel.ler_config()
        self.corpo = json.dumps(
            envelope(payload_teste(), self.privada, key_id=self.config["key_id"])
        ).encode("utf-8")
        self.corpos = {updates.CANAL_RESERVA: self.corpo, updates.CANAL_URL: self.corpo}
        self.tamanhos = {".exe": 123, ".deb": 456}
        patchers = [
            mock.patch.object(updates, "chave_publica", return_value=self.publica),
            mock.patch.object(updates, "buscar_manifesto", side_effect=self._buscar),
            mock.patch.object(
                gaspar_channel,
                "tags_publicadas",
                return_value=[("gaspar-v1.7.1", "1.7.1")],
            ),
            mock.patch.object(gaspar_channel, "_tamanho_remoto", side_effect=self._tamanho),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _buscar(self, url, timeout=updates.TIMEOUT):
        return self.corpos[url]

    def _tamanho(self, url):
        for sufixo, tamanho in self.tamanhos.items():
            if url.endswith(sufixo):
                return tamanho
        return None

    def _rodar(self, tag=None):
        return gaspar_channel.monitor(
            self.config, updates.CANAL_RESERVA, updates.CANAL_URL, tag
        )

    def test_canal_saudavel_passa(self):
        saida = _capturar(self._rodar)
        self.assertIn("versao 1.7.1", saida)
        self.assertIn("mesmos bytes", saida)
        self.assertIn("release mais nova publicada (1.7.1)", saida)
        self.assertIn("pacote linux-deb: no ar (456 bytes)", saida)

    def test_espelho_com_outra_versao_e_recusado(self):
        outro = json.dumps(
            envelope(payload_teste("1.8.0"), self.privada, key_id=self.config["key_id"])
        ).encode("utf-8")
        self.corpos[updates.CANAL_URL] = outro
        with self.assertRaises(gaspar_channel.Falha) as erro:
            self._rodar()
        self.assertIn("espelho publica 1.8.0", str(erro.exception))

    def test_espelho_assinado_por_outra_chave_e_recusado(self):
        intrusa, _ = chave_teste()
        self.corpos[updates.CANAL_URL] = json.dumps(
            envelope(payload_teste(), intrusa, key_id=self.config["key_id"])
        ).encode("utf-8")
        with self.assertRaises(gaspar_channel.Falha) as erro:
            self._rodar()
        self.assertIn("assinatura do manifesto nao confere", str(erro.exception))

    def test_canal_atras_da_release_e_recusado(self):
        with mock.patch.object(
            gaspar_channel,
            "tags_publicadas",
            return_value=[("gaspar-v1.7.1", "1.7.1"), ("gaspar-v1.8.0", "1.8.0")],
        ):
            with self.assertRaises(gaspar_channel.Falha) as erro:
                self._rodar()
        self.assertIn("release mais nova publicada e 1.8.0", str(erro.exception))

    def test_key_id_fora_do_esperado_e_recusado(self):
        self.corpos[updates.CANAL_RESERVA] = json.dumps(
            envelope(payload_teste(), self.privada, key_id="gaspar-2030-01")
        ).encode("utf-8")
        with self.assertRaises(gaspar_channel.Falha) as erro:
            self._rodar()
        self.assertIn("gaspar-2030-01", str(erro.exception))

    def test_pacote_de_tamanho_diferente_e_recusado(self):
        self.tamanhos[".exe"] = 999
        with self.assertRaises(gaspar_channel.Falha) as erro:
            self._rodar()
        self.assertIn("999 bytes no ar, 123 no manifesto", str(erro.exception))

    def test_etiqueta_esperada_dispensa_consulta_da_release(self):
        with mock.patch.object(
            gaspar_channel, "tags_publicadas", side_effect=AssertionError("nao deveria consultar")
        ):
            saida = _capturar(self._rodar, "gaspar-v1.7.1")
        self.assertIn("release mais nova publicada (1.7.1)", saida)


if __name__ == "__main__":
    unittest.main()
