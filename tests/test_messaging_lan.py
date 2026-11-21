"""Testes do motorista de rede local (celular pareado pelo Wi-Fi da loja).

Nenhum teste depende da internet, do celular de verdade nem do chip da operadora:
a soquete entra por fabrica e o grupo de ponta a ponta sobe um servidor real em
127.0.0.1 que faz o papel do aplicativo Android - abre o envelope com a chave
privada do celular, confere a etiqueta de autenticacao e devolve o ACK cifrado
pelo mesmo caminho, nos moldes de ``tests/test_e2e_sms.py``.

O que estes testes amarram, de proposito:

* com o meio desligado, nenhuma linha do modulo toca em soquete, IPv4 ou UDP - e
  o gravador enche quando o caminho e exercitado por engano, senao seria verde de
  enfeite;
* ``recusado`` so aparece enquanto nada chegou ao radio; assim que o pedido e
  empurrado na conexao e a resposta nao volta, o resultado e ``incerto``;
* um pedido ``incerto`` nunca e reenviado por este motorista, nem quando existe
  um endereco conhecido: reenviar duplicaria o SMS e a cobranca do lojista;
* o numero do cliente e o texto so existem dentro do envelope fechado na chave
  publica do celular, e o campo ``origem`` chega no comando e la dentro;
* um texto que o UTF-8 nao consegue escrever (o \\ud800 que um JSON devolve) e
  recusado antes de abrir soquete: maquiaria o pedido com outra mensagem.
"""

from __future__ import annotations

import base64
import json
import socket
import struct
import threading
import unittest
from contextlib import contextmanager

from gaspar.messaging.model import Message
from gaspar.messaging.transport import InboundReply
from gaspar.messaging.transports import android_lan
from gaspar.messaging.transports.android_lan import (
    ESTADO_ENTREGUE,
    ESTADO_FALHOU,
    PORTA_COMANDO,
    AndroidLanTransportDriver,
    LanSettings,
    _ler_ack,
)
from gaspar.sms import crypto, e2e, protocol

NUMERO = "11988887777"
TEXTO = "Retire sua encomenda"
CHAVE_PDV = base64.b64encode(b"p" * 32).decode("ascii")
CHAVE_HUB = base64.b64encode(b"h" * 32).decode("ascii")
CHAVE_ALHEIA = base64.b64encode(b"x" * 32).decode("ascii")


def pedido(**campo) -> Message:
    dados = {
        "id": "m-1",
        "origem": "PDV",
        "external_id": "pdv-100",
        "idempotency_key": "k-1",
        "recipient": NUMERO,
        "text": TEXTO,
        "created_at": 1000.0,
    }
    dados.update(campo)
    return Message(**dados)


class Alarme(Exception):
    """Alguem tentou abrir rede enquanto o meio nao tinha que abrir."""


@contextmanager
def sem_rede():
    """Trava soquete, IPv4, resolucao de nome e descoberta; devolve as tentativas."""
    tentativas: list[str] = []

    def travar(nome: str):
        def alarme(*args, **kwargs):
            tentativas.append(nome)
            raise Alarme(nome)

        return alarme

    originais = {
        (socket, "create_connection"): socket.create_connection,
        (socket, "socket"): socket.socket,
        (socket, "getaddrinfo"): socket.getaddrinfo,
        (android_lan, "discover"): android_lan.discover,
    }
    socket.create_connection = travar("socket.create_connection")
    socket.socket = travar("socket.socket")
    socket.getaddrinfo = travar("socket.getaddrinfo")
    android_lan.discover = travar("descoberta")
    try:
        yield tentativas
    finally:
        for (alvo, nome), valor in originais.items():
            setattr(alvo, nome, valor)


class Aparelho:
    """Par de chaves ponta a ponta de um celular, no formato que o app guarda."""

    def __init__(self) -> None:
        self.privada, publica = e2e.generate_keypair()
        self.publica = base64.b64encode(publica).decode("ascii")

    def abrir(self, envelope: str, etiqueta: str) -> dict:
        corpo = e2e.open_sealed(self.privada, envelope, etiqueta.encode("ascii"))
        return json.loads(corpo.decode("utf-8"))


APARELHO = Aparelho()


def ajustes(**campo) -> LanSettings:
    dados = {
        "ligada": True,
        "host": "192.168.0.50",
        "segredo": CHAVE_PDV,
        "chave_celular": APARELHO.publica,
        "base_url": "http://127.0.0.1:8765",
    }
    dados.update(campo)
    return LanSettings(**dados)


class SoqueteCurta:
    """Ponta local de mentira: grava os bytes, devolve o que estiver escalado."""

    def __init__(self, respostas: list[bytes] | None = None, erro_envio: Exception | None = None):
        self.enviados = bytearray()
        self._respostas = b"".join(respostas or [])
        self._posicao = 0
        self.erro_envio = erro_envio
        self.encerrou = False
        self.feitou = False
        self.prazos: list[float] = []

    def sendall(self, dados: bytes) -> None:
        if self.erro_envio is not None:
            raise self.erro_envio
        self.enviados.extend(dados)

    def shutdown(self, _como: int) -> None:
        self.feitou = True

    def settimeout(self, prazo: float) -> None:
        self.prazos.append(prazo)

    def recv(self, tamanho: int) -> bytes:
        pedaco = self._respostas[self._posicao : self._posicao + tamanho]
        self._posicao += len(pedaco)
        return pedaco

    def close(self) -> None:
        self.encerrou = True


