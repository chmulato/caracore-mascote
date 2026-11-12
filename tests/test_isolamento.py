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


if __name__ == "__main__":
    unittest.main()
