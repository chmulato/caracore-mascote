"""Testes da fila isolada por origem: nada de cliente em claro e nada de tralha do vizinho.

Sem rede, sem celular e sem dados reais: tudo acontece numa pasta temporaria.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from gaspar.messaging.errors import InvalidRequest, QueueFull, StorageError, UnknownMessage
from gaspar.messaging.model import (
    STATUS_ENTREGUE,
    STATUS_ENVIADO,
    STATUS_ENVIANDO,
    STATUS_FALHOU,
    STATUS_FILA,
    STATUS_INCERTO,
)
from gaspar.messaging.store import DOMAIN_RECIPIENT, MessageStore
from gaspar.messaging.transport import InboundReply
from gaspar.messaging.vault import Vault

NUMERO = "11988887777"
CONTEUDO = "COPIA-UNICA-DO-CONTEUDO-DA-MENSAGEM"


class MessagingStoreTestCase(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.base = Path(casa.name)
        self.vault = Vault.load_or_create(self.base / "messaging-vault.key")
        self.store = self.open_store()
        self.addCleanup(lambda: self.store.close())

    def open_store(self, **kwargs) -> MessageStore:
        options = {"max_pending": 5}
        options.update(kwargs)
        return MessageStore(self.base / "messaging.db", self.vault, **options)

    def guardar(self, origem="PDV", externo="venda-1", numero=NUMERO, texto=CONTEUDO, chave=""):
        return self.store.enqueue(
            origem=origem, external_id=externo, recipient=numero, text=texto, idempotency_key=chave
        )

    # ------------------------------------------------------------------ guardar

    def test_guarda_e_recupera_o_pedido(self):
        message, created = self.guardar(chave="chave-1")
        self.assertTrue(created)
        loaded = self.store.get("PDV", message.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.recipient, NUMERO)
        self.assertEqual(loaded.text, CONTEUDO)
        self.assertEqual(loaded.status, STATUS_FILA)
        self.assertEqual(loaded.origem, "PDV")

    def test_resposta_publica_nao_mostra_numero_completo_nem_texto(self):
        message, _ = self.guardar()
        data = message.to_public_dict()
        self.assertNotIn("mensagem", data)
        self.assertNotIn(NUMERO, data["destino"])
        self.assertTrue(data["destino"].endswith("7777"))
        self.assertEqual(data["id_externo"], "venda-1")

    def test_arquivo_da_fila_nao_guarda_dado_de_cliente_em_claro(self):
        self.guardar()
        disco = b""
        for arquivo in sorted(self.base.glob("messaging.db*")):
            disco += arquivo.read_bytes()
        self.assertNotIn(NUMERO.encode(), disco)
        self.assertNotIn(CONTEUDO.encode(), disco)

    def test_repetir_a_mesma_chave_nao_duplica_o_pedido(self):
        first, created_first = self.guardar(chave="mesma")
        second, created_second = self.guardar(chave="mesma")
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.store.counts("PDV")[STATUS_FILA], 1)

    def test_duas_notificacoes_do_mesmo_objeto_de_negocio_sao_permitidas(self):
        uma, _ = self.guardar(externo="pedido-9", chave="a")
        outra, _ = self.guardar(externo="pedido-9", chave="b")
        self.assertNotEqual(uma.id, outra.id)
        encontrado = self.store.get_by_external("PDV", "pedido-9")
        self.assertIn(encontrado.id, {uma.id, outra.id})

    def test_chave_de_repeticao_vazia_gera_identificador_novo(self):
        uma, _ = self.guardar(chave="")
        outra, _ = self.guardar(chave="")
        self.assertNotEqual(uma.id, outra.id)

    def test_pedido_invalido_recusado_antes_de_entrar_na_fila(self):
        with self.assertRaises(InvalidRequest):
            self.store.enqueue(origem="LOJA", external_id="x", recipient=NUMERO, text="oi")
        with self.assertRaises(InvalidRequest):
            self.guardar(numero="123")
        with self.assertRaises(InvalidRequest):
            self.guardar(texto="")
        with self.assertRaises(InvalidRequest):
            self.guardar(externo="")
        self.assertEqual(self.store.counts("PDV")[STATUS_FILA], 0)

    def test_texto_longo_demais_recusado(self):
        with self.assertRaises(InvalidRequest):
            self.guardar(texto="x" * 481)

    def test_fila_cheia_recusa_em_vez_de_esperar(self):
        self.store.close()
        self.store = self.open_store(max_pending=2)
        self.guardar(externo="a", chave="a")
        self.guardar(externo="b", chave="b")
        with self.assertRaises(QueueFull):
            self.guardar(externo="c", chave="c")

    # ---------------------------------------------------------------- isolamento

    def test_um_produto_nao_ve_o_pedido_do_outro(self):
        message, _ = self.guardar(origem="PDV", externo="mesmo-id")
        self.assertIsNone(self.store.get("HUB", message.id))
        self.assertIsNone(self.store.get_by_external("HUB", "mesmo-id"))
        self.assertEqual(self.store.events_since("HUB"), [])
        self.assertEqual(self.store.counts("HUB")[STATUS_FILA], 0)
        self.assertEqual(self.store.counts("PDV")[STATUS_FILA], 1)

    def test_contagem_do_dia_separada_por_origem(self):
        self.guardar(origem="PDV", externo="a", chave="a")
        self.guardar(origem="PDV", externo="b", chave="b")
        self.guardar(origem="HUB", externo="c", chave="c")
        self.assertEqual(self.store.day_count("PDV"), 2)
        self.assertEqual(self.store.day_count("HUB"), 1)

    def test_stats_soma_as_duas_origens_sem_misturar(self):
        self.guardar(origem="PDV", externo="a", chave="a")
        self.guardar(origem="HUB", externo="b", chave="b")
        stats = self.store.stats()
        self.assertEqual(stats["por_origem"]["PDV"][STATUS_FILA], 1)
        self.assertEqual(stats["por_origem"]["HUB"][STATUS_FILA], 1)
        self.assertEqual(stats["respostas_por_identificar"], 0)

    # ------------------------------------------------------------------- reivindicar

    def test_reivindicar_tira_da_fila_e_accounta_tentativa(self):
        message, _ = self.guardar()
        claimed = self.store.claim_next("PDV")
        self.assertEqual(claimed.id, message.id)
        self.assertEqual(claimed.status, STATUS_ENVIANDO)
        self.assertEqual(claimed.attempts, 1)
        self.assertIsNone(self.store.claim_next("PDV"))
        self.assertIsNone(self.store.claim_next("HUB"))

    def test_reinicio_confere_o_que_parou_no_meio_e_nao_reenvia(self):
        message, _ = self.guardar()
        self.store.claim_next("PDV")
        self.store.close()

        outro = self.open_store()
        self.store = outro
        self.assertEqual(outro.reconcile_after_restart(), 1)
        recuperado = outro.get("PDV", message.id)
        self.assertEqual(recuperado.status, STATUS_INCERTO)
        self.assertIn("confirmacao", recuperado.motivo)
        self.assertIsNone(outro.claim_next("PDV"))

    def test_reinicio_nao_inventa_nada_quando_a_fila_estava_vazia(self):
        self.assertEqual(self.store.reconcile_after_restart(), 0)

    # ------------------------------------------------------------------- estados

    def test_marcas_de_estado_escrevem_a_trilha(self):
        message, _ = self.guardar()
        self.store.mark(message.id, STATUS_ENVIADO, transport="loopback", reference="ref-1")
        entregue = self.store.mark(message.id, STATUS_ENTREGUE, transport="loopback")
        self.assertEqual(entregue.status, STATUS_ENTREGUE)
        self.assertGreater(entregue.sent_at, 0)
        self.assertGreaterEqual(entregue.delivered_at, entregue.sent_at)
        self.assertEqual(entregue.transport, "loopback")
        eventos = [evento.event for evento in self.store.events_since("PDV")]
        self.assertEqual(eventos, ["criada", "enviada", "entregue"])

    def test_envio_em_duvida_so_vira_entregue_ou_falhou_por_decisao_humana(self):
        message, _ = self.guardar()
        self.store.claim_next("PDV")
        self.store.mark(message.id, STATUS_INCERTO, motivo="sem confirmacao")
        with self.assertRaises(InvalidRequest):
            self.store.resolve_uncertain(message.id, "enviado")
        resolvido = self.store.resolve_uncertain(message.id, STATUS_ENTREGUE, motivo="visto no aparelho")
        self.assertEqual(resolvido.status, STATUS_ENTREGUE)
        with self.assertRaises(InvalidRequest):
            self.store.resolve_uncertain(message.id, STATUS_FALHOU)

    def test_conferir_pedido_que_nao_existe_da_desconhecido(self):
        with self.assertRaises(UnknownMessage):
            self.store.resolve_uncertain("nao-existe", STATUS_ENTREGUE)

    def test_mudar_estado_de_pedido_inexistente_devolve_none(self):
        self.assertIsNone(self.store.mark("nao-existe", STATUS_ENVIADO))

    def test_cursor_da_trilha_avanca_sem_pular_nem_repetir(self):
        message, _ = self.guardar()
        primeiro = self.store.events_since("PDV", 0)
        self.assertEqual([evento.seq for evento in primeiro], [1])
        self.store.mark(message.id, STATUS_ENVIADO)
        depois = self.store.events_since("PDV", primeiro[-1].seq)
        self.assertEqual([evento.seq for evento in depois], [2])
        self.assertEqual(depois[0].message_id, message.id)
        self.assertEqual(depois[0].external_id, "venda-1")

    def test_limites_de_leitura_da_trilha(self):
        for indice in range(4):
            self.guardar(externo=f"e{indice}", chave=f"c{indice}")
        eventos = self.store.events_since("PDV", 0, limit=2)
        self.assertEqual(len(eventos), 2)
        self.assertEqual(self.store.events_since("PDV", 999), [])

    # ------------------------------------------------------------- respostas

    def test_resposta_de_aparelho_igual_nao_duplica(self):
        reply = InboundReply("dev-1", NUMERO, "ok", time.time())
        primeira, created_first = self.store.record_inbound(reply, transport="loopback")
        _, created_second = self.store.record_inbound(reply, transport="loopback")
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(len(self.store.pending_inbound()), 1)
        self.assertEqual(self.store.stats()["respostas_por_identificar"], 1)
        self.assertEqual(primeira.text, "ok")

    def test_resposta_sem_pedido_correspondente_fica_sem_dono(self):
        self.store.record_inbound(InboundReply("dev-1", "21977776666", "quem e?", time.time()))
        self.assertEqual(self.store.inbound_for("PDV"), [])
        self.assertEqual(self.store.inbound_for("HUB"), [])
        self.assertEqual(len(self.store.pending_inbound()), 1)

    def test_rotear_para_origem_errada_recusado(self):
        message, _ = self.guardar(origem="PDV")
        inbound, _ = self.store.record_inbound(
            InboundReply("dev-1", NUMERO, "ok", time.time()), transport="loopback"
        )
        with self.assertRaises(UnknownMessage):
            self.store.route_inbound(inbound.id, "HUB", message.id)
        self.assertFalse(self.store.get_inbound(inbound.id).roteada)

    def test_rotear_entrega_a_resposta_ao_dono_e_depois_bloqueia(self):
        message, _ = self.guardar(origem="PDV")
        inbound, _ = self.store.record_inbound(
            InboundReply("dev-1", NUMERO, "ok", time.time()), transport="loopback"
        )
        routed = self.store.route_inbound(inbound.id, "PDV", message.id, motivo="resposta do cliente")
        self.assertTrue(routed.roteada)
        self.assertEqual(self.store.inbound_for("PDV")[0].id, inbound.id)
        self.assertEqual(self.store.inbound_for("HUB"), [])
        self.assertIsNone(self.store.route_inbound(inbound.id, "PDV", message.id))
        eventos = [evento.event for evento in self.store.events_since("PDV", 0)]
        self.assertEqual(eventos[-1], "recebida")

    def test_rota_resposta_inexistente_devolve_none(self):
        message, _ = self.guardar()
        self.assertIsNone(self.store.route_inbound("nao-existe", "PDV", message.id))

    def test_candidatos_excluem_o_que_ja_terminou_ou_nem_saiu(self):
        enviado, _ = self.guardar(externo="saiu", chave="saiu")
        na_fila, _ = self.guardar(externo="parado", chave="parado")
        outro_numero, _ = self.guardar(externo="outro", chave="outro", numero="11966665555")
        self.store.mark(enviado.id, STATUS_ENVIADO)
        self.store.mark(outro_numero.id, STATUS_ENVIADO)
        candidatos = self.store.candidates(enviado.recipient_tag)
        self.assertEqual([candidato.id for candidato in candidatos], [enviado.id])
        self.assertNotIn(na_fila.id, [candidato.id for candidato in candidatos])
        self.store.mark(enviado.id, STATUS_FALHOU, motivo="recusado")
        self.assertEqual(self.store.candidates(enviado.recipient_tag), [])

    def test_candidato_traz_o_id_externo_para_o_casamento(self):
        message, _ = self.guardar(externo="pedido-77")
        self.store.mark(message.id, STATUS_ENVIADO)
        candidato = self.store.candidates(message.recipient_tag)[0]
        self.assertEqual(candidato.external_id, "pedido-77")
        self.assertEqual(candidato.origem, "PDV")

    def test_numero_sem_formato_reconhecivel_vira_resposta_sem_dono(self):
        inbound, created = self.store.record_inbound(
            InboundReply("dev-1", "nao-sei", "ok", time.time()), transport="loopback"
        )
        self.assertTrue(created)
        self.assertEqual(inbound.sender, "")
        self.assertEqual(self.store.candidates(inbound.sender_tag), [])


class VaultVaultTestCase(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.path = Path(casa.name) / "vault.key"
        self.vault = Vault.load_or_create(self.path)

    def test_iv_aleatorio_separa_duas_linhas_iguais(self):
        primeiro = self.vault.seal(CONTEUDO)
        segundo = self.vault.seal(CONTEUDO)
        self.assertNotEqual(primeiro, segundo)
        self.assertEqual(self.vault.open(primeiro), CONTEUDO)

    def test_valor_deterministico_iguala_a_busca(self):
        self.assertEqual(
            self.vault.deterministic("PDV|venda-1", "id_externo"),
            self.vault.deterministic("PDV|venda-1", "id_externo"),
        )
        self.assertNotEqual(
            self.vault.deterministic("PDV|venda-1", "id_externo"),
            self.vault.deterministic("HUB|venda-1", "id_externo"),
        )
        self.assertEqual(self.vault.reveal(self.vault.deterministic("x", "d"), "d"), "x")

    def test_rotulo_estavel_nao_revela_o_numero(self):
        rotulo = self.vault.tag(NUMERO, DOMAIN_RECIPIENT)
        self.assertEqual(rotulo, self.vault.tag(NUMERO, DOMAIN_RECIPIENT))
        self.assertNotIn(NUMERO, rotulo)
        self.assertNotEqual(rotulo, self.vault.tag("11999990000", DOMAIN_RECIPIENT))

    def test_chave_reaproveitada_e_arquivo_protegido(self):
        outra = Vault.load_or_create(self.path)
        blob = outra.seal("segredo")
        self.assertEqual(self.vault.open(blob), "segredo")

    def test_chave_corrompida_da_erro_claro(self):
        self.path.write_text("nao-e-base64-valido!!!", encoding="ascii")
        with self.assertRaises(StorageError):
            Vault.load_or_create(self.path)

    def test_abrir_conteudo_de_outra_chave_nao_vaza(self):
        blob = self.vault.seal("segredo")
        outro = Vault.load_or_create(self.path.with_name("outra.key"))
        with self.assertRaises(StorageError):
            outro.open(blob)


if __name__ == "__main__":
    unittest.main()