def quadro_de(payload: dict, chave: bytes) -> bytes:
    return protocol.frame(crypto.encrypt(chave, json.dumps(payload).encode("utf-8")))


class Fabrica:
    """Monta o motorista com a soquete e a descoberta de mentirinha."""

    def __init__(self) -> None:
        self.tentativas: list[tuple[str, int]] = []
        self.soquetes: list[SoqueteCurta] = []
        self._pendentes: list[SoqueteCurta | Exception] = []

    def empilhar(self, *respostas: SoqueteCurta | Exception) -> None:
        self._pendentes.extend(respostas)

    def abrir(self, endereco, timeout=None) -> SoqueteCurta:
        self.tentativas.append((str(endereco[0]), int(endereco[1])))
        if self._pendentes:
            item = self._pendentes.pop(0)
        else:
            item = SoqueteCurta()
        if isinstance(item, Exception):
            raise item
        self.soquetes.append(item)
        return item

    @property
    def ultimo(self) -> SoqueteCurta:
        return self.soquetes[-1]

    def comando(self, indice: int = 0, chave: bytes | None = None) -> dict:
        bruto = bytes(self.soquetes[indice].enviados)
        corpo = crypto.decrypt(chave or crypto.key_from_base64(CHAVE_PDV), bruto[4:])
        return json.loads(corpo.decode("utf-8"))


def motorista(opcoes: LanSettings | None = None, **kw) -> tuple[AndroidLanTransportDriver, Fabrica]:
    fabrica = Fabrica()
    opcoes = opcoes if opcoes is not None else ajustes()
    motorista_ = AndroidLanTransportDriver(
        opcoes,
        soquete_factory=fabrica.abrir,
        descoberta=kw.pop("descoberta", lambda: [("192.168.0.77", PORTA_COMANDO)]),
        **kw,
    )
    return motorista_, fabrica


# ------------------------------------------------------------------ configura


class AjustesTeste(unittest.TestCase):
    def test_desligado_e_sem_pareamento_por_padrao(self):
        padrao = LanSettings()
        self.assertFalse(padrao.ligada)
        self.assertEqual(padrao.porta, PORTA_COMANDO)
        self.assertTrue(padrao.exigir_e2e)
        self.assertTrue(padrao.descobrir)
        self.assertFalse(padrao.tem_pareamento())
        self.assertEqual(padrao.segredo, "")

    def test_a_porta_o_prazo_e_a_base_se_ajustam_ao_uso(self):
        opcoes = LanSettings(porta=0, timeout=9999, espera_ack=-1, base_url="http://loja:8765///")
        self.assertEqual(opcoes.porta, PORTA_COMANDO)
        self.assertEqual(opcoes.timeout, 120.0)
        self.assertEqual(opcoes.espera_ack, 0.1)
        self.assertEqual(opcoes.base_url, "http://loja:8765")

    def test_o_segredo_de_cada_origem_manda_e_o_geral_serve_de_reserva(self):
        opcoes = LanSettings(segredo=CHAVE_PDV, segredos_por_origem={"HUB": CHAVE_HUB, "PDV": ""})
        self.assertEqual(opcoes.segredo_para("HUB"), CHAVE_HUB)
        self.assertEqual(opcoes.segredo_para("pdv"), CHAVE_PDV)
        self.assertEqual(opcoes.segredo_para("NADA"), "")

    def test_origem_desconhecida_nao_entra_na_lista(self):
        opcoes = LanSettings(segredos_por_origem={"HUB": CHAVE_HUB, "LOJA": CHAVE_ALHEIA, "PDV": "  "})
        self.assertEqual(sorted(opcoes.segredos_por_origem), ["HUB"])

    def test_as_chaves_vao_da_origem_para_o_pareamento_unico(self):
        opcoes = LanSettings(segredo=CHAVE_PDV, segredos_por_origem={"HUB": CHAVE_HUB})
        self.assertEqual(opcoes.chaves(), [("HUB", CHAVE_HUB), ("", CHAVE_PDV)])

    def test_a_descricao_nunca_devolve_o_segredo(self):
        descricao = ajustes().to_dict()
        serializado = json.dumps(descricao, ensure_ascii=False)
        self.assertNotIn(CHAVE_PDV, serializado)
        self.assertNotIn(CHAVE_HUB, serializado)
        self.assertTrue(descricao["pareado"])
        self.assertEqual(descricao["porta"], PORTA_COMANDO)
        self.assertIn("celular", descricao)


# --------------------------------------------------------------------- health


