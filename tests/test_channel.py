"""Testes da rotina de release do canal (sem rede externa e sem chave real)."""

from __future__ import annotations

import base64
import json
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gaspar import updates
from tools import gaspar_channel as canal

CONFIG = {"key_id": "gaspar-teste", "tag_prefix": "gaspar-v"}


def chave_teste():
    privada = Ed25519PrivateKey.generate()
    return privada, privada.public_key()


def payload_teste(versao: str = "1.8.0", **campos) -> dict:
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
                "url": (
                    "https://github.com/chmulato/caracore-mascote/releases/download/"
                    f"gaspar-v{versao}/GasparSetup-{versao}.exe"
                ),
                "sha256": "a" * 64,
                "size": 123,
            },
            "linux-deb": {
                "url": (
                    "https://github.com/chmulato/caracore-mascote/releases/download/"
                    f"gaspar-v{versao}/gaspar_{versao}_amd64.deb"
                ),
                "sha256": "b" * 64,
                "size": 456,
            },
        },
    }
    dados.update(campos)
    return dados


def envelope(payload: dict, privada) -> bytes:
    return canal.assinar(payload, CONFIG, privada)


class ProvaTest(unittest.TestCase):
    def test_aceita_release_oficial_e_espelho_iguais(self):
        privada, publica = chave_teste()
        payload = payload_teste()
        corpo = envelope(payload, privada)
        linhas = canal.conferir_prova(
            "1.8.0", payload, CONFIG, corpo, corpo, ["1.6.0", "1.7.0"], publica
        )
        texto = "\n".join(linhas)
        self.assertIn("canal oficial: 1.8.0", texto)
        self.assertIn("espelho no gateway: mesmos bytes", texto)
        self.assertIn("1.6.0: aviso da 1.8.0 obrigatorio", texto)
        self.assertIn("1.7.0: aviso da 1.8.0 opcional", texto)
        self.assertIn("versao atual 1.8.0: sem aviso", texto)
        self.assertIn("adulterado", texto)

    def test_espelho_com_bytes_diferentes_e_recusado(self):
        privada, publica = chave_teste()
        payload = payload_teste()
        corpo = envelope(payload, privada)
        outro = envelope(payload_teste(releaseNotes="Outro texto."), privada)
        with self.assertRaises(canal.Falha) as erro:
            canal.conferir_prova(
                "1.8.0", payload, CONFIG, corpo, outro, ["1.6.0"], publica
            )
        self.assertIn("mesmos bytes", str(erro.exception))

    def test_manifesto_de_outra_release_e_recusado(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(), privada)
        esperado = payload_teste(assets={"windows-setup": {"url": "u", "sha256": "c" * 64}})
        with self.assertRaises(canal.Falha) as erro:
            canal.conferir_prova(
                "1.8.0", esperado, CONFIG, corpo, corpo, ["1.6.0"], publica
            )
        self.assertIn("nao corresponde a release", str(erro.exception))
        self.assertIn("assets", str(erro.exception))

    def test_canal_atrasado_pede_espera(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste("1.7.2"), privada)
        with self.assertRaises(canal.VersaoAtrasada):
            canal.conferir_prova(
                "1.8.0", payload_teste(), CONFIG, corpo, corpo, ["1.6.0"], publica
            )

    def test_key_id_divergente_e_recusado(self):
        privada, publica = chave_teste()
        payload = payload_teste()
        corpo = envelope(payload, privada)
        with self.assertRaises(canal.Falha) as erro:
            canal.conferir_prova(
                "1.8.0", payload, {"key_id": "outra-chave"}, corpo, corpo, ["1.6.0"], publica
            )
        self.assertIn("key_id", str(erro.exception))

    def test_adulteracao_da_versao_e_recusada(self):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(), privada)
        canal.conferir_adulteracao(corpo, publica)
        envelope_adulterado = json.loads(corpo)
        payload = json.loads(base64.b64decode(envelope_adulterado["payload"]))
        payload["version"] = "9.9.9"
        envelope_adulterado["payload"] = base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        with self.assertRaises(updates.FalhaAtualizacao):
            updates.verificar_envelope(json.dumps(envelope_adulterado).encode("utf-8"), publica)


class ReferenciasTest(unittest.TestCase):
    def _manifesto(self, **campos):
        privada, publica = chave_teste()
        corpo = envelope(payload_teste(**campos), privada)
        return updates.verificar_envelope(corpo, publica)

    def test_abaixo_do_minimo_e_obrigatoria(self):
        linhas = canal.conferir_referencias(self._manifesto(), ["1.6.0", "1.7.0"])
        self.assertIn("1.6.0: aviso da 1.8.0 obrigatorio", linhas[0])
        self.assertIn("1.7.0: aviso da 1.8.0 opcional", linhas[1])

    def test_corpo_marcado_obrigatorio_vale_para_todos(self):
        manifesto = self._manifesto(mandatory=True)
        linhas = canal.conferir_referencias(manifesto, ["1.6.0", "1.7.0"])
        self.assertTrue(all("obrigatorio" in linha for linha in linhas))

    def test_sem_versao_anterior_a_regra_nao_e_provada(self):
        with self.assertRaises(canal.Falha):
            canal.conferir_referencias(self._manifesto(), [])


class TagsTest(unittest.TestCase):
    def test_aceita_etiqueta_do_gaspar_e_a_antiga(self):
        self.assertEqual(canal.versao_da_tag("gaspar-v1.7.1"), "1.7.1")
        self.assertEqual(canal.versao_da_tag("v1.6.0"), "1.6.0")

    def test_recusa_etiqueta_de_outro_app(self):
        self.assertIsNone(canal.versao_da_tag("android-v1.3"))

    def test_escolhe_a_mais_nova_sem_confiar_na_ordem(self):
        escolhida = canal._mais_nova([("gaspar-v1.7.1", "1.7.1"), ("gaspar-v1.10.0", "1.10.0")])
        self.assertEqual(escolhida, ("gaspar-v1.10.0", "1.10.0"))


if __name__ == "__main__":
    unittest.main()
