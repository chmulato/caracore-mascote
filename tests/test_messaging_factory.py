"""Testes da fabrica de motoristas e dos ajustes que moram no ``messaging.json``.

A Onda B6-A e a primeira vez em que o produto monta um motorista a partir do
arquivo: antes, so os testes construiam ``EmailBridgeDriver`` e
``AndroidLanTransportDriver``. Nada aqui abre conexao com caixa postal, celular ou
porta serie - o que se prova e que o nome escolhido vira objeto, que segredo so
entra no arquivo selado e que o que da errado fica com um motivo dito no log.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gaspar.messaging.config import MessagingConfig, load_config
from gaspar.messaging.model import STATUS_ENVIADO
from gaspar.messaging.transports import TransportRegistry
from gaspar.messaging.transports.android_lan import NOME_MOTORISTA as NOME_ANDROID_LAN
from gaspar.messaging.transports.android_lan import AndroidLanTransportDriver, LanSettings
from gaspar.messaging.transports.factory import (
    ARQUIVO_ESTADO_EMAIL,
    MotoristaNaoMontavel,
    construir,
    montar_registry,
    nomes_disponiveis,
)
from gaspar.messaging.transports.loopback import LoopbackTransportDriver
from gaspar.messaging.transports.smtp_email import EmailBridgeDriver
from gaspar.messaging.service import MessagingService
from gaspar.messaging.vault import Vault

#: o nome com que cada meio aparece no messaging.json
NOME_EMAIL = EmailBridgeDriver.name

SEGREDO = "segredo-do-pareamento-que-nao-pode-sair-do-envelope"
CHAVE_HUB = "segredo-proprio-do-hub-32-bytes"
SENCA = "senha-de-app-da-caixa-da-loja"
NUMERO = "11988887777"
CONTEUDO = "Seu pedido 771 ficou pronto."


class BaseComCofre(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.home = Path(casa.name)
        self.vault = Vault.load_or_create(self.home / "chave-da-fila.key")

    def selar(self, texto: str) -> str:
        return self.vault.seal(texto)

    def outro_cofre(self) -> Vault:
        return Vault.load_or_create(self.home / "chave-de-outra-maquina.key")


class FabricaDeMotoristasTests(BaseComCofre):
    def test_cada_nome_da_casa_monta_o_motorista_correspondente(self):
        montados = {
            NOME_EMAIL: construir(NOME_EMAIL, {}, vault=self.vault, home=self.home),
            NOME_ANDROID_LAN: construir(NOME_ANDROID_LAN, {}, vault=self.vault, home=self.home),
            "loopback": construir("loopback", {}, vault=self.vault, home=self.home),
        }
        self.assertEqual(
            (EmailBridgeDriver, AndroidLanTransportDriver, LoopbackTransportDriver),
            tuple(type(montados[nome]) for nome in (NOME_EMAIL, NOME_ANDROID_LAN, "loopback")),
        )
        self.assertEqual(sorted(montados), sorted(nomes_disponiveis()))

    def test_sem_bloco_de_ajustes_o_motorista_real_sobe_desligado(self):
        """Escolher o meio nao e ligar nada: quem liga e o ajuste dentro do bloco."""
        for nome in (NOME_EMAIL, NOME_ANDROID_LAN):
            with self.subTest(nome=nome):
                driver = construir(nome, None, vault=self.vault, home=self.home)
                health = driver.health()
                self.assertFalse(health.available, driver.describe())
                self.assertTrue(health.reason)

    def test_o_meio_de_bancada_nao_precisa_de_bloco(self):
        """loopback existe para provar a fila sem meio fisico: nasce disponivel."""
        driver = construir("loopback", None, vault=self.vault, home=self.home)
        self.assertTrue(driver.health().available)
        self.assertEqual("loopback-0", driver.device_id)

    def test_bloco_torto_nao_derruba_a_fabrica(self):
        for corpo in (None, [], "texto", 7, {"desconhecido": {"aninhado": [1, 2]}}):
            with self.subTest(corpo=repr(corpo)):
                self.assertIsNotNone(construir("loopback", corpo, vault=self.vault, home=self.home))

    def test_meio_sem_codigo_tem_motivo_especifico(self):
        with self.assertRaises(MotoristaNaoMontavel) as erro:
            construir("usb_modem", {}, vault=self.vault, home=self.home)
        self.assertIn("ainda nao foi escrito", str(erro.exception))

    def test_nome_inventado_recusa_e_diz_o_que_existe(self):
        with self.assertRaises(MotoristaNaoMontavel) as erro:
            construir("bluetooth-fax", {}, vault=self.vault, home=self.home)
        motivo = str(erro.exception)
        self.assertIn("meio desconhecido", motivo)
        for nome in nomes_disponiveis():
            self.assertIn(nome, motivo)

    def test_nome_vazio_recusa_em_vez_de_montar_qualquer_coisa(self):
        with self.assertRaises(MotoristaNaoMontavel):
            construir("   ", {}, vault=self.vault, home=self.home)


class SegredoSeladoTests(BaseComCofre):
    def test_segredo_de_pareamento_selado_abre_so_em_memoria(self):
        bloco = {
            "ligada": True,
            "host": "192.168.0.40",
            "segredo_sealed": self.selar(SEGREDO),
            "segredos_por_origem_sealed": {"HUB": self.selar(CHAVE_HUB)},
        }
        driver = construir(NOME_ANDROID_LAN, bloco, vault=self.vault, home=self.home)
        self.assertEqual(SEGREDO, driver.settings.segredo)
        self.assertEqual({"HUB": CHAVE_HUB}, driver.settings.segredos_por_origem)
        self.assertEqual(SEGREDO, driver.settings.segredo_para("PDV"))
        self.assertEqual(CHAVE_HUB, driver.settings.segredo_para("HUB"))

    def test_o_segredo_aparece_como_presenca_nunca_como_texto(self):
        bloco = {"ligada": True, "segredo_sealed": self.selar(SEGREDO)}
        driver = construir(NOME_ANDROID_LAN, bloco, vault=self.vault, home=self.home)
        vitrine = json.dumps(driver.describe(), ensure_ascii=False)
        self.assertTrue(vitrine)
        self.assertNotIn(SEGREDO, vitrine)
        self.assertNotIn(bloco["segredo_sealed"], vitrine)

    def test_segredo_em_claro_no_arquivo_e_recusado_e_nao_ecoado(self):
        for nome, campo, valor in (
            (NOME_ANDROID_LAN, "segredo", SEGREDO),
            (NOME_ANDROID_LAN, "segredos_por_origem", {"PDV": SEGREDO}),
            (NOME_EMAIL, "password", SENCA),
            (NOME_EMAIL, "bridge_key", "chave-da-ponte-em-claro"),
        ):
            with self.subTest(nome=nome, campo=campo):
                with self.assertRaises(MotoristaNaoMontavel) as erro:
                    construir(nome, {campo: valor}, vault=self.vault, home=self.home)
                motivo = str(erro.exception)
                self.assertIn(campo, motivo)
                self.assertIn(f"{campo}_sealed", motivo)
                texto = valor if isinstance(valor, str) else SEGREDO
                self.assertNotIn(texto, motivo)

    def test_selo_de_outra_maquina_recusa_sem_estourar_a_barra(self):
        blob = self.outro_cofre().seal(SEGREDO)
        with self.assertRaises(MotoristaNaoMontavel) as erro:
            construir(NOME_ANDROID_LAN, {"ligada": True, "segredo_sealed": blob}, vault=self.vault)
        self.assertIn("nao abriu com a chave desta maquina", str(erro.exception))
        self.assertNotIn(SEGREDO, str(erro.exception))
        self.assertNotIn(blob, str(erro.exception))

    def test_campo_selado_sem_cofre_e_recusado(self):
        with self.assertRaises(MotoristaNaoMontavel) as erro:
            construir(
                NOME_ANDROID_LAN,
                {"ligada": True, "segredo_sealed": self.selar(SEGREDO)},
                vault=None,
            )
        self.assertIn("cofre da fila", str(erro.exception))

    def test_o_arquivo_grava_o_selo_e_nunca_o_texto_aberto(self):
        config = MessagingConfig(
            enabled=True,
            transports={"PDV": NOME_ANDROID_LAN},
            transport_settings={NOME_ANDROID_LAN: {"ligada": True, "segredo_sealed": self.selar(SEGREDO)}},
            source=str(self.home / "messaging.json"),
        )
        caminho = config.save()
        conteudo = Path(caminho).read_text(encoding="utf-8")
        self.assertNotIn(SEGREDO, conteudo)
        self.assertIn("segredo_sealed", conteudo)
        relido = load_config(caminho)
        driver = construir(NOME_ANDROID_LAN, relido.settings_for(NOME_ANDROID_LAN), vault=self.vault)
        self.assertEqual(SEGREDO, driver.settings.segredo)


class EstadoDaPonteDeEmailTests(BaseComCofre):
    def test_sem_caminho_dito_o_estado_vai_para_a_pasta_de_dados(self):
        driver = construir(NOME_EMAIL, {"enabled": True}, vault=self.vault, home=self.home)
        self.assertEqual(self.home / ARQUIVO_ESTADO_EMAIL, Path(driver.settings.state_path))
        self.assertEqual(self.home / ARQUIVO_ESTADO_EMAIL, Path(driver.estado.path))

    def test_caminho_dito_no_arquivo_e_respeitado(self):
        alvo = self.home / "outra-pasta" / "ponte.state"
        driver = construir(
            NOME_EMAIL,
            {"enabled": True, "state_path": str(alvo)},
            vault=self.vault,
            home=self.home,
        )
        self.assertEqual(alvo, Path(driver.settings.state_path))

    def test_sem_pasta_de_dados_nenhum_caminho_e_inventado(self):
        driver = construir(NOME_EMAIL, {"enabled": True}, vault=self.vault, home=None)
        self.assertEqual("", driver.settings.state_path)
        self.assertIsNone(driver.estado.path)

    def test_montar_a_ponte_nao_escreve_nem_abre_conexao(self):
        antes = sorted(p.name for p in self.home.iterdir())
        construir(NOME_EMAIL, {"enabled": True}, vault=self.vault, home=self.home)
        self.assertEqual(antes, sorted(p.name for p in self.home.iterdir()))


class AjustesPorMotoristaNoArquivoTests(BaseComCofre):
    def test_escolha_por_origem_e_ajustes_por_motorista_sobrevivem_ao_arquivo(self):
        config = MessagingConfig(
            enabled=True,
            transports={"PDV": NOME_ANDROID_LAN, "HUB": NOME_EMAIL},
            transport_settings={
                NOME_ANDROID_LAN: {"ligada": True, "host": "192.168.0.40"},
                NOME_EMAIL: {"enabled": True, "user": "loja@caracore.com.br"},
            },
            source=str(self.home / "messaging.json"),
        )
        caminho = config.save()
        relido = load_config(caminho)
        self.assertEqual(NOME_ANDROID_LAN, relido.transport_for("PDV"))
        self.assertEqual(NOME_EMAIL, relido.transport_for("HUB"))
        self.assertEqual("192.168.0.40", relido.settings_for(NOME_ANDROID_LAN)["host"])
        self.assertEqual("loja@caracore.com.br", relido.settings_for(NOME_EMAIL)["user"])
        self.assertEqual((NOME_ANDROID_LAN, NOME_EMAIL), relido.meios_citados)

    def test_duas_origens_no_mesmo_motorista_compartilham_uma_soa_caixa(self):
        """Um bloco por nome e o desenho que impede dois cursores sobre a mesma caixa.

        Se os ajustes fossem por origem, PDV e Hub na mesma caixa postal teriam dois
        motores lendo a mesma fila de recados - cada um consumiria os do vizinho.
        """
        config = MessagingConfig(
            enabled=True,
            transports={"PDV": NOME_EMAIL, "HUB": NOME_EMAIL},
            transport_settings={NOME_EMAIL: {"enabled": True, "user": "loja@caracore.com.br"}},
        )
        registry = TransportRegistry()
        self.assertEqual([NOME_EMAIL], montar_registry(registry, config, vault=self.vault, home=self.home))
        registry.bind("PDV", NOME_EMAIL)
        registry.bind("HUB", NOME_EMAIL)
        self.assertIs(registry.driver_for("PDV"), registry.driver_for("HUB"))
        self.assertIs(registry.driver_for("PDV").estado, registry.driver_for("HUB").estado)

    def test_bloco_fora_de_objeto_e_descartado_na_leitura(self):
        config = MessagingConfig(
            transport_settings={
                NOME_EMAIL: "texto em vez de bloco",
                "": {"enabled": True},
                NOME_ANDROID_LAN: {"ligada": True},
            }
        )
        self.assertEqual([NOME_ANDROID_LAN], list(config.transport_settings))
        self.assertEqual({}, config.settings_for(NOME_EMAIL))

    def test_set_settings_sem_conteudo_remove_o_bloco(self):
        config = MessagingConfig(transport_settings={NOME_EMAIL: {"enabled": True}})
        config.set_settings(NOME_EMAIL, {})
        self.assertEqual({}, config.transport_settings)
        config.set_settings("", {"enabled": True})
        self.assertEqual({}, config.transport_settings)

    def test_ajustes_sao_copiados_para_fora_do_objeto_gravado(self):
        bloco = {"enabled": True}
        config = MessagingConfig(transport_settings={NOME_EMAIL: bloco})
        config.settings_for(NOME_EMAIL)["user"] = "quem mexeu no espelho"
        bloco["smtp_port"] = 2525
        self.assertEqual({"enabled": True}, config.transport_settings[NOME_EMAIL])

    def test_o_arquivo_nao_grava_o_que_nao_tem_bloco(self):
        corpo = json.loads(MessagingConfig(enabled=True, transports={"PDV": "loopback"}).save(
            self.home / "messaging.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual({}, corpo["transport_settings"])


class LanSettingsDoArquivoTests(unittest.TestCase):
    def test_from_dict_le_so_os_campos_conhecidos(self):
        settings = LanSettings.from_dict(
            {"ligada": True, "host": "10.0.0.5", "porta": "49998", "segredo_sealed": "nao e campo"}
        )
        self.assertTrue(settings.ligada)
        self.assertEqual("10.0.0.5", settings.host)
        self.assertEqual(49998, settings.porta)
        self.assertFalse(hasattr(settings, "segredo_sealed"))

    def test_from_dict_tolera_arquivo_sem_nada(self):
        for dados in (None, [], "texto", {}):
            with self.subTest(dados=repr(dados)):
                vazio = LanSettings.from_dict(dados)
                self.assertFalse(vazio.ligada)
                self.assertFalse(vazio.tem_pareamento())


class ServicoMontaOsMeiosTests(BaseComCofre):
    def service(self, config, **kwargs):
        kwargs.setdefault("on_log", lambda _texto: None)
        return MessagingService(config, home=self.home, **kwargs)

    def test_motor_desligado_nao_monta_nem_escreve_estado(self):
        config = MessagingConfig(
            enabled=False,
            transports={"PDV": NOME_EMAIL},
            transport_settings={NOME_EMAIL: {"enabled": True}},
        )
        service = self.service(config)
        self.addCleanup(service.close)
        self.assertEqual([], service.registry.names())
        self.assertFalse((self.home / ARQUIVO_ESTADO_EMAIL).exists())
        self.assertFalse(service.start(start_round=False, open_port=False))

    def test_motor_ligado_monta_o_que_as_origens_escolheram(self):
        logs: list[str] = []
        config = MessagingConfig(
            enabled=True,
            transports={"PDV": "loopback", "HUB": NOME_ANDROID_LAN},
            transport_settings={NOME_ANDROID_LAN: {"ligada": True, "host": "192.168.0.40"}},
        )
        service = self.service(config, on_log=logs.append)
        self.addCleanup(service.close)
        self.assertTrue(service.start(start_round=False, open_port=False))
        self.assertEqual(sorted(["loopback", NOME_ANDROID_LAN]), service.registry.names())
        self.assertEqual({"PDV": "loopback", "HUB": NOME_ANDROID_LAN}, service.registry.bindings())
        meios = service.status()["meios"]
        self.assertTrue(meios["PDV"]["disponivel"])
        self.assertFalse(meios["HUB"]["disponivel"])
        self.assertIn("segredo de pareamento", meios["HUB"]["motivo"])

    def test_pedido_do_pdv_sai_pelo_motorista_escolhido_no_arquivo(self):
        config = MessagingConfig(enabled=True, transports={"PDV": "loopback"})
        service = self.service(config)
        self.addCleanup(service.close)
        service.start(start_round=False, open_port=False)
        message, _ = service.store.enqueue(
            origem="PDV", external_id="venda-9", recipient=NUMERO, text=CONTEUDO
        )
        self.assertEqual(1, service.dispatcher.run_once())
        motorista = service.registry.driver_for("PDV")
        self.assertEqual([message.id], [ped.id for ped in motorista.submitted])
        self.assertEqual(STATUS_ENVIADO, service.store.get("PDV", message.id).status)

    def test_um_bloco_recusado_nao_tira_a_origem_vizinha_do_ar(self):
        logs: list[str] = []
        config = MessagingConfig(
            enabled=True,
            transports={"PDV": "loopback", "HUB": NOME_ANDROID_LAN},
            transport_settings={NOME_ANDROID_LAN: {"ligada": True, "segredo": SEGREDO}},
        )
        service = self.service(config, on_log=logs.append)
        self.addCleanup(service.close)
        self.assertTrue(service.start(start_round=False, open_port=False))
        self.assertEqual(["loopback"], service.registry.names())
        self.assertIsNotNone(service.registry.driver_for("PDV"))
        self.assertIsNone(service.registry.driver_for("HUB"))
        self.assertTrue(any("nao montado" in texto and "em claro" in texto for texto in logs))
        self.assertNotIn(SEGREDO, " | ".join(logs))

    def test_registro_injetado_manda_sozinho(self):
        """Quem injeta o registro (testes e integradores) nao leva motorista extra."""
        registry = TransportRegistry()
        registry.register(LoopbackTransportDriver())
        config = MessagingConfig(enabled=True, transports={"PDV": NOME_EMAIL})
        service = self.service(config, registry=registry)
        self.addCleanup(service.close)
        self.assertTrue(service.start(start_round=False, open_port=False))
        self.assertEqual(["loopback"], service.registry.names())
        self.assertFalse((self.home / ARQUIVO_ESTADO_EMAIL).exists())
