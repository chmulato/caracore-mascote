"""Testes do contrato local, das credenciais por origem e da fachada do servico.

Tudo numa pasta temporaria, com porta escolhida pelo sistema e o motorista de
referencia: nenhum pedido sai do computador e nada de cliente existe aqui.
"""

from __future__ import annotations

import json
import secrets
import tempfile
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

from gaspar.messaging.config import MessagingConfig, is_loopback_host, load_config
from gaspar.messaging.credentials import CredentialVault, new_token
from gaspar.messaging.errors import CredentialError
from gaspar.messaging.model import STATUS_ENTREGUE, STATUS_FILA, STATUS_INCERTO
from gaspar.messaging.service import MessagingService
from gaspar.messaging.store import MessageStore
from gaspar.messaging.transports.loopback import LoopbackTransportDriver
from gaspar.messaging.vault import Vault
from gaspar.sms import signing

NUMERO = "11988887777"
OUTRO_NUMERO = "21977776666"
CONTEUDO = "TEXTO-UNICO-DA-MENSAGEM-DE-TESTE"


def _inteiro(valor: object) -> int:
    """Solo para o teste de cabecalho torto: o que nao e numero vira 0 na assinatura."""
    try:
        return int(str(valor))
    except (TypeError, ValueError):
        return 0


class TempTestCase(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        self.base = Path(casa.name)

    def config(self, **kwargs) -> MessagingConfig:
        opcoes = {"enabled": True, "port": 0, "require_signed_requests": True}
        opcoes.update(kwargs)
        return MessagingConfig(**opcoes)


class ConfigTeste(TempTestCase):
    def test_o_padrao_deixa_tudo_desligado(self):
        config = MessagingConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8767)
        self.assertTrue(config.require_signed_requests)
        self.assertEqual(config.transports, {})

    def test_escrever_e_ler_batem(self):
        config = MessagingConfig(enabled=True, port=0, max_attempts=3, daily_limit_per_origin=10)
        config.set_transport("PDV", "loopback")
        caminho = config.save(self.base / "messaging.json")
        relida = load_config(caminho)
        self.assertTrue(relida.enabled)
        self.assertEqual(relida.max_attempts, 3)
        self.assertEqual(relida.daily_limit_per_origin, 10)
        self.assertEqual(relida.transport_for("PDV"), "loopback")
        self.assertEqual(relida.transport_for("HUB"), "")

    def test_desligar_o_meio_da_origem_e_nada_de_chaves_desconhecidas(self):
        config = MessagingConfig(transports={"PDV": "loopback", "HUB": "smtp_email"})
        config.set_transport("PDV", "")
        self.assertEqual(config.transports, {"HUB": "smtp_email"})
        self.assertEqual(config.transport_for("LOJA"), "")
        self.assertEqual(config.origins_with_transport, ("HUB",))

    def test_arquivo_ausente_ou_torto_devolve_o_padrao_desligado(self):
        self.assertFalse(load_config(self.base / "nao-existe.json").enabled)
        (self.base / "ruim.json").write_text("{isto nao e json", encoding="utf-8")
        self.assertFalse(load_config(self.base / "ruim.json").enabled)
        (self.base / "lista.json").write_text("[1, 2, 3]", encoding="utf-8")
        self.assertFalse(load_config(self.base / "lista.json").enabled)
        (self.base / "invencao.json").write_text('{"enabled": true, "nada_aqui": 1}', encoding="utf-8")
        self.assertTrue(load_config(self.base / "invencao.json").enabled)

    def test_valores_fora_do_mundo_real_sao_ajustados(self):
        config = MessagingConfig(
            enabled="sim",
            host="0.0.0.0",
            port="99999999",
            max_attempts="7",
            poll_interval_seconds=-3,
            transports={"PDV": " loopback ", "LOJA": "x", "HUB": None},
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 65535)
        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.poll_interval_seconds, 0.2)
        self.assertEqual(config.transport_for("PDV"), "loopback")
        self.assertEqual(config.transport_for("HUB"), "")
        self.assertEqual(config.transport_for("LOJA"), "")
        self.assertNotIn("LOJA", config.transports)

    def test_so_endereco_do_proprio_computador_aceito(self):
        for host in ("127.0.0.1", "localhost", "::1", "127.5.5.5"):
            self.assertTrue(is_loopback_host(host), host)
        for host in ("0.0.0.0", "192.168.0.10", "", "hub.caracore.com.br", "10.0.0.5"):
            self.assertFalse(is_loopback_host(host), host)


