"""Testes da volta do SMS: o comprovante do celular chega, abre e escreve na fila.

A ida ja tem teste proprio (``tests/test_messaging_lan.py``). Aqui o que se amarra
e o caminho de volta, que depende de tres casas ao mesmo tempo:

* a fila 2.0 so aceita o que o motorista conseguiu abrir com o segredo do
  pareamento - e o pedido que ela nao conhece devolvido para quem abriu a porta;
* um pedido ja fechado (entregue ou falhou) nao reabre por comprovante nenhum;
* a porta HTTP e a mesma da 1.7, entao um celular pareado ontem continua devolvendo
  o recibo hoje, e o recibo que nao e da fila 2.0 cai no colo da ponte antiga
  exatamente como caia antes.

Nada aqui usa internet, celular de verdade ou dados reais: soquete em 127.0.0.1 e
pasta temporaria.
"""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path

from gaspar.messaging.comprovantes import ESTADOS_DE_COMPROVANTE, aplicar_comprovante
from gaspar.messaging.config import MessagingConfig
from gaspar.messaging.model import (
    STATUS_ENTREGUE,
    STATUS_ENVIADO,
    STATUS_FALHOU,
    STATUS_FILA,
    STATUS_INCERTO,
)
from gaspar.messaging.service import MessagingService
from gaspar.messaging.store import MessageStore
from gaspar.messaging.transports import TransportRegistry
from gaspar.messaging.transports.android_lan import ESTADOS, AndroidLanTransportDriver, LanSettings
from gaspar.messaging.transports.loopback import LoopbackTransportDriver
from gaspar.messaging.vault import Vault
from gaspar.sms import crypto
from gaspar.sms.config import SmsConfig
from gaspar.sms.server import SmsHttpServer

NUMERO = "11988887777"
CONTEUDO = "Retire sua encomenda na loja"
CHAVE_PDV = base64.b64encode(b"p" * 32).decode("ascii")
CHAVE_HUB = base64.b64encode(b"h" * 32).decode("ascii")
CHAVE_ALHEIA = base64.b64encode(b"x" * 32).decode("ascii")


def blob(corpo: dict, segredo: str = CHAVE_PDV) -> str:
    """O mesmo envelope que o aplicativo do celular POSTa de volta."""
    cifrado = crypto.encrypt(crypto.key_from_base64(segredo), json.dumps(corpo).encode("utf-8"))
    return base64.b64encode(cifrado).decode("ascii")


def motorista(segredo: str = CHAVE_PDV) -> AndroidLanTransportDriver:
    return AndroidLanTransportDriver(
        LanSettings(
            ligada=True,
            segredo=segredo,
            segredos_por_origem={"HUB": CHAVE_HUB},
            host="127.0.0.1",
            descobrir=False,
        )
    )


class PonteFalsa:
    """A ponte 1.7 so para contar o que passou por ela - nenhum soquete, nenhum disco."""

    def __init__(self) -> None:
        self.aplicados: list[tuple[str, str]] = []
        self.enviados: list[str] = []

    def stats(self) -> dict:
        return {"counts": {"fila": 0, "enviando": 0}, "phone": {"online": False}}

    def enqueue(self, numero, texto, venda_id, **_extra):
        self.enviados.append(str(venda_id))
        return type(
            "Job",
            (),
            {
                "id": "job-da-17",
                "status": "fila",
                "confirmed": False,
                "sealed": False,
                "recipient_tag": "*7777",
                "content_tag": "abc",
            },
        )()

    def apply_receipt(self, job_id: str, event: str, detail: str = ""):
        self.aplicados.append((job_id, event))
        return type("Job", (), {"status": event})()


