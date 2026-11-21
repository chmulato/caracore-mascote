"""Testes da regra de convivencia pelo celular (Onda B6-A).

O celular pareado pelo Wi-Fi escuta uma unica porta TCP, a 49998, e os dois motores
do Gaspar falam com ela: a ponte de SMS da 1.7 e o motorista ``android_lan`` do 2.0.
A regra, gravada pelo dono do produto em 21/11/2026, e esta:

* motor 2.0 ligado com alguma origem escolhendo ``android_lan`` -> o celular e do
  2.0 e a 1.7 cede a vez, sem tocar na porta;
* motor 2.0 desligado (o padrao de fabrica) -> a 1.7 opera exatamente como hoje.

Estes testes so leem configuracao: nada aqui abre soquete, descobre celular na rede
ou monta motorista. A outra metade da prova - a de que o painel respeita a regra -
esta em ``test_app.py``.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from gaspar.messaging.config import MessagingConfig
from gaspar.messaging.convivencia import (
    NOME_MEIO_CELULAR,
    celular_reservado,
    motivo_celular_reservado,
    origens_com_celular,
)
from gaspar.messaging.transports.android_lan import NOME_MOTORISTA
from gaspar.messaging.transports.loopback import LoopbackTransportDriver
from gaspar.messaging.transports.smtp_email import EmailBridgeDriver


class NomeDoMeioTests(unittest.TestCase):
    def test_a_regra_usa_o_mesmo_nome_que_o_motorista_se_apresenta(self):
        """Se o motorista mudar de nome, a regra muda junto - nao tem literal solto."""
        self.assertEqual(NOME_MOTORISTA, NOME_MEIO_CELULAR)

    def test_o_nome_reservado_nao_confunde_com_os_outros_meios(self):
        self.assertNotIn(NOME_MEIO_CELULAR, (EmailBridgeDriver.name, LoopbackTransportDriver.name))


class ReservaDoCelularTests(unittest.TestCase):
    def config(self, *, enabled=True, **transports):
        return MessagingConfig(enabled=enabled, transports=dict(transports))

    def test_sem_arquivo_lido_nada_esta_reservado(self):
        self.assertFalse(celular_reservado(None))
        self.assertEqual("", motivo_celular_reservado(None))

    def test_motor_desligado_deixa_a_1_7_como_ela_e_hoje(self):
        config = self.config(enabled=False, PDV=NOME_MEIO_CELULAR, HUB=NOME_MEIO_CELULAR)
        self.assertFalse(celular_reservado(config))
        self.assertEqual("", motivo_celular_reservado(config))

    def test_motor_ligado_com_celular_reserva_a_porta(self):
        for origem in ("PDV", "HUB"):
            with self.subTest(origem=origem):
                config = self.config(**{origem: NOME_MEIO_CELULAR})
                self.assertTrue(celular_reservado(config))
                self.assertIn(origem, motivo_celular_reservado(config))
                self.assertIn("49998", motivo_celular_reservado(config))

    def test_as_duas_origens_aparecem_na_frase_de_aviso(self):
        motivo = motivo_celular_reservado(
            self.config(PDV=NOME_MEIO_CELULAR, HUB=NOME_MEIO_CELULAR)
        )
        self.assertEqual(("PDV", "HUB"), tuple(o for o in ("PDV", "HUB") if o in motivo))

    def test_meio_que_nao_e_celular_nao_tira_a_porta_da_1_7(self):
        for nome in (EmailBridgeDriver.name, LoopbackTransportDriver.name, "usb_modem", ""):
            with self.subTest(nome=nome):
                self.assertFalse(celular_reservado(self.config(PDV=nome, HUB=nome)))

    def test_bloco_de_ajustes_por_si_so_nao_reserva_nada(self):
        """Existe um bloco android_lan no arquivo, mas nenhuma origem o escolheu."""
        config = MessagingConfig(
            enabled=True,
            transports={"PDV": EmailBridgeDriver.name},
            transport_settings={NOME_MEIO_CELULAR: {"ligada": True}},
        )
        self.assertFalse(celular_reservado(config))

    def test_a_escolha_com_grafia_diferente_nao_reserva(self):
        """Nome torto nao liga motorista nenhum, entao o celular segue com a 1.7."""
        config = MessagingConfig(enabled=True, transports={"PDV": NOME_MEIO_CELULAR.upper()})
        self.assertEqual((), origens_com_celular(config))
        self.assertFalse(celular_reservado(config))

    def test_arquivo_torto_nao_quebra_a_consulta(self):
        for config in (
            SimpleNamespace(enabled=True, transports="PDV=android_lan"),
            SimpleNamespace(enabled=True, transports=None),
            SimpleNamespace(enabled=True),
            SimpleNamespace(transports={"PDV": NOME_MEIO_CELULAR}),
            SimpleNamespace(),
        ):
            with self.subTest(config=config):
                self.assertFalse(celular_reservado(config))
                self.assertEqual("", motivo_celular_reservado(config))

    def test_origens_com_celular_nao_depende_do_motor_estar_ligado(self):
        """A consulta das origens e so de escolha; quem pesa o ligado e celular_reservado."""
        ligado = self.config(PDV=NOME_MEIO_CELULAR, HUB=EmailBridgeDriver.name)
        self.assertEqual(("PDV",), origens_com_celular(ligado))
        self.assertEqual((), origens_com_celular(SimpleNamespace(transports="torto")))
        self.assertEqual((), origens_com_celular(SimpleNamespace()))

    def test_a_consulta_nao_escreve_nem_mexe_em_nada(self):
        config = self.config(PDV=NOME_MEIO_CELULAR)
        antes = (config.enabled, dict(config.transports), dict(config.transport_settings))
        motivo_celular_reservado(config)
        self.assertEqual(antes, (config.enabled, dict(config.transports), dict(config.transport_settings)))