class ServicoTeste(TempTestCase):
    def service(self, on_log=None, **config_kwargs) -> MessagingService:
        service = MessagingService(self.config(**config_kwargs), home=self.base, on_log=on_log)
        self.addCleanup(service.close)
        return service

    def test_desligado_nao_abre_porta_nem_ronda(self):
        logs: list[str] = []
        service = MessagingService(MessagingConfig(), home=self.base, on_log=logs.append)
        self.addCleanup(service.close)
        self.assertFalse(service.start())
        self.assertFalse(service.running)
        self.assertIsNone(service.api)
        self.assertIn("barra de mensagens desligada na configuracao", logs)

    def test_na_primeira_volta_a_credencial_e_criada_uma_sozinha(self):
        service = self.service()
        primeira, criada = service.credentials.ensure("PDV")
        self.assertTrue(criada)
        self.assertEqual(len(primeira.token), len(new_token()))
        segunda, criada_de_novo = service.credentials.ensure("PDV")
        self.assertFalse(criada_de_novo)
        self.assertIsNone(segunda)

    def test_girar_a_credencial_derruba_a_anterior(self):
        service = self.service()
        antiga = service.issue_credential("HUB")
        nova = service.issue_credential("HUB")
        self.assertNotEqual(antiga.token, nova.token)
        self.assertIsNone(service.credentials.resolve(antiga.token))
        self.assertEqual(service.credentials.resolve(nova.token), "HUB")
        with self.assertRaises(CredentialError):
            service.credentials.issue("HUB", replace=False)
        self.assertTrue(service.credentials.revoke("HUB"))
        self.assertIsNone(service.credentials.resolve(nova.token))
        self.assertFalse(service.credentials.revoke("HUB"))

    def test_arquivo_da_fila_nao_contem_a_credencial_nem_o_cliente(self):
        service = self.service()
        credencial = service.issue_credential("PDV")
        service.store.enqueue(origem="PDV", external_id="venda-1", recipient=NUMERO, text=CONTEUDO)
        disco = b""
        for arquivo in sorted(self.base.iterdir()):
            if arquivo.is_file():
                disco += arquivo.read_bytes()
        self.assertNotIn(credencial.token.encode(), disco)
        self.assertNotIn(credencial.secret.encode(), disco)
        self.assertNotIn(NUMERO.encode(), disco)
        self.assertNotIn(CONTEUDO.encode(), disco)

    def test_reinicio_confere_o_que_parou_no_meio_e_nada_reenvia(self):
        service = self.service()
        service.start(start_round=False, open_port=False)
        service.registry.register(LoopbackTransportDriver())
        service.registry.bind("PDV", "loopback")
        message, _ = service.store.enqueue(
            origem="PDV", external_id="pendente", recipient=NUMERO, text=CONTEUDO
        )
        service.store.claim_next("PDV")

        outro = self.service()
        outro.start(start_round=False, open_port=False)
        self.assertEqual(outro.uncertain_after_restart, 1)
        self.assertEqual(outro.store.get("PDV", message.id).status, STATUS_INCERTO)
        self.assertIsNone(outro.store.claim_next("PDV"))

    def test_meio_inexistente_deixa_a_origem_desligada_sem_quebrar(self):
        logs: list[str] = []
        service = self.service(on_log=logs.append)
        service.config.set_transport("PDV", "modem-que-nao-existe")
        self.assertTrue(service.start(start_round=False, open_port=False))
        self.assertIsNone(service.registry.driver_for("PDV"))
        self.assertTrue(any("indisponivel para PDV" in texto for texto in logs))

    def test_descricao_do_servico_nao_vaza_dado_de_cliente(self):
        service = self.service()
        service.start(start_round=False, open_port=False)
        service.issue_credential("PDV")
        service.store.enqueue(origem="PDV", external_id="v", recipient=NUMERO, text=CONTEUDO)
        estado = service.status()
        texto = json.dumps(estado, ensure_ascii=False)
        self.assertNotIn(NUMERO, texto)
        self.assertNotIn(CONTEUDO, texto)
        self.assertTrue(estado["ativo"])
        self.assertTrue(estado["rodando"])
        self.assertEqual(estado["fila"]["por_origem"]["PDV"][STATUS_FILA], 1)
        self.assertFalse(estado["meios"]["PDV"]["disponivel"])
        self.assertTrue(estado["assinatura_obrigatoria"])

    def test_ronda_liquida_a_fila_sozinha(self):
        service = self.service(max_attempts=1, poll_interval_seconds=0.2)
        service.registry.register(LoopbackTransportDriver())
        service.config.set_transport("PDV", "loopback")
        service.start()
        self.addCleanup(service.stop)
        service.store.enqueue(origem="PDV", external_id="sozinho", recipient=NUMERO, text=CONTEUDO)
        limite = time.time() + 5
        counts = service.store.counts("PDV")
        while time.time() < limite and counts["fila"] + counts["enviando"] > 0:
            time.sleep(0.05)
            counts = service.store.counts("PDV")
        self.assertEqual(counts["enviado"], 1)