class ComprovanteNaFilaTeste(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.base = Path(casa.name)
        self.vault = Vault.load_or_create(self.base / "messaging-vault.key")
        self.store = MessageStore(self.base / "messaging.db", self.vault, max_pending=50)
        self.addCleanup(lambda: self.store.close())
        self.motorista = motorista()
        self.registry = TransportRegistry()
        self.registry.register(self.motorista)

    def guardar(self, origem: str = "PDV", externo: str = "venda-1"):
        message, _ = self.store.enqueue(
            origem=origem, external_id=externo, recipient=NUMERO, text=CONTEUDO, idempotency_key=""
        )
        return message

    def registrar(self, corpo, registry=None) -> bool:
        return aplicar_comprovante(self.store, registry or self.registry, corpo)

    # ------------------------------------------------------------------ aplicar

    def test_o_comprovante_de_entrega_fecha_o_pedido(self):
        message = self.guardar()
        self.store.mark(message.id, STATUS_ENVIADO, origem="PDV", motivo="entregue ao celular")
        self.assertTrue(self.registrar(blob({"id": message.id, "status": "delivered"})))
        depois = self.store.get("PDV", message.id)
        self.assertEqual(depois.status, STATUS_ENTREGUE)
        self.assertGreater(depois.delivered_at, 0)
        self.assertEqual(depois.motivo, "comprovante do celular")

    def test_o_pedido_em_duvida_deixa_de_estar_em_duvida(self):
        """O buraco que a porta fecha: um incerto com recibo do celular nao e mais humano."""
        message = self.guardar()
        self.store.mark(message.id, STATUS_INCERTO, origem="PDV", motivo="sem resposta")
        self.assertTrue(self.registrar(blob({"id": message.id, "status": "failed"})))
        depois = self.store.get("PDV", message.id)
        self.assertEqual(depois.status, STATUS_FALHOU)
        self.assertEqual(depois.motivo, "comprovante do celular")

    def test_o_que_o_recibo_escreve_aparece_na_trilha_do_produto(self):
        message = self.guardar()
        self.store.mark(message.id, STATUS_ENVIADO, origem="PDV")
        self.registrar(blob({"id": message.id, "status": "delivered"}))
        eventos = [evento.to_dict() for evento in self.store.events_since("PDV", 0, 20)]
        entregues = [e for e in eventos if e["status"] == STATUS_ENTREGUE]
        self.assertEqual(len(entregues), 1)
        self.assertEqual(entregues[0]["id_mensagem"], message.id)
        self.assertEqual(entregues[0]["motivo"], "comprovante do celular")

    def test_o_estado_terminal_nao_reabre(self):
        message = self.guardar()
        self.store.mark(message.id, STATUS_ENTREGUE, origem="PDV")
        self.assertTrue(self.registrar(blob({"id": message.id, "status": "failed"})))
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_ENTREGUE)

    def test_o_recibo_de_envio_nao_promove_para_entregue(self):
        message = self.guardar()
        self.store.mark(message.id, STATUS_INCERTO, origem="PDV")
        self.assertTrue(self.registrar(blob({"id": message.id, "status": "sent"})))
        depois = self.store.get("PDV", message.id)
        self.assertEqual(depois.status, STATUS_ENVIADO)
        self.assertEqual(depois.delivered_at, 0)

    def test_a_origem_vem_da_fila_nunca_do_celular(self):
        """O recibo so traz o identificador; o vizinho nao pode mover o pedido alheio."""
        do_pdv, do_hub = self.guardar("PDV", "venda-1"), self.guardar("HUB", "hub-1")
        self.store.mark(do_hub.id, STATUS_INCERTO, origem="HUB")
        self.registrar(blob({"id": do_hub.id, "status": "delivered"}, CHAVE_HUB))
        self.assertEqual(self.store.get("HUB", do_hub.id).status, STATUS_ENTREGUE)
        self.assertEqual(self.store.get("PDV", do_pdv.id).status, STATUS_FILA)

    def test_o_mesmo_recibo_duas_vezes_escreve_uma(self):
        message = self.guardar()
        self.store.mark(message.id, STATUS_ENVIADO, origem="PDV")
        corpo = blob({"id": message.id, "status": "delivered"})
        self.assertTrue(self.registrar(corpo))
        antes = self.store.events_since("PDV", 0, 50)
        self.assertTrue(self.registrar(corpo))
        self.assertEqual(len(self.store.events_since("PDV", 0, 50)), len(antes))

    # ---------------------------------------------------------------- recusas

    def test_recibo_que_abre_mas_o_pedido_nao_e_da_fila_devolve_false(self):
        self.assertFalse(self.registrar(blob({"id": "nao-existentee", "status": "delivered"})))
        self.assertEqual(self.motorista.comprovante_de("nao-existentee"), STATUS_ENTREGUE)

    def test_recibo_de_celular_que_nao_pareou_devolve_false(self):
        self.assertFalse(self.registrar(blob({"id": "m-1", "status": "delivered"}, CHAVE_ALHEIA)))

    def test_um_estado_inventado_nao_escreve_na_fila(self):
        """O recibo e nosso, mas nao afirma nada dos tres estados: a fila nao se move."""
        message = self.guardar()
        self.store.mark(message.id, STATUS_INCERTO, origem="PDV")
        self.assertTrue(self.registrar(blob({"id": message.id, "status": "quem_sabe"})))
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_INCERTO)

    def test_motorista_que_estoura_nao_derruba_a_porta(self):
        class Estoura(AndroidLanTransportDriver):
            def abrir_comprovante(self, corpo):
                raise RuntimeError("celular inventou um estado")

        registro = TransportRegistry()
        registro.register(Estoura(LanSettings(ligada=True, segredo=CHAVE_PDV, host="127.0.0.1")))
        message = self.guardar()
        self.assertFalse(self.registrar(blob({"id": message.id, "status": "delivered"}), registro))
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_FILA)

    def test_meio_sem_comprovante_nao_tampa_o_meio_que_tem(self):
        registro = TransportRegistry()
        registro.register(LoopbackTransportDriver())
        registro.register(self.motorista)
        message = self.guardar()
        self.store.mark(message.id, STATUS_ENVIADO, origem="PDV")
        self.assertTrue(self.registrar(blob({"id": message.id, "status": "delivered"}), registro))
        self.assertEqual(self.store.get("PDV", message.id).status, STATUS_ENTREGUE)

    def test_o_motorista_narra_na_mesma_moeda_da_fila(self):
        """Os dois vocabularios tem de ser os mesmos: o comprovante e escrito cru na fila."""
        self.assertEqual(set(ESTADOS), set(ESTADOS_DE_COMPROVANTE))
        self.assertEqual(set(ESTADOS_DE_COMPROVANTE), {STATUS_ENVIADO, STATUS_ENTREGUE, STATUS_FALHOU})
        self.assertNotIn(STATUS_FILA, ESTADOS_DE_COMPROVANTE)