class SaudeTeste(unittest.TestCase):
    def test_desligado_nem_chega_perto_da_rede(self):
        with sem_rede() as tentativas:
            motorista_ = AndroidLanTransportDriver(ajustes(ligada=False))
            self.assertFalse(motorista_.health().available)
            self.assertEqual(motorista_.submit(pedido()).outcome, "indisponivel")
            self.assertEqual(tentativas, [])

    def test_ligado_mas_sem_pareamento_tambem_nao_abre_rede(self):
        with sem_rede() as tentativas:
            motorista_ = AndroidLanTransportDriver(ajustes(segredo="", segredos_por_origem={}))
            self.assertFalse(motorista_.health().available)
            self.assertEqual(motorista_.submit(pedido()).outcome, "indisponivel")
            self.assertEqual(tentativas, [])

    def test_a_health_nao_faz_descoberta_mesmo_ligada(self):
        """Disponivel por configuracao nao e promessa de que o celular esta acordado."""
        chamadas: list[int] = []

        def descobrir():
            chamadas.append(1)
            return []

        motorista_, _ = motorista(ajustes(host=""), descoberta=descobrir)
        with sem_rede() as tentativas:
            self.assertTrue(motorista_.health().available)
            self.assertEqual(chamadas, [])
            self.assertEqual(tentativas, [])
        # e o envio, esse sim, pergunta na rede onde o celular esta
        self.assertEqual(motorista_._enderecos(), [])
        self.assertEqual(chamadas, [1])

    def test_health_diz_o_que_falta_sem_abrir_nada(self):
        faltas = [
            (LanSettings(ligada=True), "celular sem segredo de pareamento"),
            (LanSettings(ligada=True, segredo=CHAVE_PDV, host="", descobrir=False), "nenhum endereco"),
            (
                LanSettings(ligada=True, segredo=CHAVE_PDV, chave_celular=""),
                "sem chave de criptografia",
            ),
        ]
        for opcoes, motivo in faltas:
            with self.subTest(motivo=motivo):
                checagem = AndroidLanTransportDriver(opcoes).health()
                self.assertFalse(checagem.available)
                self.assertIn(motivo, checagem.reason)

    def test_ligado_e_pareado_diz_disponivel(self):
        checagem = AndroidLanTransportDriver(ajustes()).health()
        self.assertTrue(checagem.available)
        self.assertEqual(checagem.detail, "android-lan")

    def test_descoberta_desligada_nao_busca_o_celular(self):
        motorista_, _ = motorista(ajustes(host="", descobrir=False), descoberta=lambda: [])
        self.assertEqual(motorista_._enderecos(), [])

    def test_a_descoberta_e_o_endereco_vem_do_celular_encontrado(self):
        chamada: list[int] = []

        def descobrir():
            chamada.append(1)
            return [("192.168.0.9", 49998), ("", 49998), ("192.168.0.10", 0)]

        motorista_, _ = motorista(ajustes(host=""), descoberta=descobrir)
        self.assertEqual(motorista_._enderecos(), [("192.168.0.9", 49998)])
        self.assertEqual(chamada, [1])

    def test_descoberta_que_explode_vira_endereco_vazio(self):
        def descobrir():
            raise OSError("sem broadcast")

        motorista_, _ = motorista(ajustes(host=""), descoberta=descobrir)
        self.assertEqual(motorista_._enderecos(), [])

    def test_a_roda_de_enderecos_tem_teto(self):
        achados = [(f"192.168.0.{n}", PORTA_COMANDO) for n in range(1, 9)]
        motorista_, _ = motorista(ajustes(host=""), descoberta=lambda: achados)
        self.assertEqual(len(motorista_._enderecos()), 3)

    def test_meio_desligado_recusa_sem_tentar_nada(self):
        motorista_, fabrica = motorista(ajustes(ligada=False))
        self.assertEqual(motorista_.submit(pedido()).outcome, "indisponivel")
        self.assertEqual(fabrica.tentativas, [])


# ----------------------------------------------------------------------- envio