class CredenciaisTeste(unittest.TestCase):
    def setUp(self):
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        base = Path(casa.name)
        self.vault = Vault.load_or_create(base / "vault.key")
        self.store = MessageStore(base / "credenciais.db", self.vault)
        self.addCleanup(self.store.close)
        self.credenciais = CredentialVault(self.store, self.vault)

    def test_duas_origens_dois_pares_diferentes(self):
        pdv = self.credenciais.issue("PDV")
        hub = self.credenciais.issue("HUB")
        self.assertEqual(self.credenciais.resolve(pdv.token), "PDV")
        self.assertEqual(self.credenciais.resolve(hub.token), "HUB")
        self.assertNotEqual(pdv.token, hub.token)
        self.assertNotEqual(pdv.secret, hub.secret)

    def test_segredo_fica_cifrado_mas_fica_disponivel_para_assinar(self):
        emissao = self.credenciais.issue("PDV")
        self.assertEqual(self.credenciais.secret_for("PDV"), emissao.secret)
        disco = Path(self.store.path).read_bytes()
        self.assertNotIn(emissao.secret.encode(), disco)

    def test_token_vazio_ou_de_fora_nao_resolve(self):
        self.credenciais.issue("PDV")
        for token in ("", None, "   ", "token-inventado"):
            self.assertIsNone(self.credenciais.resolve(token))

    def test_origem_sem_credencial_nao_tem_segredo(self):
        self.assertEqual(self.credenciais.secret_for("HUB"), "")
        self.assertFalse(self.credenciais.exists("HUB"))

    def test_descricao_mostra_so_metadados(self):
        self.credenciais.issue("PDV")
        descricao = self.credenciais.describe()
        texto = json.dumps(descricao, ensure_ascii=False)
        self.assertNotIn("verifier", texto)
        self.assertNotIn("salt", texto)
        self.assertIn("emitida_em", texto)
        self.assertTrue(descricao["PDV"]["assinatura"])
        self.assertEqual(descricao["HUB"]["emitida_em"], 0.0)