class PortaDeComprovantesTeste(unittest.TestCase):
    """A porta da 1.7 de pe com o celular cedido: recibo para a 2.0 e recibo para a 1.7."""

    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.base = Path(casa.name)
        self.sms_config = SmsConfig(
            api_token="token-da-porta", shared_secret_b64=CHAVE_ALHEIA, require_signed_requests=False
        )
        self.ponte = PonteFalsa()
        self.motorista = motorista()
        self.registry = TransportRegistry()
        self.registry.register(self.motorista)
        self.service = MessagingService(
            MessagingConfig(enabled=True, port=0),
            home=self.base,
            registry=self.registry,
        )
        self.addCleanup(self.service.close)

    def abrir_porta(self, *, com_servico: bool = True, cedida: bool = False) -> SmsHttpServer:
        server = SmsHttpServer(
            self.ponte,
            self.sms_config,
            host="127.0.0.1",
            port=0,
            on_receipt=self.service.registrar_comprovante if com_servico else None,
            send_blocker=(lambda: "o celular desta casa envia pela barra 2.0") if cedida else None,
        )
        server.start()
        self.addCleanup(server.stop)
        return server

    def post(self, server: SmsHttpServer, rota: str, corpo: dict) -> tuple[int, dict]:
        pedido = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        conn = HTTPConnection("127.0.0.1", server.port, timeout=5)
        self.addCleanup(conn.close)
        conn.request(
            "POST",
            rota,
            body=pedido,
            headers={"Content-Type": "application/json", "X-Api-Token": self.sms_config.api_token},
        )
        resposta = conn.getresponse()
        bruto = resposta.read()
        return resposta.status, json.loads(bruto.decode("utf-8")) if bruto else {}

    def pedido_na_fila(self, origem: str = "PDV", status: str = STATUS_ENVIADO):
        message, _ = self.service.store.enqueue(
            origem=origem, external_id="venda-9", recipient=NUMERO, text=CONTEUDO, idempotency_key=""
        )
        self.service.store.mark(message.id, status, origem=origem)
        return message

    # ------------------------------------------------------------------- rotas

    def test_o_recibo_da_fila_2_0_fecha_o_pedido_pela_porta(self):
        server = self.abrir_porta()
        message = self.pedido_na_fila()
        code, corpo = self.post(
            server, "/api/mobile/receipt", {"blob": blob({"id": message.id, "status": "delivered"})}
        )
        self.assertEqual(code, 202)
        self.assertEqual(self.service.store.get("PDV", message.id).status, STATUS_ENTREGUE)

    def test_o_recibo_da_fila_2_0_nao_passa_pela_ponte_antiga(self):
        server = self.abrir_porta()
        message = self.pedido_na_fila()
        self.post(server, "/api/mobile/receipt", {"blob": blob({"id": message.id, "status": "sent"})})
        self.assertEqual(self.ponte.aplicados, [])

    def test_o_recibo_que_nao_e_da_fila_2_0_segue_para_a_1_7(self):
        server = self.abrir_porta()
        corpo = {"id": "job-da-17", "status": "delivered"}
        code, resposta = self.post(
            server, "/api/mobile/receipt", {"blob": blob(corpo, self.sms_config.shared_secret_b64)}
        )
        self.assertEqual(code, 202)
        self.assertEqual(resposta.get("status"), "delivered")
        self.assertEqual(self.ponte.aplicados, [("job-da-17", "delivered")])

    def test_a_porta_nao_inventa_destino_para_um_recibo_vazio(self):
        server = self.abrir_porta()
        code, resposta = self.post(server, "/api/mobile/receipt", {"blob": "   "})
        self.assertEqual(code, 400)
        self.assertEqual(resposta.get("error"), "recibo ausente")
        self.assertEqual(self.ponte.aplicados, [])

    def test_a_ponte_antiga_recusa_enviar_com_o_celular_cedido(self):
        server = self.abrir_porta(cedida=True)
        code, resposta = self.post(
            server, "/api/sms", {"number": NUMERO, "message": CONTEUDO, "venda_id": "venda-9"}
        )
        self.assertEqual(code, 503)
        self.assertEqual(resposta.get("codigo"), "celular_reservado")
        self.assertEqual(self.ponte.enviados, [])

    def test_sem_reserva_a_porta_e_exatamente_a_1_7_de_sempre(self):
        server = self.abrir_porta(com_servico=False)
        code, resposta = self.post(
            server, "/api/sms", {"number": NUMERO, "message": CONTEUDO, "venda_id": "venda-9"}
        )
        self.assertEqual(code, 202)
        self.assertEqual(resposta.get("id"), "job-da-17")
        self.assertEqual(self.ponte.enviados, ["venda-9"])

    def test_a_saude_continua_respondendo_com_o_celular_cedido(self):
        server = self.abrir_porta(cedida=True)
        conn = HTTPConnection("127.0.0.1", server.port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/api/health")
        resposta = conn.getresponse()
        corpo = json.loads(resposta.read().decode("utf-8"))
        self.assertEqual(resposta.status, 200)
        self.assertIn("pending", corpo)

    def test_o_gancho_que_estoura_nao_tranca_a_porta(self):
        def estoura() -> str:
            raise RuntimeError("painel indisponivel")

        server = SmsHttpServer(
            self.ponte, self.sms_config, host="127.0.0.1", port=0, send_blocker=estoura
        )
        server.start()
        self.addCleanup(server.stop)
        code, _ = self.post(
            server, "/api/sms", {"number": NUMERO, "message": CONTEUDO, "venda_id": "venda-9"}
        )
        self.assertEqual(code, 202)
        self.assertEqual(self.ponte.enviados, ["venda-9"])


class ServicoRegistraComprovanteTeste(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.base = Path(casa.name)
        self.motorista = motorista()
        registry = TransportRegistry()
        registry.register(self.motorista)
        self.service = MessagingService(
            MessagingConfig(enabled=True, port=0), home=self.base / "com-celular", registry=registry
        )
        self.addCleanup(self.service.close)

    def test_a_fachada_devolve_false_para_um_meio_sem_volta(self):
        """Um motorista sem comprovante de celular nao escreve nada na fila."""
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        registry = TransportRegistry()
        registry.register(LoopbackTransportDriver())
        service = MessagingService(
            MessagingConfig(enabled=True, port=0), home=Path(casa.name) / "sem-celular", registry=registry
        )
        self.addCleanup(service.close)
        mensagem, _ = service.store.enqueue(
            origem="PDV", external_id="venda-1", recipient=NUMERO, text=CONTEUDO, idempotency_key=""
        )
        self.assertFalse(service.registrar_comprovante(blob({"id": mensagem.id, "status": "sent"})))
        self.assertEqual(service.store.get("PDV", mensagem.id).status, STATUS_FILA)

    def test_a_fachada_abre_pelo_segredo_da_origem(self):
        mensagem, _ = self.service.store.enqueue(
            origem="HUB", external_id="hub-1", recipient=NUMERO, text=CONTEUDO, idempotency_key=""
        )
        self.service.store.mark(mensagem.id, STATUS_INCERTO, origem="HUB")
        self.assertTrue(
            self.service.registrar_comprovante(
                blob({"id": mensagem.id, "status": "delivered"}, CHAVE_HUB)
            )
        )
        self.assertEqual(self.service.store.get("HUB", mensagem.id).status, STATUS_ENTREGUE)


if __name__ == "__main__":
    unittest.main()
