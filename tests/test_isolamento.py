"""Garante que o Gaspar nao alcance as APIs de pagamento e nota do PDV."""

from __future__ import annotations

import unittest
from pathlib import Path

import gaspar
from gaspar.telemetry_hosts import DOMAINS

HOSTS_PROTEGIDOS = (
    "api.mercadopago.com",
    "api.mercadopago.com.br",
    "api.plugnotas.com.br",
    "api.sandbox.plugnotas.com.br",
    "app2.plugnotas.com.br",
    "api.tecnospeed.com.br",
)

#: sairam da lista em 17/11/2026: bloque-los derruba o login da Microsoft e a loja de extensoes
FORA_DA_LISTA = (
    "login.microsoftonline.com",
    "marketplace.visualstudio.com",
    "vscode.dev",
    "management.azure.com",
    "global.azure.microsoft.com",
)


def _alcanca(bloqueado: str, alvo: str) -> bool:
    bloqueado = bloqueado.lower().rstrip(".")
    alvo = alvo.lower().rstrip(".")
    return (
        bloqueado == alvo
        or alvo.endswith("." + bloqueado)
        or bloqueado.endswith("." + alvo)
    )


class IsolamentoTest(unittest.TestCase):
    def test_bloqueio_de_telemetria_nao_alcanca_pagamento_nem_nota(self):
        for bloqueado in DOMAINS:
            for protegido in HOSTS_PROTEGIDOS:
                self.assertFalse(
                    _alcanca(bloqueado, protegido),
                    f"{bloqueado} alcanca {protegido}",
                )

    def test_codigo_do_gaspar_nao_cita_apis_de_pagamento_nem_nota(self):
        raiz = Path(gaspar.__file__).resolve().parent
        for arquivo in raiz.rglob("*.py"):
            texto = arquivo.read_text(encoding="utf-8", errors="replace").lower()
            for protegido in HOSTS_PROTEGIDOS:
                self.assertNotIn(
                    protegido,
                    texto,
                    f"{arquivo.name} cita {protegido}",
                )

    def test_login_marketplace_e_gestao_de_nuvem_fora_da_lista_de_bloqueio(self):
        # Enderecos que o BlackBox passou a evitar de proposito: bloque-los
        # derruba o login da Microsoft e a loja de extensoes do VS Code.
        for fora in FORA_DA_LISTA:
            self.assertNotIn(fora, DOMAINS, f"{fora} voltou para a lista do BlackBox")
        self.assertEqual(
            len(DOMAINS),
            29,
            "a quantidade de dominios esta escrita em manual-tecnico/tecnico.md",
        )


if __name__ == "__main__":
    unittest.main()