class ContratoLocalTeste(TempTestCase):
    def setUp(self):
        super().setUp()
        self.config_obj = self.config(max_attempts=1, poll_interval_seconds=0.2)
        self.meio = LoopbackTransportDriver()
        self.service = MessagingService(self.config_obj, home=self.base)
        self.addCleanup(self.service.close)
        self.service.registry.register(self.meio)
        self.pdv = self.service.issue_credential("PDV")
        self.hub = self.service.issue_credential("HUB")
        self.service.start(start_round=False)

    # ------------------------------------------------------------------ ajuda

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        credencial=None,
        *,
        sign: bool = True,
        nonce: str | None = None,
        timestamp: object = None,
        signature: str | None = None,
        raw: bytes | None = None,
    ):
        payload = (
            raw
            if raw is not None
            else (json.dumps(body).encode("utf-8") if body is not None else None)
        )
        envio = {"Content-Type": "application/json"} if payload is not None else {}
        if credencial is not None:
            envio["X-Api-Token"] = credencial.token
        if sign and method.upper() == "POST" and credencial is not None:
            momento = int(time.time()) if timestamp is None else _inteiro(timestamp)
            valor_nonce = nonce or secrets.token_hex(8)
            assinatura = signature or signing.sign_request(
                credencial.secret.encode("utf-8"),
                method,
                path,
                payload or b"",
                momento,
                valor_nonce,
            )
            envio[signing.TIMESTAMP_HEADER] = str(momento if timestamp is None else timestamp)
            envio[signing.NONCE_HEADER] = valor_nonce
            envio[signing.SIGNATURE_HEADER] = assinatura
        connection = HTTPConnection("127.0.0.1", self.service.port, timeout=5)
        connection.request(method, path, body=payload, headers=envio)
        response = connection.getresponse()
        texto = response.read().decode("utf-8")
        connection.close()
        try:
            return response.status, json.loads(texto)
        except ValueError:  # pragma: no cover - o contrato sempre responde json
            return response.status, {"bruto": texto}

    def pedir(self, externo="venda-1", numero=NUMERO, texto=CONTEUDO, chave="", credencial=None):
        return self.request(
            "POST",
            "/v2/messages",
            {"id_externo": externo, "destino": numero, "mensagem": texto, "chave_repeticao": chave},
            credencial or self.pdv,
        )

    def ligar_meio(self, origem="PDV"):
        self.service.registry.bind(origem, self.meio.name)

    # ------------------------------------------------------------------ portas

    def test_saude_publica_nao_mostra_conteudo_nem_trafego(self):
        self.pedir()
        code, data = self.request("GET", "/v2/health", sign=False)
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["servico"], "gaspar-messaging")
        self.assertTrue(data["ativo"])
        self.assertGreater(data["porta"], 0)
        texto = json.dumps(data, ensure_ascii=False)
        self.assertNotIn(NUMERO, texto)
        self.assertNotIn("por_origem", texto)

    def test_indice_do_contrato_sem_credencial(self):
        code, data = self.request("GET", "/v2")
        self.assertEqual(code, 200)
        self.assertEqual(data["fase"], "alpha")

    def test_sem_credencial_nao_passa(self):
        code, data = self.request(
            "POST", "/v2/messages", {"id_externo": "x"}, credencial=None, sign=False
        )
        self.assertEqual(code, 401)
        self.assertIn("credencial", data["error"])

    def test_credencial_falsa_nao_passa(self):
        class Falsa:
            token = "token-que-ninguem-emitiu"
            secret = "segredo-que-ninguem-emitiu"

        self.assertEqual(
            self.request("POST", "/v2/messages", {"id_externo": "x"}, credencial=Falsa())[0], 401
        )
        self.assertEqual(self.request("GET", "/v2/events", credencial=Falsa())[0], 401)

    def test_rota_desconhecida(self):
        self.assertEqual(self.request("GET", "/v2/nada")[0], 404)
        self.assertEqual(self.request("POST", "/v2/nada", {}, credencial=self.pdv)[0], 404)

    def test_pedido_de_fora_do_computador_recusado(self):
        original = self.service.api.allows_local_only
        self.service.api.allows_local_only = lambda address: False
        try:
            code, data = self.request("GET", "/v2/events", credencial=self.pdv)
            self.assertEqual(code, 403)
            self.assertIn("proprio computador", data["error"])
        finally:
            self.service.api.allows_local_only = original

    # ------------------------------------------------------------------ gravar

    def test_pedido_valido_devolve_202_e_guarda_na_fila(self):
        code, data = self.pedir(externo="pedido-9")
        self.assertEqual(code, 202)
        self.assertTrue(data["criado"])
        self.assertEqual(data["pedido"]["status"], STATUS_FILA)
        self.assertEqual(data["pedido"]["origem"], "PDV")
        self.assertIn("guardado", data["aviso"])
        self.assertNotIn(NUMERO, json.dumps(data, ensure_ascii=False))
        guardado = self.service.store.get("PDV", data["pedido"]["id_mensagem"])
        self.assertEqual(guardado.text, CONTEUDO)

    def test_origem_nunca_vem_do_corpo(self):
        code, data = self.request(
            "POST",
            "/v2/messages",
            {"id_externo": "x", "destino": NUMERO, "mensagem": "oi", "origem": "HUB"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 403)
        self.assertEqual(data["codigo"], "origem_diferente")
        self.assertEqual(self.service.store.counts("PDV")[STATUS_FILA], 0)
        self.assertEqual(self.service.store.counts("HUB")[STATUS_FILA], 0)

    def test_origem_no_corpo_batendo_com_a_credencial_e_aceita(self):
        code, _ = self.request(
            "POST",
            "/v2/messages",
            {"id_externo": "x", "destino": NUMERO, "mensagem": "oi", "origem": "pdv"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 202)

    def test_pedido_repetido_achata_no_mesmo_identificador(self):
        _, primeiro = self.pedir(chave="mesma")
        _, segundo = self.pedir(chave="mesma")
        self.assertTrue(primeiro["criado"])
        self.assertFalse(segundo["criado"])
        self.assertEqual(primeiro["pedido"]["id_mensagem"], segundo["pedido"]["id_mensagem"])
        self.assertEqual(self.service.store.counts("PDV")[STATUS_FILA], 1)

    def test_pedido_invalido_devolve_400(self):
        self.assertEqual(self.pedir(numero="12")[0], 400)
        self.assertEqual(self.pedir(texto="x" * 481)[0], 400)
        self.assertEqual(self.pedir(externo="")[0], 400)

    def test_corpo_vazio_ou_enorme_ou_fora_de_json(self):
        vazio = self.request("POST", "/v2/messages", None, credencial=self.pdv, raw=b"")
        self.assertEqual(vazio[0], 400)
        lista = self.request("POST", "/v2/messages", None, credencial=self.pdv, raw=b"[1,2]")
        self.assertEqual(lista[0], 400)
        enorme = self.request(
            "POST", "/v2/messages", None, credencial=self.pdv, raw=b"x" * (70 * 1024)
        )
        self.assertEqual(enorme[0], 400)

    def test_cota_diaria_e_por_origem(self):
        self.service.config.daily_limit_per_origin = 1
        self.assertEqual(self.pedir(externo="um", chave="um")[0], 202)
        code, data = self.pedir(externo="dois", chave="dois")
        self.assertEqual(code, 429)
        self.assertIn("cota", data["error"])
        self.assertEqual(
            self.request(
                "POST",
                "/v2/messages",
                {"id_externo": "hub-1", "destino": OUTRO_NUMERO, "mensagem": "oi do hub"},
                credencial=self.hub,
            )[0],
            202,
        )

    # -------------------------------------------------------------------- ler

    def test_le_o_pedido_por_id_e_por_id_externo(self):
        _, criado = self.pedir(externo="consulta-1")
        identificador = criado["pedido"]["id_mensagem"]
        code, data = self.request("GET", f"/v2/messages/{identificador}", credencial=self.pdv)
        self.assertEqual(code, 200)
        self.assertEqual(data["pedido"]["id_externo"], "consulta-1")
        code, data = self.request("GET", "/v2/messages?id_externo=consulta-1", credencial=self.pdv)
        self.assertEqual(code, 200)
        self.assertEqual(data["pedido"]["id_mensagem"], identificador)

    def test_credencial_do_outro_produto_nao_ve_nada(self):
        _, criado = self.pedir(externo="so-do-pdv")
        identificador = criado["pedido"]["id_mensagem"]
        self.assertEqual(
            self.request("GET", f"/v2/messages/{identificador}", credencial=self.hub)[0], 404
        )
        self.assertEqual(
            self.request("GET", "/v2/messages?id_externo=so-do-pdv", credencial=self.hub)[0], 404
        )
        _, eventos_hub = self.request("GET", "/v2/events", credencial=self.hub)
        self.assertEqual(eventos_hub["eventos"], [])

    def test_leitura_sem_id_externo_e_pedido_inexistente(self):
        self.assertEqual(self.request("GET", "/v2/messages", credencial=self.pdv)[0], 400)
        self.assertEqual(self.request("GET", "/v2/messages/ninguem", credencial=self.pdv)[0], 404)

    def test_trilha_de_notificacoes_anda_por_cursor(self):
        self.ligar_meio("PDV")
        self.pedir(externo="trilha")
        self.service.dispatcher.run_once()
        _, primeira = self.request("GET", "/v2/events", credencial=self.pdv)
        self.assertEqual([item["evento"] for item in primeira["eventos"]], ["criada", "enviada"])
        cursor = primeira["cursor"]
        _, depois = self.request("GET", f"/v2/events?from={cursor}", credencial=self.pdv)
        self.assertEqual(depois["eventos"], [])
        self.assertEqual(depois["cursor"], cursor)
        _, com_limite = self.request("GET", "/v2/events?from=0&limit=1", credencial=self.pdv)
        self.assertEqual(len(com_limite["eventos"]), 1)
        _, sem_numero = self.request("GET", "/v2/events?from=abc", credencial=self.pdv)
        self.assertEqual(len(sem_numero["eventos"]), 2)

    # ------------------------------------------------------------- assinatura

    def test_sem_assinatura_o_pedido_nao_entra(self):
        code, data = self.request(
            "POST",
            "/v2/messages",
            {"id_externo": "x", "destino": NUMERO, "mensagem": "oi"},
            credencial=self.pdv,
            sign=False,
        )
        self.assertEqual(code, 401)
        self.assertEqual(data["error"], "assinatura ausente")
        self.assertEqual(self.service.store.counts("PDV")[STATUS_FILA], 0)

    def test_assinatura_errada_expirada_ou_curta_nao_entra(self):
        corpo = {"id_externo": "x", "destino": NUMERO, "mensagem": "oi"}
        code, data = self.request(
            "POST", "/v2/messages", corpo, credencial=self.pdv, signature="0" * 64
        )
        self.assertEqual(code, 401)
        self.assertEqual(data["error"], "assinatura invalida")
        code, data = self.request(
            "POST", "/v2/messages", corpo, credencial=self.pdv, timestamp=int(time.time()) - 3600
        )
        self.assertEqual(code, 401)
        self.assertEqual(data["error"], "assinatura expirada")
        code, data = self.request("POST", "/v2/messages", corpo, credencial=self.pdv, nonce="curto")
        self.assertEqual(code, 401)
        self.assertEqual(data["error"], "assinatura invalida")
        code, data = self.request(
            "POST", "/v2/messages", corpo, credencial=self.pdv, timestamp="ontem"
        )
        self.assertEqual(code, 401)
        self.assertEqual(self.service.store.counts("PDV")[STATUS_FILA], 0)

    def test_pedido_capturado_nao_se_repete(self):
        corpo = {"id_externo": "repetido", "destino": NUMERO, "mensagem": "oi"}
        nonce_unico = secrets.token_hex(8)
        primeiro = self.request(
            "POST", "/v2/messages", corpo, credencial=self.pdv, nonce=nonce_unico
        )
        segundo = self.request(
            "POST", "/v2/messages", corpo, credencial=self.pdv, nonce=nonce_unico
        )
        self.assertEqual(primeiro[0], 202)
        self.assertEqual(segundo[0], 401)
        self.assertEqual(segundo[1]["error"], "pedido repetido")

    def test_assinatura_pode_ser_dispensada_na_configuracao(self):
        self.service.config.require_signed_requests = False
        code, _ = self.request(
            "POST",
            "/v2/messages",
            {"id_externo": "livre", "destino": NUMERO, "mensagem": "oi"},
            credencial=self.pdv,
            sign=False,
        )
        self.assertEqual(code, 202)

    def test_assinatura_feita_com_segredo_errado_nao_entra(self):
        class OutroSegredo:
            def __init__(self, token: str):
                self.token = token
                self.secret = "segredo-que-nao-foi-este"

        code, data = self.request(
            "POST",
            "/v2/messages",
            {"id_externo": "x", "destino": NUMERO, "mensagem": "oi"},
            credencial=OutroSegredo(self.pdv.token),
        )
        self.assertEqual(code, 401)
        self.assertEqual(data["error"], "assinatura invalida")
        self.assertEqual(self.service.store.counts("PDV")[STATUS_FILA], 0)

    def test_girar_a_credencial_derruba_o_pedido_do_produto(self):
        self.service.credentials.issue("PDV")
        code, data = self.pedir(externo="depois-do-giro")
        self.assertEqual(code, 401)
        self.assertIn("credencial", data["error"])
        self.assertEqual(self.service.store.counts("PDV")[STATUS_FILA], 0)

    # --------------------------------------------------------- decisao humana

    def test_envio_em_duvida_conferido_pelo_produto(self):
        self.meio.script("incerto")
        self.ligar_meio("PDV")
        _, criado = self.pedir(externo="duvida")
        identificador = criado["pedido"]["id_mensagem"]
        self.service.dispatcher.run_once()
        self.assertEqual(self.service.store.get("PDV", identificador).status, STATUS_INCERTO)
        code, data = self.request(
            "POST",
            f"/v2/messages/{identificador}/confirm",
            {"status": "entregue"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 200)
        self.assertEqual(data["pedido"]["status"], STATUS_ENTREGUE)
        code, _ = self.request(
            "POST",
            f"/v2/messages/{identificador}/confirm",
            {"status": "entregue"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 409)
        self.assertEqual(len(self.meio.submitted), 1)

    def test_confirmar_o_que_nao_estava_em_duvida(self):
        self.ligar_meio("PDV")
        _, criado = self.pedir(externo="saiu-bem")
        identificador = criado["pedido"]["id_mensagem"]
        self.service.dispatcher.run_once()
        self.assertEqual(
            self.request(
                "POST",
                f"/v2/messages/{identificador}/confirm",
                {"status": "entregue"},
                credencial=self.pdv,
            )[0],
            409,
        )
        # uma decisao que nao existe so chega a ser recusada num pedido em duvida
        self.meio.script("incerto")
        _, duvida = self.pedir(externo="ficou-em-duvida")
        self.service.dispatcher.run_once()
        id_duvida = duvida["pedido"]["id_mensagem"]
        code, data = self.request(
            "POST",
            f"/v2/messages/{id_duvida}/confirm",
            {"status": "quizemandou"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 400)
        self.assertIn("entregue ou falhou", data["error"])
        self.assertEqual(
            self.request(
                "POST",
                "/v2/messages/nao-existe/confirm",
                {"status": "entregue"},
                credencial=self.pdv,
            )[0],
            404,
        )
        self.assertEqual(
            self.request(
                "POST", f"/v2/messages/{identificador}/confirm", {"status": "entregue"}, credencial=self.hub
            )[0],
            404,
        )

    # -------------------------------------------------------------- respostas

    def test_resposta_com_um_pedido_so_volta_pelo_contrato(self):
        self.ligar_meio("PDV")
        _, criado = self.pedir(externo="resposta-1")
        self.service.dispatcher.run_once()
        self.meio.receive(NUMERO, "pode deixar")
        self.service.dispatcher.drain_inbound()
        _, respostas = self.request("GET", "/v2/replies", credencial=self.pdv)
        self.assertEqual(respostas["respostas"][0]["mensagem"], "pode deixar")
        self.assertEqual(
            respostas["respostas"][0]["id_mensagem"], criado["pedido"]["id_mensagem"]
        )
        _, do_hub = self.request("GET", "/v2/replies", credencial=self.hub)
        self.assertEqual(do_hub["respostas"], [])

    def test_resposta_ambigua_fica_por_identificar_ate_o_produto_assumir(self):
        self.ligar_meio("PDV")
        nota_a = self.pedir(externo="nota-a", chave="a")[1]["pedido"]["id_mensagem"]
        nota_b = self.pedir(externo="nota-b", chave="b")[1]["pedido"]["id_mensagem"]
        self.service.dispatcher.run_once()
        self.service.dispatcher.run_once()
        self.meio.receive(NUMERO, "ok")
        self.service.dispatcher.drain_inbound()
        _, proprias = self.request("GET", "/v2/replies", credencial=self.pdv)
        self.assertEqual(proprias["respostas"], [])
        _, saude = self.request("GET", "/v2/health")
        self.assertEqual(saude["respostas_por_identificar"], 1)
        pendente = self.service.store.pending_inbound()[0]
        code, data = self.request(
            "POST",
            f"/v2/replies/{pendente.id}/assign",
            {"id_externo": "nota-b"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 200)
        self.assertEqual(data["resposta"]["id_mensagem"], nota_b)
        self.assertNotEqual(data["resposta"]["id_mensagem"], nota_a)
        code, _ = self.request(
            "POST",
            f"/v2/replies/{pendente.id}/assign",
            {"id_externo": "nota-b"},
            credencial=self.pdv,
        )
        self.assertEqual(code, 409)
        _, depois = self.request("GET", "/v2/replies?limit=abc", credencial=self.pdv)
        self.assertEqual(len(depois["respostas"]), 1)

    def test_assumir_resposta_que_nao_existe_ou_sem_pedido(self):
        self.assertEqual(
            self.request(
                "POST", "/v2/replies/nao-existe/assign", {"id_externo": "x"}, credencial=self.pdv
            )[0],
            404,
        )
        self.assertEqual(
            self.request(
                "POST",
                "/v2/replies/qualquer/assign",
                {"id_externo": "sem-pedido"},
                credencial=self.pdv,
            )[0],
            404,
        )
        self.assertEqual(
            self.request(
                "POST", "/v2/replies/qualquer/assign", {"id_externo": ""}, credencial=self.pdv
            )[0],
            400,
        )

    def test_auditoria_local_nao_grava_conteudo(self):
        self.ligar_meio("PDV")
        self.pedir(externo="lgpd")
        self.service.dispatcher.run_once()
        linhas = self.service.audit.entries(10)
        self.assertTrue(linhas)
        texto = json.dumps(linhas, ensure_ascii=False)
        self.assertNotIn(NUMERO, texto)
        self.assertNotIn(CONTEUDO, texto)
        for linha in linhas:
            self.assertNotIn("number", linha)
            self.assertNotIn("message", linha)


if __name__ == "__main__":
    unittest.main()