class EnvioTeste(unittest.TestCase):
    def test_o_numero_e_o_texto_so_existem_dentro_do_envelope(self):
        resposta = quadro_de({"ok": True, "id": "m-1", "status": "aceito"}, crypto.key_from_base64(CHAVE_PDV))
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([resposta]))
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "aceito")
        comando = fabrica.comando()
        self.assertEqual(comando["action"], "send_sms")
        self.assertEqual(comando["origem"], "PDV")
        self.assertEqual(comando["id"], "m-1")
        self.assertEqual(comando["base"], "http://127.0.0.1:8765")
        self.assertNotIn("number", comando)
        self.assertNotIn("message", comando)
        self.assertNotIn(NUMERO, json.dumps(comando))
        self.assertNotIn(TEXTO, json.dumps(comando))
        corpo = APARELHO.abrir(comando["envelope"], "m-1")
        self.assertEqual(corpo["number"], NUMERO)
        self.assertEqual(corpo["message"], TEXTO)
        self.assertEqual(corpo["origem"], "PDV")
        self.assertEqual(corpo["id_externo"], "pdv-100")

    def test_o_quadro_comeca_com_o_tamanho_e_a_espera_do_ack_e_curta(self):
        resposta = quadro_de({"ok": True, "id": "m-1"}, crypto.key_from_base64(CHAVE_PDV))
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([resposta]))
        motorista_.submit(pedido())
        bruto = bytes(fabrica.ultimo.enviados)
        self.assertEqual(struct.unpack(">I", bruto[:4])[0], len(bruto) - 4)
        self.assertIn(0.8, fabrica.ultimo.prazos)
        self.assertTrue(fabrica.ultimo.feitou)
        self.assertTrue(fabrica.ultimo.encerrou)

    def test_sem_origem_nao_ha_pedido(self):
        motorista_, fabrica = motorista()
        self.assertEqual(motorista_.submit(pedido(origem="LOJA")).outcome, "recusado")
        self.assertEqual(fabrica.tentativas, [])

    def test_sem_pareamento_da_origem_o_meio_indisponivel(self):
        motorista_, fabrica = motorista(ajustes(segredo="", segredos_por_origem={"HUB": CHAVE_HUB}))
        resultado = motorista_.submit(pedido(origem="PDV"))
        self.assertEqual(resultado.outcome, "indisponivel")
        self.assertEqual(fabrica.tentativas, [])

    def test_segredo_torto_indisponivel_em_vez_de_estouro(self):
        motorista_, fabrica = motorista(ajustes(segredo="nao e base64 !!!"))
        self.assertEqual(motorista_.submit(pedido()).outcome, "indisponivel")
        self.assertEqual(fabrica.tentativas, [])

    def test_sem_chave_do_celular_a_saida_e_recusada(self):
        motorista_, fabrica = motorista(ajustes(chave_celular=""))
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "recusado")
        self.assertIn("pareie o celular", resultado.reason)
        self.assertEqual(fabrica.tentativas, [])

    def test_chave_torta_recusa_antes_de_abrir_rede(self):
        motorista_, fabrica = motorista(ajustes(chave_celular="AAAA"))
        self.assertEqual(motorista_.submit(pedido()).outcome, "recusado")
        self.assertEqual(fabrica.tentativas, [])

    def test_o_modo_antigo_so_vale_com_a_exigencia_desligada(self):
        resposta = quadro_de({"ok": True, "id": "m-1"}, crypto.key_from_base64(CHAVE_PDV))
        motorista_, fabrica = motorista(ajustes(chave_celular="", exigir_e2e=False))
        fabrica.empilhar(SoqueteCurta([resposta]))
        self.assertEqual(motorista_.submit(pedido()).outcome, "aceito")
        comando = fabrica.comando()
        self.assertEqual(comando["number"], NUMERO)
        self.assertEqual(comando["message"], TEXTO)
        self.assertEqual(comando["origem"], "PDV")
        self.assertNotIn("envelope", comando)

    def test_celular_recusa_e_o_motivo_chega_na_fila(self):
        resposta = quadro_de(
            {"ok": False, "error": "sem permissao de SMS"}, crypto.key_from_base64(CHAVE_PDV)
        )
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([resposta]))
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "recusado")
        self.assertIn("sem permissao", resultado.reason)

    def test_a_etiqueta_atrasada_no_celular_vira_recusa_diagnostica(self):
        resposta = quadro_de({"ok": False, "error": "pedido repetido"}, crypto.key_from_base64(CHAVE_PDV))
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([resposta]))
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "recusado")
        self.assertIn("sequencia", resultado.reason)

    def test_o_celular_que_ja_viu_o_pedido_confirma_sem_duplicar(self):
        resposta = quadro_de(
            {"ok": True, "id": "m-1", "status": "repetido"}, crypto.key_from_base64(CHAVE_PDV)
        )
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([resposta]))
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "aceito")
        self.assertIn("ja tinha recebido", resultado.reason)
        self.assertEqual(resultado.reference, "m-1")

    def test_celular_inalcancavel_recusa_e_tenta_o_proximo_endereco(self):
        motorista_, fabrica = motorista(ajustes(host=""), descoberta=lambda: [
            ("192.168.0.1", PORTA_COMANDO),
            ("192.168.0.2", PORTA_COMANDO),
        ])
        respondeu = quadro_de({"ok": True, "id": "m-1"}, crypto.key_from_base64(CHAVE_PDV))
        fabrica.empilhar(ConnectionRefusedError("negado"), SoqueteCurta([respondeu]))
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "aceito")
        self.assertEqual([h for h, _ in fabrica.tentativas], ["192.168.0.1", "192.168.0.2"])

    def test_sem_celular_na_rede_nada_e_enviado(self):
        motorista_, fabrica = motorista(ajustes(host=""), descoberta=lambda: [])
        resultado = motorista_.submit(pedido())
        self.assertEqual(resultado.outcome, "recusado")
        self.assertIn("celular nao encontrado", resultado.reason)
        self.assertEqual(fabrica.tentativas, [])

    def test_queda_durante_o_envio_deixa_duvida(self):
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta(erro_envio=OSError("soquete fechada")))
        self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")

    def test_sem_resposta_depois_de_empurrar_deixa_duvida(self):
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([]))
        self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")

    def test_resposta_torta_deixa_duvida_e_nao_estoura(self):
        chave = crypto.key_from_base64(CHAVE_PDV)
        motorista_, fabrica = motorista()
        fabrica.empilhar(SoqueteCurta([protocol.frame(crypto.encrypt(chave, b"[1, 2, 3]"))]))
        self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")

    def test_a_duvida_encerra_a_roda_de_enderecos(self):
        """Caiu no meio de um endereco: nao se empurra o mesmo pedido no proximo."""
        motorista_, fabrica = motorista(
            ajustes(host=""),
            descoberta=lambda: [("192.168.0.50", PORTA_COMANDO), ("192.168.0.51", PORTA_COMANDO)],
        )
        fabrica.empilhar(SoqueteCurta([]))
        self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")
        self.assertEqual([h for h, _ in fabrica.tentativas], ["192.168.0.50"])

    def test_o_caminho_de_volta_e_por_comprovante_e_nao_por_resposta(self):
        motorista_, _ = motorista()
        self.assertFalse(motorista_.supports_reception)
        self.assertTrue(motorista_.supports_delivery_report)
        self.assertEqual(motorista_.poll_inbound(), [])
        self.assertIsNone(
            motorista_.correlate(InboundReply("android-lan", NUMERO, "oi", 1000.0), [])
        )


