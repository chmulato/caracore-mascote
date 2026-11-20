"""Testes do contrato dos motoristas e do motor da fila.

Nenhum deles mexe em celular, modem ou caixa postal: o motorista de referencia e
um dos que estao no produto, e os outros tres sao improvisados aqui mesmo para
provar as situacoes que a fila precisa tratar.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from gaspar.messaging.dispatcher import (
    MOTIVO_EXCECAO,
    MOTIVO_MEIO_OFF,
    MOTIVO_RESPOSTA,
    Dispatcher,
)
from gaspar.messaging.errors import MessagingError
from gaspar.messaging.model import (
    STATUS_ENTREGUE,
    STATUS_ENVIADO,
    STATUS_FALHOU,
    STATUS_FILA,
    STATUS_INCERTO,
    Message,
    MessageBrief,
)
from gaspar.messaging.store import MessageStore
from gaspar.messaging.transport import (
    OUTCOME_ACCEPTED,
    OUTCOME_REJECTED,
    OUTCOME_UNKNOWN,
    OUTCOME_UNAVAILABLE,
    Health,
    InboundReply,
    SmsTransportDriver,
    SubmitResult,
    accepted,
    rejected,
    unavailable,
    unknown,
)
from gaspar.messaging.transports import TransportRegistry, UnknownTransport
from gaspar.messaging.transports.loopback import LoopbackTransportDriver
from gaspar.messaging.vault import Vault

NUMERO = "11988887777"


class ContratoDoMotoristaTeste(unittest.TestCase):
    def test_classe_abstrata_exige_saude_e_envio(self):
        with self.assertRaises(TypeError):
            SmsTransportDriver()  # type: ignore[abstract]

    def test_metodos_opcionais_tem_padrao_seguro(self):
        class Minimo(SmsTransportDriver):
            name = "minimo"

            def health(self) -> Health:
                return Health(True)

            def submit(self, message: Message) -> SubmitResult:
                return accepted()

        driver = Minimo()
        self.assertEqual(driver.poll_inbound(), [])
        self.assertIsNone(driver.correlate(InboundReply("d", NUMERO, "oi", time.time()), []))
        self.assertIsNone(driver.resolve_uncertain(Message(id="1", origem="PDV", external_id="e",
                                                          idempotency_key="k", recipient=NUMERO, text="oi")))
        self.assertIsNone(driver.shutdown())
        self.assertFalse(driver.supports_reception)
        self.assertEqual(driver.describe()["nome"], "minimo")

    def test_resultado_fora_dos_quatro_nao_existe(self):
        with self.assertRaises(ValueError):
            SubmitResult("quieta")

    def test_atalhos_devolvem_os_quatro_resultados(self):
        self.assertEqual(accepted("ok", "ref").outcome, OUTCOME_ACCEPTED)
        self.assertEqual(rejected("sem").outcome, OUTCOME_REJECTED)
        self.assertEqual(unknown().outcome, OUTCOME_UNKNOWN)
        self.assertEqual(unavailable("fora").outcome, OUTCOME_UNAVAILABLE)


class MotoristaDeReferenciaTeste(unittest.TestCase):
    def setUp(self):
        self.driver = LoopbackTransportDriver()

    def test_disponibilidade_por_configuracao(self):
        self.assertTrue(self.driver.health().available)
        desligado = LoopbackTransportDriver(available=False)
        self.assertFalse(desligado.health().available)

    def test_guarda_o_que_recebeu(self):
        message = Message(
            id="m-1", origem="PDV", external_id="venda-1", idempotency_key="k",
            recipient=NUMERO, text="oi",
        )
        resultado = self.driver.submit(message)
        self.assertEqual(resultado.outcome, OUTCOME_ACCEPTED)
        self.assertEqual(self.driver.submitted, [message])

    def test_escala_os_quatro_resultados_por_nome(self):
        for nome, esperado in (
            ("aceito", OUTCOME_ACCEPTED),
            ("recusado", OUTCOME_REJECTED),
            ("incerto", OUTCOME_UNKNOWN),
            ("indisponivel", OUTCOME_UNAVAILABLE),
        ):
            driver = LoopbackTransportDriver()
            driver.script(nome)
            message = Message(
                id=f"m-{nome}", origem="PDV", external_id="e", idempotency_key="k",
                recipient=NUMERO, text="oi",
            )
            self.assertEqual(driver.submit(message).outcome, esperado)

    def test_meio_desligado_recusa_sem_gravar(self):
        driver = LoopbackTransportDriver(available=False)
        message = Message(id="m", origem="PDV", external_id="e", idempotency_key="k",
                          recipient=NUMERO, text="oi")
        self.assertEqual(driver.submit(message).outcome, OUTCOME_UNAVAILABLE)
        self.assertEqual(driver.submitted, [])

    def test_respostas_recebidas_sao_entregues_uma_unica_vez(self):
        driver = LoopbackTransportDriver(device_id="dev-9")
        driver.receive(NUMERO, "pode ser", reference="ref-1", when=123.0)
        replies = driver.poll_inbound()
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].device_id, "dev-9")
        self.assertEqual(replies[0].reference, "ref-1")
        self.assertEqual(replies[0].received_at, 123.0)
        self.assertEqual(driver.poll_inbound(), [])


class RegistroTeste(unittest.TestCase):
    def setUp(self):
        self.registry = TransportRegistry()
        self.loop = LoopbackTransportDriver()

    def test_motorista_sem_nome_nao_entra(self):
        class SemNome(SmsTransportDriver):
            name = ""

            def health(self):
                return Health(True)

            def submit(self, message):
                return accepted()

        with self.assertRaises(MessagingError):
            self.registry.register(SemNome())

    def test_ligar_origem_a_meio_inexistente_da_erro(self):
        with self.assertRaises(UnknownTransport):
            self.registry.bind("PDV", "nao-tem")
        self.assertEqual(self.registry.bindings(), {})

    def test_ligar_desligar_e_descobrir_por_origem(self):
        self.registry.register(self.loop)
        self.registry.bind("PDV", "loopback")
        self.assertIs(self.registry.driver_for("PDV"), self.loop)
        self.assertIsNone(self.registry.driver_for("HUB"))
        self.assertEqual(self.registry.bindings(), {"PDV": "loopback"})
        self.registry.bind("PDV", "")
        self.assertIsNone(self.registry.driver_for("PDV"))
        self.registry.unbind("HUB")

    def test_saude_de_origem_sem_meio_diz_o_motivo(self):
        saude = self.registry.health()
        self.assertFalse(saude["PDV"].available)
        self.registry.register(self.loop)
        self.registry.bind("PDV", "loopback")
        self.assertTrue(self.registry.health()["PDV"].available)
        self.assertEqual(self.registry.names(), ["loopback"])
        self.assertIn("loopback", self.registry.describe())

    def test_motorista_que_quebra_nao_derruba_a_checagem(self):
        class Quebrado(LoopbackTransportDriver):
            name = "quebrado"

            def health(self):
                raise RuntimeError("porta ocupada")

        self.registry.register(Quebrado())
        self.registry.bind("HUB", "quebrado")
        saude = self.registry.health()["HUB"]
        self.assertFalse(saude.available)
        self.assertIn("porta ocupada", saude.detail)

    def test_encerrar_chama_todos_e_ignora_quem_reclama(self):
        chamada = []

        class Entra(SmsTransportDriver):
            name = "entra"

            def health(self):
                return Health(True)

            def submit(self, message):
                return accepted()

            def shutdown(self):
                chamada.append("entra")

        class Rebela(SmsTransportDriver):
            name = "rebela"

            def health(self):
                return Health(True)

            def submit(self, message):
                return accepted()

            def shutdown(self):
                raise RuntimeError("na largo a porta")

        registro = TransportRegistry()
        registro.register(Entra())
        registro.register(Rebela())
        registro.shutdown()
        self.assertEqual(chamada, ["entra"])


class FilaBaseTeste(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        base = Path(casa.name)
        self.vault = Vault.load_or_create(base / "vault.key")
        self.store = MessageStore(base / "messaging.db", self.vault)
        self.addCleanup(lambda: self.store.close())
        self.registry = TransportRegistry()
        self.loop = LoopbackTransportDriver()
        self.registry.register(self.loop)
        self.eventos: list[str] = []
        self.dispatcher = Dispatcher(
            self.store, self.registry, max_attempts=2, on_log=self.eventos.append
        )

    def pedir(self, origem="PDV", externo="venda-1", numero=NUMERO, chave=""):
        message, _ = self.store.enqueue(
            origem=origem, external_id=externo, recipient=numero, text="oi", idempotency_key=chave
        )
        return message

    def usar_motorista(self, driver, origem="PDV"):
        self.registry.register(driver)
        self.registry.bind(origem, driver.name)

    def test_sem_meio_ligado_nada_sai_e_nada_se_perde(self):
        message = self.pedir()
        self.assertEqual(self.dispatcher.run_once(), 0)
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_FILA)

    def test_aceito_vira_enviado_com_referencia_do_meio(self):
        self.usar_motorista(self.loop)
        message = self.pedir()
        self.assertEqual(self.dispatcher.run_once(), 1)
        atual = self.store.get("PDV", message.id)
        self.assertEqual(atual.status, STATUS_ENVIADO)
        self.assertEqual(atual.transport, "loopback")
        self.assertEqual(len(self.loop.submitted), 1)
        eventos = [evento.event for evento in self.store.events_since("PDV", 0)]
        self.assertEqual(eventos, ["criada", "enviada"])

    def test_recusa_volta_para_a_fila_ate_acabar_a_tentativa(self):
        driver = LoopbackTransportDriver(outcomes=["recusado", "recusado"])
        self.usar_motorista(driver)
        message = self.pedir()
        self.dispatcher.run_once()
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_FILA)
        self.dispatcher.run_once()
        falho = self.store.get("PDV", message.id)
        self.assertEqual(falho.status, STATUS_FALHOU)
        self.assertEqual(falho.attempts, 2)
        self.assertEqual(len(driver.submitted), 2)

    def test_meio_indisponivel_devolve_para_a_fila_sem_gastar_o_pedido(self):
        driver = LoopbackTransportDriver(available=False)
        self.usar_motorista(driver)
        message = self.pedir()
        self.dispatcher.run_once()
        volta = self.store.get("PDV", message.id)
        self.assertEqual(volta.status, STATUS_FILA)
        self.assertIn("desligado", volta.motivo)
        self.assertEqual(driver.submitted, [])

    def test_motivo_do_motorista_quando_ele_nao_sabe_explicar(self):
        class SemExplicacao(LoopbackTransportDriver):
            name = "semexplicacao"

            def health(self):
                return Health(False)

        driver = SemExplicacao()
        self.usar_motorista(driver)
        message = self.pedir()
        self.dispatcher.run_once()
        self.assertEqual(self.store.get("PDV", message.id).motivo, MOTIVO_MEIO_OFF)

    def test_incerto_espera_decisao_humana_e_jamais_reenvia_sozinho(self):
        driver = LoopbackTransportDriver(outcomes=["incerto"])
        self.usar_motorista(driver)
        message = self.pedir()
        self.dispatcher.run_once()
        duvida = self.store.get("PDV", message.id)
        self.assertEqual(duvida.status, STATUS_INCERTO)
        for _ in range(3):
            self.dispatcher.run_once()
        self.assertEqual(len(driver.submitted), 1)
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_INCERTO)
        resolvido = self.store.resolve_uncertain(
            message.id, STATUS_ENTREGUE, origem="PDV", motivo="visto no celular"
        )
        self.assertEqual(resolvido.status, STATUS_ENTREGUE)

    def test_excecao_no_meio_vira_duvida_e_o_motor_para_de_puxar(self):
        class Explode(LoopbackTransportDriver):
            name = "explode"

            def submit(self, message):
                raise RuntimeError("modem caiu no meio")

        driver = Explode()
        self.usar_motorista(driver)
        message = self.pedir()
        self.dispatcher.run_once()
        atual = self.store.get("PDV", message.id)
        self.assertEqual(atual.status, STATUS_INCERTO)
        self.assertIn(MOTIVO_EXCECAO, atual.motivo)
        self.dispatcher.run_once()
        self.assertEqual(self.store.counts("PDV")[STATUS_INCERTO], 1)

    def test_meio_que_devolve_bobagem_vira_duvida(self):
        class Bobagem(LoopbackTransportDriver):
            name = "bobagem"

            def submit(self, message):
                return "acho que mandei"

        self.usar_motorista(Bobagem())
        message = self.pedir()
        self.dispatcher.run_once()
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_INCERTO)

    def test_uma_rodada_atende_as_duas_origens(self):
        driver = LoopbackTransportDriver()
        self.registry.register(driver)
        self.registry.bind("PDV", "loopback")
        self.registry.bind("HUB", "loopback")
        self.pedir(origem="PDV", externo="p")
        self.pedir(origem="HUB", externo="h")
        self.assertEqual(self.dispatcher.run_once(), 2)
        self.assertEqual(self.store.counts("PDV")[STATUS_ENVIADO], 1)
        self.assertEqual(self.store.counts("HUB")[STATUS_ENVIADO], 1)

    def test_pedido_nao_rouba_o_lugar_do_outro_na_fila(self):
        self.usar_motorista(self.loop)
        primeiro = self.pedir(externo="a", chave="a")
        self.pedir(externo="b", chave="b")
        self.dispatcher.run_once()
        self.assertEqual(self.store.get("PDV", primeiro.id).status, STATUS_ENVIADO)
        self.assertEqual(self.store.counts("PDV")[STATUS_FILA], 1)


class RespostasTeste(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        base = Path(casa.name)
        self.vault = Vault.load_or_create(base / "vault.key")
        self.store = MessageStore(base / "messaging.db", self.vault)
        self.addCleanup(lambda: self.store.close())
        self.registry = TransportRegistry()
        self.loop = LoopbackTransportDriver()
        self.registry.register(self.loop)
        self.registry.bind("PDV", "loopback")
        self.registry.bind("HUB", "loopback")
        self.dispatcher = Dispatcher(self.store, self.registry)

    def pedir_e_enviar(self, origem="PDV", externo="venda-1", numero=NUMERO):
        message, _ = self.store.enqueue(
            origem=origem, external_id=externo, recipient=numero, text="oi"
        )
        self.dispatcher.run_once()
        return message

    def test_resposta_unica_para_o_numero_volta_ao_dono(self):
        message = self.pedir_e_enviar(origem="PDV", externo="pedido-3")
        self.loop.receive(NUMERO, "pode deixar")
        self.assertEqual(self.dispatcher.drain_inbound(), 1)
        respostas = self.store.inbound_for("PDV")
        self.assertEqual([resposta.message_id for resposta in respostas], [message.id])
        self.assertEqual(self.store.inbound_for("HUB"), [])
        self.assertEqual(self.store.pending_inbound(), [])
        eventos = self.store.events_since("PDV", 0)
        self.assertEqual(eventos[-1].event, "recebida")
        self.assertEqual(eventos[-1].motivo, MOTIVO_RESPOSTA)
        self.assertEqual(eventos[-1].external_id, "pedido-3")

    def test_resposta_repetida_pelo_meio_nao_duplica(self):
        self.pedir_e_enviar()
        self.loop.receive(NUMERO, "ok")
        self.assertEqual(self.dispatcher.drain_inbound(), 1)
        self.loop.receive(NUMERO, "ok")
        self.assertEqual(self.dispatcher.drain_inbound(), 0)
        self.assertEqual(len(self.store.inbound_for("PDV")), 1)

    def test_resposta_sem_pedido_correspondente_fica_por_identificar(self):
        self.loop.receive("21977776666", "quem fala?")
        self.assertEqual(self.dispatcher.drain_inbound(), 1)
        self.assertEqual(len(self.store.pending_inbound()), 1)
        self.assertEqual(self.store.inbound_for("PDV"), [])
        self.assertEqual(self.store.inbound_for("HUB"), [])

    def test_dois_pedidos_para_o_mesmo_numero_nao_se_escolhe_no_chute(self):
        primeiro = self.pedir_e_enviar(externo="um")
        segundo = self.pedir_e_enviar(externo="dois")
        self.loop.receive(NUMERO, "qual dos dois?")
        self.dispatcher.drain_inbound()
        self.assertEqual(len(self.store.pending_inbound()), 1)
        self.assertEqual(self.store.inbound_for("PDV"), [])
        self.assertNotIn(primeiro.id, [r.message_id for r in self.store.inbound_for("PDV")])
        self.assertNotIn(segundo.id, [r.message_id for r in self.store.inbound_for("PDV")])

    def test_meio_que_prova_o_destino_da_resposta_escolhe_o_pedido(self):
        class ComProva(LoopbackTransportDriver):
            name = "comprova"

            def correlate(self, reply, candidates):
                for candidato in candidates:
                    if candidato.external_id in reply.text:
                        return candidato
                return None

        driver = ComProva()
        self.registry.register(driver)
        self.registry.bind("PDV", driver.name)
        self.registry.bind("HUB", driver.name)
        self.pedir_e_enviar(origem="PDV", externo="nota-fiscal")
        self.pedir_e_enviar(origem="HUB", externo="agenda")
        driver.receive(NUMERO, "sobre a nota-fiscal: certo")
        self.dispatcher.drain_inbound()
        respostas = self.store.inbound_for("PDV")
        self.assertEqual(len(respostas), 1)
        self.assertEqual(self.store.inbound_for("HUB"), [])
        self.assertEqual(respostas[0].message_id, self.store.get_by_external("PDV", "nota-fiscal").id)

    def test_prova_apontando_para_pedido_que_nao_existe_e_ignorada(self):
        class Mentiroso(LoopbackTransportDriver):
            name = "mentiroso"

            def correlate(self, reply, candidates):
                return MessageBrief(id="invento-1", origem="HUB", external_id="x",
                                    created_at=time.time(), status=STATUS_ENVIADO)

        driver = Mentiroso()
        self.registry.register(driver)
        self.registry.bind("PDV", driver.name)
        self.pedir_e_enviar(origem="PDV", externo="um")
        self.pedir_e_enviar(origem="PDV", externo="dois")
        driver.receive(NUMERO, "resposta")
        self.dispatcher.drain_inbound()
        self.assertEqual(len(self.store.pending_inbound()), 1)

    def test_meio_sem_recepcao_nao_e_perguntado(self):
        class SemRecepcao(LoopbackTransportDriver):
            name = "semrecepcao"
            supports_reception = False

        self.registry.register(SemRecepcao())
        self.registry.bind("HUB", "semrecepcao")
        self.assertEqual(self.dispatcher.drain_inbound(), 0)

    def test_meio_que_nao_sabe_ler_nao_para_a_ronda(self):
        class Muda(LoopbackTransportDriver):
            name = "muda"

            def poll_inbound(self):
                raise RuntimeError("caixa postal fora do ar")

        self.registry.register(Muda())
        self.registry.bind("HUB", "muda")
        self.pedir_e_enviar(origem="PDV")
        self.loop.receive(NUMERO, "oi")
        self.assertEqual(self.dispatcher.drain_inbound(), 1)


class RondaTeste(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        base = Path(casa.name)
        self.store = MessageStore(base / "messaging.db", Vault.load_or_create(base / "vault.key"))
        self.addCleanup(lambda: self.store.close())
        self.registry = TransportRegistry()
        self.registry.register(LoopbackTransportDriver())
        self.registry.bind("PDV", "loopback")

    def test_ronda_para_quando_mandam_parar(self):
        import threading

        dispatcher = Dispatcher(self.store, self.registry)
        parada = threading.Event()
        thread = threading.Thread(target=dispatcher.run_forever, args=(parada,), kwargs={"interval": 0.2})
        thread.start()
        self.store.enqueue(origem="PDV", external_id="v", recipient=NUMERO, text="oi")
        limite = time.time() + 5
        while time.time() < limite and self.store.counts("PDV")[STATUS_ENVIADO] == 0:
            time.sleep(0.05)
        parada.set()
        thread.join(timeout=3)
        self.assertEqual(self.store.counts("PDV")[STATUS_ENVIADO], 1)
        self.assertFalse(thread.is_alive())

    def test_ronda_sobrevive_a_erro_do_motorista(self):
        import threading

        class Instavel(LoopbackTransportDriver):
            name = "instavel"
            detonou = False

            def submit(self, message):
                if not Instavel.detonou:
                    Instavel.detonou = True
                    raise RuntimeError("modem caiu no meio")
                return accepted()

        self.registry.register(Instavel())
        self.registry.bind("PDV", "instavel")
        dispatcher = Dispatcher(self.store, self.registry)
        parada = threading.Event()
        thread = threading.Thread(
            target=dispatcher.run_forever, args=(parada,), kwargs={"interval": 0.2}
        )
        thread.start()
        self.store.enqueue(origem="PDV", external_id="quebrou", recipient=NUMERO, text="oi")
        limite = time.time() + 5
        while time.time() < limite and self.store.counts("PDV")[STATUS_INCERTO] == 0:
            time.sleep(0.05)
        self.store.enqueue(origem="PDV", external_id="depois", recipient=NUMERO, text="oi")
        limite = time.time() + 5
        while time.time() < limite and self.store.counts("PDV")[STATUS_ENVIADO] == 0:
            time.sleep(0.05)
        parada.set()
        thread.join(timeout=3)
        self.assertEqual(self.store.counts("PDV")[STATUS_INCERTO], 1)
        self.assertEqual(self.store.counts("PDV")[STATUS_ENVIADO], 1)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
