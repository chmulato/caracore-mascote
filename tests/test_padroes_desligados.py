"""Trava os padroes desligados por privacidade e seguranca do Gaspar.

Cada assercao aqui e uma decisao de produto, nao um espelho do codigo: o
aplicativo nao movimenta o mouse, nao tecla, nao abre porta e nao bloqueia
login por conta propria. Os mesmos valores aparecem em README.md,
docs/index.html e manual-tecnico/tecnico.md; quem mudar um deles muda os
tres. Nenhum teste deste arquivo abre janela, toca rede ou escreve fora da
pasta temporaria.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gaspar.config import Settings, load_settings
from gaspar.messaging.config import MessagingConfig
from gaspar.messaging.config import load_config as carregar_barra
from gaspar.sms.config import SmsConfig
from gaspar.sms.config import load_config as carregar_ponte_1x


class PresencaDoPainelTest(unittest.TestCase):
    def test_o_painel_nasce_sem_mouse_tecla_teams_e_autostart(self):
        padrao = Settings()
        self.assertFalse(padrao.simulate_mouse)
        self.assertEqual(padrao.press_key, "none")
        self.assertFalse(padrao.keep_teams)
        self.assertFalse(padrao.auto_start)
        self.assertFalse(padrao.system_telemetry)
        self.assertFalse(padrao.sound)

    def test_o_respeito_a_quem_esta_trabalhando_nasce_ligado(self):
        padrao = Settings()
        self.assertTrue(padrao.only_when_idle)
        self.assertTrue(padrao.pause_fullscreen)
        self.assertEqual(padrao.idle_seconds, 60)

    def test_arquivo_que_nao_cita_os_acionamentos_nao_liga_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(
                json.dumps({"interval": 60, "opacity": 90, "logging": False}),
                encoding="utf-8",
            )
            settings = load_settings(target)
            self.assertEqual(settings.interval, 60)
            self.assertEqual(settings.opacity, 90)
            self.assertFalse(settings.simulate_mouse)
            self.assertEqual(settings.press_key, "none")
            self.assertFalse(settings.keep_teams)
            self.assertFalse(settings.auto_start)

    def test_escolha_ja_gravada_nao_apaga_por_conta_propria(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(
                json.dumps({"simulate_mouse": True, "press_key": "f15"}),
                encoding="utf-8",
            )
            quem_escolheu = load_settings(target)
            self.assertTrue(quem_escolheu.simulate_mouse)
            self.assertEqual(quem_escolheu.press_key, "f15")

    def test_tecla_fora_da_lista_para_em_nenhuma(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(json.dumps({"press_key": "caps-lock"}), encoding="utf-8")
            self.assertEqual(load_settings(target).press_key, "none")


class PonteSms1xTest(unittest.TestCase):
    def test_a_porta_do_celular_nasce_fechada(self):
        self.assertFalse(SmsConfig().enabled)
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "sms_config.json"
            alvo.write_text(json.dumps({"max_per_day": 10}), encoding="utf-8")
            self.assertFalse(carregar_ponte_1x(alvo).enabled)

    def test_ponte_que_o_cliente_ligou_fica_ligada_ao_reler(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "sms_config.json"
            alvo.write_text(json.dumps({"enabled": True}), encoding="utf-8")
            self.assertTrue(carregar_ponte_1x(alvo).enabled)

    def test_texto_que_negue_o_ligamento_nao_abre_a_ponte(self):
        for cru in ("false", "0", "nao", "off", ""):
            with tempfile.TemporaryDirectory() as tmp:
                alvo = Path(tmp) / "sms_config.json"
                alvo.write_text(json.dumps({"enabled": cru}), encoding="utf-8")
                self.assertFalse(carregar_ponte_1x(alvo).enabled, cru)

    def test_texto_que_o_gaspar_nao_entende_deixa_o_padrao(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "sms_config.json"
            alvo.write_text(
                json.dumps({"enabled": "x", "require_signed_requests": "talvez"}),
                encoding="utf-8",
            )
            config = carregar_ponte_1x(alvo)
            self.assertFalse(config.enabled)
            self.assertTrue(config.require_signed_requests)

    def test_cliente_que_escreveu_sim_na_ponte_fica_atendido(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "sms_config.json"
            alvo.write_text(json.dumps({"enabled": "sim"}), encoding="utf-8")
            self.assertTrue(carregar_ponte_1x(alvo).enabled)

    def test_os_limites_prometidos_na_loja_valem_por_padrao(self):
        padrao = SmsConfig()
        self.assertTrue(padrao.require_signed_requests)
        self.assertTrue(padrao.only_templates)
        self.assertEqual(padrao.per_number_per_hour, 1)
        self.assertEqual(padrao.per_number_per_day, 3)


class BarraMensagens20Test(unittest.TestCase):
    def test_a_barra_nasce_desligada_e_sem_meio_escolhido(self):
        padrao = MessagingConfig()
        self.assertFalse(padrao.enabled)
        self.assertEqual(padrao.transports, {})
        self.assertTrue(padrao.require_signed_requests)
        self.assertEqual(padrao.host, "127.0.0.1")

    def test_texto_que_negue_o_ligamento_nao_abre_a_barra(self):
        for cru in ("false", "0", "nao", "off", "", "x"):
            self.assertFalse(MessagingConfig(enabled=cru).enabled, cru)
        self.assertTrue(MessagingConfig(enabled="sim").enabled)

    def test_endereco_fora_do_computador_cai_para_o_padrao(self):
        self.assertEqual(MessagingConfig(host="0.0.0.0").host, "127.0.0.1")
        self.assertEqual(MessagingConfig(host="10.0.0.5").host, "127.0.0.1")

    def test_arquivo_que_nao_escolhe_meio_deixa_a_barra_desligada(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "messaging.json"
            alvo.write_text(
                json.dumps({"daily_limit_per_origin": 5, "transports": {}}),
                encoding="utf-8",
            )
            config = carregar_barra(alvo)
            self.assertFalse(config.enabled)
            self.assertEqual(config.transports, {})

    def test_escolha_explicita_do_operador_prevalece_sobre_o_padrao(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "messaging.json"
            alvo.write_text(
                json.dumps({"enabled": True, "transports": {"PDV": "smtp_email"}}),
                encoding="utf-8",
            )
            escolha = carregar_barra(alvo)
            self.assertTrue(escolha.enabled)
            self.assertEqual(escolha.transports["PDV"], "smtp_email")


if __name__ == "__main__":
    unittest.main()