class SequenciaTeste(unittest.TestCase):
    def ack_ok(self) -> bytes:
        return quadro_de({"ok": True, "id": "m-1"}, crypto.key_from_base64(CHAVE_PDV))

    def test_a_sequencia_sobe_a_cada_pedido(self):
        motorista_, fabrica = motorista()
        for indice in range(3):
            fabrica.empilhar(SoqueteCurta([self.ack_ok()]))
            motorista_.submit(pedido(id=f"m-{indice}"))
        sequencias = [fabrica.comando(i)["seq"] for i in range(3)]
        self.assertEqual(sequencias, [1, 2, 3])

    def test_quando_o_pareamento_manda_a_contagem_ele_manda(self):
        contador = iter([41, 42, 43])
        motorista_, fabrica = motorista(sequencia=lambda: next(contador))
        for indice in range(2):
            fabrica.empilhar(SoqueteCurta([self.ack_ok()]))
            motorista_.submit(pedido(id=f"m-{indice}"))
        self.assertEqual([fabrica.comando(i)["seq"] for i in range(2)], [41, 42])

    def test_contador_de_fora_torto_nao_para_o_canal(self):
        for valor in (0, -3, None, "abc"):
            with self.subTest(valor=valor):
                motorista_, fabrica = motorista(sequencia=lambda v=valor: v)
                fabrica.empilhar(SoqueteCurta([self.ack_ok()]))
                self.assertEqual(motorista_.submit(pedido()).outcome, "aceito")
                self.assertGreaterEqual(fabrica.comando()["seq"], 1)


# ---------------------------------------------------------------- isolamento


class IsolamentoTeste(unittest.TestCase):
    def test_cada_origem_fala_com_o_proprio_segredo(self):
        resposta = quadro_de({"ok": True, "id": "m-1"}, crypto.key_from_base64(CHAVE_HUB))
        opcoes = ajustes(segredo="", segredos_por_origem={"PDV": CHAVE_PDV, "HUB": CHAVE_HUB})
        motorista_, fabrica = motorista(opcoes)
        fabrica.empilhar(SoqueteCurta([resposta]))
        resultado = motorista_.submit(pedido(origem="HUB", id="m-9"))
        self.assertEqual(resultado.outcome, "aceito")
        comando = fabrica.comando(0, crypto.key_from_base64(CHAVE_HUB))
        self.assertEqual(comando["origem"], "HUB")
        self.assertEqual(comando["id"], "m-9")
        corpo = APARELHO.abrir(comando["envelope"], "m-9")
        self.assertEqual(corpo["origem"], "HUB")

    def test_o_comprovante_de_um_nao_limpa_o_outro(self):
        motorista_, _ = motorista()
        motorista_.registrar_comprovante("m-1", "entregue")
        self.assertEqual(motorista_.comprovante_de("m-1"), ESTADO_ENTREGUE)
        self.assertEqual(motorista_.comprovante_de("m-2"), "")
        self.assertIsNone(motorista_.resolve_uncertain(pedido(id="m-2")))


# ---------------------------------------------------------------- comprovantes


class ComprovanteTeste(unittest.TestCase):
    def blob(self, corpo: dict, segredo: str = CHAVE_PDV) -> str:
        cifrado = crypto.encrypt(crypto.key_from_base64(segredo), json.dumps(corpo).encode("utf-8"))
        return base64.b64encode(cifrado).decode("ascii")

    def test_o_estado_do_app_vira_estado_da_fila(self):
        motorista_, _ = motorista()
        for bruto, esperado in (
            ({"id": "a", "status": "sent"}, "enviado"),
            ({"id": "b", "status": "delivered"}, ESTADO_ENTREGUE),
            ({"id": "c", "status": "failed"}, ESTADO_FALHOU),
        ):
            self.assertEqual(motorista_.abrir_comprovante(self.blob(bruto)), bruto["id"])
            self.assertEqual(motorista_.comprovante_de(bruto["id"]), esperado)

    def test_estado_desconhecido_nao_entra(self):
        motorista_, _ = motorista()
        self.assertFalse(motorista_.registrar_comprovante("m-1", "talvez"))
        self.assertFalse(motorista_.registrar_comprovante("", "entregue"))
        self.assertEqual(motorista_.comprovante_de("m-1"), "")

    def test_blob_de_outro_celular_e_descartado(self):
        motorista_, _ = motorista(ajustes(segredo=CHAVE_ALHEIA))
        self.assertEqual(motorista_.abrir_comprovante(self.blob({"id": "m-1", "status": "sent"})), "")
        self.assertEqual(motorista_.comprovante_de("m-1"), "")

    def test_o_comprovante_chega_pelo_segredo_da_origem(self):
        opcoes = ajustes(segredo="", segredos_por_origem={"HUB": CHAVE_HUB})
        motorista_, _ = motorista(opcoes)
        abertos = motorista_.abrir_comprovante(self.blob({"id": "m-7", "status": "delivered"}, CHAVE_HUB))
        self.assertEqual(abertos, "m-7")
        self.assertEqual(motorista_.comprovante_de("m-7"), ESTADO_ENTREGUE)

    def test_corpo_torto_nao_estoura(self):
        motorista_, _ = motorista()
        for corpo in ("", "   ", "nao-e-base64!!", base64.b64encode(b"aleatorio").decode("ascii")):
            self.assertEqual(motorista_.abrir_comprovante(corpo), "")

    def test_o_que_abre_mas_nao_e_um_comprovante_conhecido_nao_entra(self):
        motorista_, _ = motorista()
        # Cifra certa, conteudo que nao serve: nem objeto, nem pedido identificado.
        self.assertEqual(motorista_.abrir_comprovante(self.blob([1, 2, 3])), "")
        self.assertEqual(motorista_.abrir_comprovante(self.blob({"status": "delivered"})), "")
        self.assertEqual(motorista_.comprovante_de("m-1"), "")

    def test_a_memoria_tem_teto(self):
        motorista_, _ = motorista()
        for indice in range(210):
            motorista_.registrar_comprovante(f"m-{indice}", "enviado")
        self.assertEqual(len(motorista_._comprovantes), 200)
        self.assertEqual(motorista_.comprovante_de("m-0"), "")
        self.assertEqual(motorista_.comprovante_de("m-209"), "enviado")
        self.assertEqual(len(motorista_._ordem), 200)

    def test_resolve_so_diz_o_que_o_celular_contou(self):
        caso = AndroidLanTransportDriver(ajustes())
        self.assertIsNone(caso.resolve_uncertain(pedido()))
        caso.registrar_comprovante("m-1", "enviado")
        self.assertEqual(caso.resolve_uncertain(pedido()).outcome, "aceito")
        outro = AndroidLanTransportDriver(ajustes())
        outro.registrar_comprovante("m-1", "failed")
        self.assertEqual(outro.resolve_uncertain(pedido()).outcome, "recusado")
        entregue = AndroidLanTransportDriver(ajustes())
        entregue.registrar_comprovante("m-1", "entregue")
        self.assertEqual(entregue.resolve_uncertain(pedido()).outcome, "aceito")

    def test_resolve_nao_reabre_a_rede(self):
        motorista_, fabrica = motorista()
        motorista_.registrar_comprovante("m-1", "entregue")
        with sem_rede() as tentativas:
            self.assertEqual(motorista_.resolve_uncertain(pedido()).outcome, "aceito")
            self.assertEqual(motorista_.poll_inbound(), [])
            motorista_.shutdown()
            self.assertEqual(tentativas, [])
        self.assertEqual(fabrica.tentativas, [])


# ------------------------------------------------------------------- recantos


class SoqueteQueNaoFecha(SoqueteCurta):
    """Soquete que reclama tambem na hora de fechar, como faz a rede de verdade."""

    def __init__(self, respostas: list[bytes] | None = None) -> None:
        super().__init__(respostas)
        self.motivos: list[str] = []

    def shutdown(self, _como: int) -> None:
        self.motivos.append("shutdown")
        raise OSError("conexao ja era")

    def close(self) -> None:
        self.motivos.append("close")
        raise OSError("conexao ja era")


class TextoImpossivelTeste(unittest.TestCase):
    """Um caractere que o UTF-8 nao escreve nao pode virar SMS maquiado."""

    def test_no_modo_antigo_a_saida_e_recusada_antes_da_rede(self):
        motorista_, fabrica = motorista(ajustes(chave_celular="", exigir_e2e=False))
        resultado = motorista_.submit(pedido(text="entregue \ud800 agora"))
        self.assertEqual(resultado.outcome, "recusado")
        self.assertEqual(resultado.reason, "a mensagem tem caracteres que o celular nao aceita")
        self.assertEqual(fabrica.tentativas, [])

    def test_com_envelope_a_saida_tambem_e_recusada_antes_da_rede(self):
        motorista_, fabrica = motorista()
        resultado = motorista_.submit(pedido(text="entregue \ud800 agora"))
        self.assertEqual(resultado.outcome, "recusado")
        self.assertEqual(fabrica.tentativas, [])

    def test_identificador_fora_do_ascii_recusa_o_envelope(self):
        motorista_, fabrica = motorista()
        resultado = motorista_.submit(pedido(id="m-\xe3"))
        self.assertEqual(resultado.outcome, "recusado")
        self.assertEqual(resultado.reason, "identificador do pedido nao serve de etiqueta do envelope")
        self.assertEqual(fabrica.tentativas, [])


class RecantosTeste(unittest.TestCase):
    def test_a_conexao_que_nao_fecha_ainda_devolve_a_duvida(self):
        fabrica = Fabrica()
        aparelho = SoqueteQueNaoFecha()
        fabrica.empilhar(aparelho)
        motorista_ = AndroidLanTransportDriver(
            ajustes(), soquete_factory=fabrica.abrir, descoberta=lambda: []
        )
        self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")
        self.assertEqual(aparelho.motivos, ["shutdown", "close"])

    def test_ajuste_torto_vira_o_padrao_e_nao_um_estouro(self):
        opcoes = LanSettings(porta="torta", timeout="", espera_ack=None, timeout_descoberta="rapido")
        self.assertEqual(opcoes.porta, PORTA_COMANDO)
        self.assertEqual(opcoes.timeout, 5.0)
        self.assertEqual(opcoes.espera_ack, 0.8)
        self.assertEqual(opcoes.timeout_descoberta, 1.6)

    def test_endereco_sem_porta_usavel_fica_de_fora(self):
        motorista_, fabrica = motorista(
            ajustes(host=""),
            descoberta=lambda: [
                ("192.168.0.9", "torta"),
                ("", 49998),
                ("192.168.0.10", "49998"),
            ],
        )
        self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")
        self.assertEqual(fabrica.tentativas, [("192.168.0.10", 49998)])

    def test_o_comprovante_recebido_de_novo_sai_por_ultimo_da_fila(self):
        motorista_, _ = motorista()
        for numero in range(200):
            motorista_.registrar_comprovante(f"m-{numero}", "enviado")
        motorista_.registrar_comprovante("m-0", "entregue")
        motorista_.registrar_comprovante("m-200", "enviado")
        motorista_.registrar_comprovante("m-201", "enviado")
        self.assertEqual(motorista_.comprovante_de("m-0"), ESTADO_ENTREGUE)
        self.assertEqual(motorista_.comprovante_de("m-1"), "")


# ------------------------------------------------------------- ponta a ponta


class CelularLocal:
    """O aplicativo Android de mentirinha: TCP real, cifra real, chave real."""

    def __init__(self, segredos, privada: bytes, *, responder: bool = True, segurar: bool = False):
        # Um segredo = o celular de hoje (uma chave unica por aparelho).
        # Varios segredos = o celular 2.0, com uma credencial por origem.
        if isinstance(segredos, str):
            segredos = {"": segredos}
        self.segredos = {rotulo: crypto.key_from_base64(s) for rotulo, s in segredos.items()}
        self.privada = privada
        self.responder = responder
        self.segurar = segurar
        self.comandos: list[dict] = []
        self.conteudos: list[dict] = []
        self.abertos_por: list[str] = []
        self.eros: list[Exception] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self.port = self._sock.getsockname()[1]
        self._parar = threading.Event()
        self._linha = threading.Thread(target=self._servir, daemon=True)
        self._linha.start()

    def _servir(self) -> None:
        self._sock.settimeout(0.2)
        while not self._parar.is_set():
            try:
                cliente, _ = self._sock.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break
            try:
                self._tratar(cliente)
            except Exception as exc:  # o celular de mentira tambem tem defeito
                self.eros.append(exc)
            finally:
                cliente.close()

    def _abrir(self, corpo: bytes):
        """Abre o pedido com a primeira credencial que servir, como faria o aparelho."""
        for rotulo, chave in self.segredos.items():
            try:
                return rotulo, json.loads(crypto.decrypt(chave, corpo).decode("utf-8")), chave
            except Exception:
                continue
        raise ValueError("nenhuma credencial do celular abre este pedido")

    def _tratar(self, cliente: socket.socket) -> None:
        cabecalho = self._exato(cliente, 4)
        corpo = self._exato(cliente, struct.unpack(">I", cabecalho)[0])
        rotulo, comando, chave = self._abrir(corpo)
        self.comandos.append(comando)
        self.abertos_por.append(rotulo)
        envelope = comando.get("envelope")
        if envelope:
            etiqueta = str(comando.get("id") or "").encode("ascii")
            self.conteudos.append(
                json.loads(e2e.open_sealed(self.privada, envelope, etiqueta).decode("utf-8"))
            )
        else:
            self.conteudos.append(
                {
                    "number": comando.get("number", ""),
                    "message": comando.get("message", ""),
                    "origem": comando.get("origem", ""),
                    "id_externo": "",
                }
            )
        if self.segurar:
            self._parar.wait(5.0)
            return
        if self.responder:
            ack = {"ok": True, "id": comando.get("id", ""), "status": "aceito"}
            cliente.sendall(protocol.frame(crypto.encrypt(chave, json.dumps(ack).encode("utf-8"))))

    @staticmethod
    def _exato(sock: socket.socket, tamanho: int) -> bytes:
        pedacos = bytearray()
        while len(pedacos) < tamanho:
            parte = sock.recv(tamanho - len(pedacos))
            if not parte:
                break
            pedacos.extend(parte)
        return bytes(pedacos)

    def fechar(self) -> None:
        self._parar.set()
        self._linha.join(timeout=6.0)
        try:
            self._sock.close()
        except OSError:  # pragma: no cover
            pass


class PontaAPontaTeste(unittest.TestCase):
    def motorista_do(self, celular: CelularLocal, **campo) -> AndroidLanTransportDriver:
        opcoes = ajustes(host="127.0.0.1", porta=celular.port, base_url="", **campo)
        return AndroidLanTransportDriver(opcoes, descoberta=lambda: [])

    def test_o_celular_recebe_o_pedido_e_responde_pelo_mesmo_canal(self):
        aparelho = Aparelho()
        celular = CelularLocal(CHAVE_PDV, aparelho.privada)
        try:
            motorista_ = self.motorista_do(celular, chave_celular=aparelho.publica)
            resultado = motorista_.submit(pedido())
            self.assertEqual(resultado.outcome, "aceito")
            self.assertEqual(len(celular.comandos), 1)
            self.assertEqual(celular.comandos[0]["origem"], "PDV")
            self.assertEqual(celular.conteudos[0]["number"], NUMERO)
            self.assertEqual(celular.conteudos[0]["message"], TEXTO)
            self.assertEqual(celular.conteudos[0]["origem"], "PDV")
            self.assertEqual(celular.eros, [])
        finally:
            celular.fechar()

    def test_pdv_e_hub_chegam_marcarados_pela_propria_credencial(self):
        aparelho = Aparelho()
        celular = CelularLocal({"PDV": CHAVE_PDV, "HUB": CHAVE_HUB}, aparelho.privada)
        try:
            motorista_ = self.motorista_do(
                celular, segredos_por_origem={"HUB": CHAVE_HUB}, chave_celular=aparelho.publica
            )
            self.assertEqual(motorista_.submit(pedido(origem="PDV", id="m-a")).outcome, "aceito")
            self.assertEqual(motorista_.submit(pedido(origem="HUB", id="m-b", external_id="hub-9")).outcome, "aceito")
            # Cada origem fala com o celular pela sua credencial e se anuncia nos
            # dois lugares: no pedido aberto e no envelope lacrado.
            self.assertEqual(celular.abertos_por, ["PDV", "HUB"])
            self.assertEqual([c["origem"] for c in celular.comandos], ["PDV", "HUB"])
            self.assertEqual([c["origem"] for c in celular.conteudos], ["PDV", "HUB"])
            self.assertEqual([c["id_externo"] for c in celular.conteudos], ["pdv-100", "hub-9"])
        finally:
            celular.fechar()

    def test_a_credencial_de_fora_nao_abre_a_caixa(self):
        aparelho = Aparelho()
        # O celular so guarda a credencial do HUB: o pedido do PDV nao passa da
        # porta, porque a cifra nao abre com a chave errada.
        celular = CelularLocal({"HUB": CHAVE_HUB}, aparelho.privada)
        try:
            motorista_ = self.motorista_do(celular, chave_celular=aparelho.publica)
            self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")
            self.assertEqual(celular.comandos, [])
            self.assertEqual(len(celular.eros), 1)
        finally:
            celular.fechar()

    def test_o_celular_mudo_deixa_o_pedido_em_duvida(self):
        aparelho = Aparelho()
        celular = CelularLocal(CHAVE_PDV, aparelho.privada, responder=False)
        try:
            motorista_ = self.motorista_do(celular, chave_celular=aparelho.publica, espera_ack=0.3)
            self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")
            self.assertEqual(len(celular.comandos), 1)
        finally:
            celular.fechar()

    def test_o_celular_lento_tambem_deixa_em_duvida_sem_reenviar(self):
        aparelho = Aparelho()
        celular = CelularLocal(CHAVE_PDV, aparelho.privada, segurar=True)
        try:
            motorista_ = self.motorista_do(celular, chave_celular=aparelho.publica, espera_ack=0.3)
            self.assertEqual(motorista_.submit(pedido()).outcome, "incerto")
            self.assertEqual(len(celular.comandos), 1)
        finally:
            celular.fechar()

    def test_a_chave_errada_nao_abre_o_envelope_e_deixa_em_duvida(self):
        aparelho = Aparelho()
        intruso = Aparelho()
        celular = CelularLocal(CHAVE_PDV, intruso.privada)
        try:
            motorista_ = self.motorista_do(celular, chave_celular=aparelho.publica)
            resultado = motorista_.submit(pedido())
            # O pedido chegou ao celular, mas a chave errada nao abre o envelope:
            # o aparelho nao responde e a duvida tem de aparecer, nao virar recusa.
            self.assertEqual(resultado.outcome, "incerto")
            self.assertEqual(len(celular.comandos), 1)
            self.assertEqual(len(celular.eros), 1)
            self.assertEqual(celular.conteudos, [])
        finally:
            celular.fechar()


# ------------------------------------------------------------------- utilidade


class LeituraDeQuadroTeste(unittest.TestCase):
    def test_devolve_nada_quando_nao_ha_resposta(self):
        self.assertIsNone(_ler_ack(SoqueteCurta([]), crypto.key_from_base64(CHAVE_PDV), 0.1))

    def test_devolve_nada_quando_a_etiqueta_nao_bate(self):
        bruto = quadro_de({"ok": True}, crypto.key_from_base64(CHAVE_HUB))
        self.assertIsNone(_ler_ack(SoqueteCurta([bruto]), crypto.key_from_base64(CHAVE_PDV), 0.1))

    def test_devolve_nada_quando_o_tamanho_mentiroso(self):
        self.assertIsNone(_ler_ack(SoqueteCurta([b"\xff\xff\xff\xff"]), crypto.key_from_base64(CHAVE_PDV), 0.1))
        self.assertIsNone(_ler_ack(SoqueteCurta([b"\x00\x00\x00\x00"]), crypto.key_from_base64(CHAVE_PDV), 0.1))

    def test_devolve_nada_quando_o_corpo_vem_pela_metade(self):
        anunciado = struct.pack(">I", 40) + b"x" * 10
        self.assertIsNone(_ler_ack(SoqueteCurta([anunciado]), crypto.key_from_base64(CHAVE_PDV), 0.1))

    def test_descricao_do_motorista_nao_vaza_segredo(self):
        descricao = AndroidLanTransportDriver(ajustes()).describe()
        serializado = json.dumps(descricao, ensure_ascii=False)
        self.assertNotIn(CHAVE_PDV, serializado)
        self.assertEqual(descricao["nome"], "android_lan")
        self.assertEqual(descricao["comprovantes"], 0)


if __name__ == "__main__":
    unittest.main()
