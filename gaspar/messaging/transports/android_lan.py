"""Motorista da rede local: o celular que ja esta pareado pelo Wi-Fi da loja.

O canal nao e novo. Desde a 1.7 o computador do balcao fala com o aplicativo
Android por TCP na porta 49998: quadro de quatro bytes com o tamanho, corpo
cifrado com o segredo do pareamento e, dentro dele, um pedido de SMS fechado no
envelope ponta a ponta do celular. Este modulo entra na barra de mensagens 2.0
pela porta da frente, entao o celular pareado hoje continua servindo amanha.

O que chega de novo:

* ``origem`` (PDV ou HUB) vai no comando e dentro do envelope. O aplicativo 1.7
  le as chaves que conhece e ignora as outras, entao o campo extra nao estraga o
  app ja instalado;
* o numero do cliente e o texto nunca saem do envelope. Sem a chave privada do
  celular, que fica no Keystore, nem este modulo abre o proprio pedido;
* a sequencia e crescente e o celular recusa a que for igual ou menor que a
  ultima que viu. Essa recusa e a prova de que nada saiu duas vezes, e e por
  isso que um pedido em duvida nunca e reenviado por aqui.

Os quatro resultados do contrato saem assim:

* ``aceito``: o celular respondeu ``ok``; ele tem o pedido e devolve comprovante;
* ``recusado``: nada chegou ao radio - meio desligado, sem pareamento, sem chave,
  sem endereco na rede, texto que o UTF-8 nao escreve, ou recusa dita pelo
  proprio aplicativo;
* ``incerto``: o pedido foi empurrado na conexao e a resposta nao voltou. Pode ter
  saido, entao a fila congela o pedido ate aparecer um comprovante;
* ``indisponivel``: o meio esta desligado ou sem segredo.

``health()`` nao abre conexao nem faz descoberta: ela le so a configuracao, para o
painel poder perguntar sem incomodar ninguem na rede. Quem quer a prova de verdade e
``testar_acesso()``, que abre uma conexao e fecha sem mandar quadro. As conexoes de
verdade entram por fabrica injetavel (``soquete_factory``, ``descoberta``), e os testes
usam rede real em 127.0.0.1 com o mesmo AES e o mesmo envelope do Android.
"""

from __future__ import annotations

import base64
import json
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Callable

from gaspar.messaging.errors import MessagingError
from gaspar.messaging.model import Message, validar_origem
from gaspar.messaging.transport import (
    OUTCOME_REJECTED,
    Health,
    SmsTransportDriver,
    SubmitResult,
    accepted,
    rejected,
    unavailable,
    unknown,
)
from gaspar.sms import crypto, e2e, protocol
from gaspar.sms.discovery import discover

#: nome com que este meio aparece na configuracao e na fila
NOME_MOTORISTA = "android_lan"

#: porta TCP que o aplicativo Android escuta, e a de descoberta por broadcast
PORTA_COMANDO = protocol.COMMAND_PORT
PORTA_DESCOBERTA = protocol.DISCOVERY_PORT

#: unico comando que o app sabe executar neste canal
ACAO_ENVIO = "send_sms"

#: o que o celular conta sobre um pedido
ESTADO_ENVIADO = "enviado"
ESTADO_ENTREGUE = "entregue"
ESTADO_FALHOU = "falhou"
ESTADOS: tuple[str, ...] = (ESTADO_ENVIADO, ESTADO_ENTREGUE, ESTADO_FALHOU)

#: o app 1.7 escreve o estado em ingles; dentro da fila so valem os de cima
_ALIAS_DE_ESTADO = {
    "sent": ESTADO_ENVIADO,
    "enviado": ESTADO_ENVIADO,
    "delivered": ESTADO_ENTREGUE,
    "entregue": ESTADO_ENTREGUE,
    "failed": ESTADO_FALHOU,
    "falhou": ESTADO_FALHOU,
}

#: palavra que o app usa para dizer que a sequencia ja passou por ele
RECUSA_DE_SEQUENCIA = "pedido repetido"

#: teto de comprovantes em memoria
LIMITE_COMPROVANTES = 200

#: enderecos tentados por pedido - o celular troca de IP quando o roteador quer
LIMITE_ENDERECOS = 3

SoqueteFactory = Callable[..., object]
Descoberta = Callable[[], list[tuple[str, int]]]
Sequencia = Callable[[], int]


class AndroidLanError(MessagingError):
    """O canal local nao tem como falar com o celular do jeito pedido."""


def _json_seguro(corpo: dict) -> bytes:
    """Serializa o pedido. Caractere que o UTF-8 nao aceita e recusa, nao maquiagem.

    Um sobrogate solto no texto (o que um JSON com \\ud800 devolve) nao tem como
    virar SMS: trocar por '?' mandaria ao cliente uma mensagem que ninguem escreveu.
    """
    try:
        return json.dumps(corpo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AndroidLanError("a mensagem tem caracteres que o celular nao aceita") from exc


# ---------------------------------------------------------------- configuracao


def _texto(valor: object) -> str:
    return str(valor if valor is not None else "").strip()


def _inteiro(valor: object, padrao: int, *, limite: int) -> int:
    try:
        numero = int(float(str(valor)))
    except (TypeError, ValueError):
        return padrao
    return numero if 1 <= numero <= limite else padrao


def _decimal(valor: object, padrao: float, *, low: float, high: float) -> float:
    try:
        numero = float(str(valor))
    except (TypeError, ValueError):
        return padrao
    return min(max(numero, low), high)


@dataclass
class LanSettings:
    """Opcoes do canal Wi-Fi. Nascem desligadas e sem segredo: nada mexe sozinho."""

    #: desligado, o motorista nao abre soquete e a health responde indisponivel
    ligada: bool = False
    #: endereco fixo do celular; vazio = descobrir na rede a cada pedido
    host: str = ""
    porta: int = PORTA_COMANDO
    #: permitir a descoberta por broadcast quando nao ha endereco fixo
    descobrir: bool = True
    #: segredo do pareamento (base64), o mesmo que o app 1.7 ja guarda
    segredo: str = ""
    #: segredo proprio de uma origem, para o app 2.0 pareado por produto
    segredos_por_origem: dict[str, str] = field(default_factory=dict)
    #: chave publica EC do celular, em base64, para fechar o envelope
    chave_celular: str = ""
    #: exige envelope ponta a ponta; sem chave, o pedido e recusado
    exigir_e2e: bool = True
    #: para onde o celular manda o comprovante
    base_url: str = ""
    #: quanto esperar a conexao e a resposta do celular
    timeout: float = 5.0
    espera_ack: float = 0.8
    timeout_descoberta: float = 1.6

    def __post_init__(self) -> None:
        self.ligada = bool(self.ligada)
        self.host = _texto(self.host)
        self.porta = _inteiro(self.porta, PORTA_COMANDO, limite=65535)
        self.descobrir = bool(self.descobrir)
        self.segredo = _texto(self.segredo)
        self.segredos_por_origem = self._limpar_origens(self.segredos_por_origem)
        self.chave_celular = _texto(self.chave_celular)
        self.exigir_e2e = bool(self.exigir_e2e)
        self.base_url = _texto(self.base_url).rstrip("/")
        self.timeout = _decimal(self.timeout, 5.0, low=0.2, high=120.0)
        self.espera_ack = _decimal(self.espera_ack, 0.8, low=0.1, high=60.0)
        self.timeout_descoberta = _decimal(self.timeout_descoberta, 1.6, low=0.4, high=30.0)

    @staticmethod
    def _limpar_origens(valor: object) -> dict[str, str]:
        result: dict[str, str] = {}
        for chave, item in (valor if isinstance(valor, dict) else {}).items():
            try:
                origem = validar_origem(chave)
            except ValueError:
                continue
            texto = _texto(item)
            if texto:
                result[origem] = texto
        return result

    def segredo_para(self, origem: object) -> str:
        """O segredo daquela origem; sem um proprio, o do pareamento unico."""
        try:
            origin = validar_origem(origem)
        except ValueError:
            return ""
        return self.segredos_por_origem.get(origin) or self.segredo

    def tem_pareamento(self, origem: object = None) -> bool:
        if origem is None:
            return bool(self.segredo or self.segredos_por_origem)
        return bool(self.segredo_para(origem))

    def tem_endereco(self) -> bool:
        return bool(self.host or self.descobrir)

    def chaves(self) -> list[tuple[str, str]]:
        """Pares (rotulo, segredo base64) possiveis, do mais especifico ao geral."""
        pares = sorted(self.segredos_por_origem.items())
        if self.segredo:
            pares.append(("", self.segredo))
        return [(rotulo, segredo) for rotulo, segredo in pares if segredo]

    def to_dict(self) -> dict:
        """Versao para tela e log: presenca de segredo, nunca o segredo."""
        return {
            "ligada": self.ligada,
            "host": self.host,
            "porta": self.porta,
            "descobrir": self.descobrir,
            "pareado": self.tem_pareamento(),
            "origens_pareadas": sorted(self.segredos_por_origem),
            "celular": e2e.fingerprint_b64(self.chave_celular),
            "exigir_e2e": self.exigir_e2e,
            "base_url": self.base_url,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, dados: object) -> "LanSettings":
        """Le o bloco do ``messaging.json``.

        Campo que nao existe aqui fica de fora, sem pane: o arquivo pode carregar
        ajustes de outra versao e o canal sobe com os proprios padroes. Segredo de
        pareamento nunca aparece nesta forma - quem le o arquivo entrega o campo
        ja aberto (``segredo``), e a fabrica e a unica que abre o selo.
        """
        itens = dados if isinstance(dados, dict) else {}
        conhecidos = {
            chave: valor for chave, valor in itens.items() if chave in cls.__dataclass_fields__
        }
        return cls(**conhecidos)


# ------------------------------------------------------------------ motorista


class AndroidLanTransportDriver(SmsTransportDriver):
    """Entrega o pedido da fila ao celular pareado pela rede local da loja."""

    name = NOME_MOTORISTA
    #: o canal leva pedidos e traz comprovantes; resposta de cliente nao vem por aqui
    supports_reception = False
    supports_delivery_report = True

    def __init__(
        self,
        settings: LanSettings | None = None,
        *,
        soquete_factory: SoqueteFactory | None = None,
        descoberta: Descoberta | None = None,
        sequencia: Sequencia | None = None,
    ) -> None:
        self.settings = settings if settings is not None else LanSettings()
        self.device_id = "android-lan"
        self._abrir_soquete = soquete_factory or socket.create_connection
        self._descobrir = descoberta if descoberta is not None else _descobrir_padrao
        self._sequencia_externa = sequencia
        self._sequencia_local = 0
        self._comprovantes: dict[str, str] = {}
        self._ordem: list[str] = []

    # -------------------------------------------------------------- diagnostico

    def health(self) -> Health:
        """O que a configuracao permite ver, sem tocar na rede."""
        if not self.settings.ligada:
            return Health(False, "meio desligado na configuracao")
        if not self.settings.tem_pareamento():
            return Health(False, "celular sem segredo de pareamento")
        if not self.settings.tem_endereco():
            return Health(False, "nenhum endereco do celular conhecido")
        if self.settings.exigir_e2e and not self.settings.chave_celular:
            return Health(False, "celular sem chave de criptografia; pareie o celular de novo")
        return Health(True, "", self.device_id)

    def testar_acesso(self) -> Health:
        """Confere o celular de verdade sem mandar nada: abre a conexao e fecha na hora.

        Ensaiar um envio nao e possivel - se saisse, o cliente receberia um SMS. O que
        da para provar sem efeito e que o aparelho esta do outro lado da porta que a
        fila vai usar, que e exatamente o que costuma quebrar na loja (celular
        desligado, trocado de endereco, app fechado).
        """
        saude = self.health()
        if not saude.available:
            return saude
        enderecos = self._enderecos()
        if not enderecos:
            return Health(False, "o celular nao apareceu na rede da loja")
        motivo = ""
        for host, porta in enderecos:
            rotulo = f"{host}:{porta}"
            try:
                soquete = self._abrir_soquete((host, porta), timeout=self.settings.timeout)
            except Exception as exc:
                detalhe = str(exc).strip()
                motivo = f"o celular nao atendeu em {rotulo}" + (f" ({detalhe[:60]})" if detalhe else "")
                continue
            with _Fecho(soquete):
                pass
            return Health(True, "", rotulo)
        return Health(False, motivo or "o celular nao atendeu na rede da loja")

    def describe(self) -> dict:
        dados: dict = {
            "nome": self.name,
            "dispositivo": self.device_id,
            "recepcao": self.supports_reception,
            "comprovante_entrega": self.supports_delivery_report,
        }
        dados.update(self.settings.to_dict())
        dados["comprovantes"] = len(self._comprovantes)
        return dados

    # -------------------------------------------------------------------- enviar

    def submit(self, message: Message) -> SubmitResult:
        if not self.settings.ligada:
            return unavailable("meio desligado na configuracao")
        try:
            origem = validar_origem(message.origem)
        except ValueError as exc:
            return rejected(str(exc))
        if not self.settings.tem_pareamento(origem):
            return unavailable("celular sem segredo de pareamento")
        chave = self._chave(origem)
        if chave is None:
            return unavailable("segredo de pareamento invalido")
        envelope = self._envelope(message)
        if isinstance(envelope, SubmitResult):
            return envelope
        try:
            quadro = self._quadro(message, origem, envelope, chave)
        except AndroidLanError as exc:
            return rejected(str(exc))

        enderecos = self._enderecos()
        if not enderecos:
            return rejected("celular nao encontrado na rede")

        ultimo = rejected("celular sem resposta")
        for host, porta in enderecos:
            ultimo = self._transmitir(host, porta, quadro, chave)
            if ultimo.outcome != OUTCOME_REJECTED:
                return ultimo
        return ultimo

    def _quadro(self, message: Message, origem: str, envelope: str, chave: bytes) -> bytes:
        """Comando do app 1.7 mais a origem; o conteudo sai fechado no envelope."""
        comando: dict = {
            "action": ACAO_ENVIO,
            "origem": origem,
            "id": message.id,
            "ts": int(message.created_at or time.time()),
            "seq": self._proxima_sequencia(),
        }
        if self.settings.base_url:
            comando["base"] = self.settings.base_url
        if envelope:
            comando["envelope"] = envelope
        else:
            comando["number"] = message.recipient
            comando["message"] = message.text
        payload = _json_seguro(comando)
        return protocol.frame(crypto.encrypt(chave, payload))

    def _envelope(self, message: Message) -> str | SubmitResult:
        """Fecha numero e texto na chave publica do celular; o AAD e o id do pedido."""
        if not self.settings.chave_celular:
            if self.settings.exigir_e2e:
                return rejected("celular sem chave de criptografia; pareie o celular de novo")
            return ""
        corpo = {
            "number": message.recipient,
            "message": message.text,
            "origem": message.origem,
            "id_externo": message.external_id,
        }
        try:
            payload = _json_seguro(corpo)
            etiqueta = message.id.encode("ascii")
        except AndroidLanError as exc:
            return rejected(str(exc))
        except UnicodeEncodeError:
            return rejected("identificador do pedido nao serve de etiqueta do envelope")
        try:
            return e2e.seal(self.settings.chave_celular, payload, etiqueta)
        except e2e.E2EError as exc:
            return rejected(str(exc))

    def _chave(self, origem: str) -> bytes | None:
        try:
            return crypto.key_from_base64(self.settings.segredo_para(origem))
        except ValueError:
            return None

    def _proxima_sequencia(self) -> int:
        """Crescente sempre. Em producao vem do pareamento, para nao colidir com a ponte 1.7."""
        if self._sequencia_externa is not None:
            try:
                valor = int(self._sequencia_externa())
            except (TypeError, ValueError):
                valor = 0
            if valor > 0:
                return valor
        self._sequencia_local += 1
        return self._sequencia_local

    def _enderecos(self) -> list[tuple[str, int]]:
        if self.settings.host:
            return [(self.settings.host, self.settings.porta)]
        if not self.settings.descobrir:
            return []
        try:
            achados = list(self._descobrir() or [])
        except Exception:
            return []
        enderecos: list[tuple[str, int]] = []
        for host, porta in achados[:LIMITE_ENDERECOS]:
            texto = str(host or "").strip()
            try:
                numero = int(porta)
            except (TypeError, ValueError):
                continue
            if texto and numero > 0:
                enderecos.append((texto, numero))
        return enderecos

    def _transmitir(self, host: str, porta: int, quadro: bytes, chave: bytes) -> SubmitResult:
        rotulo = f"{host}:{porta}"
        try:
            soquete = self._abrir_soquete((host, porta), timeout=self.settings.timeout)
        except Exception as exc:
            return rejected(f"celular sem resposta em {rotulo}: {str(exc)[:80]}")
        try:
            with _Fecho(soquete) as sock:
                try:
                    sock.sendall(quadro)
                except OSError:
                    return unknown(f"o pedido comecou a sair e a rede caiu em {rotulo}")
                try:
                    sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                ack = _ler_ack(sock, chave, self.settings.espera_ack)
        except Exception:
            return unknown(f"a conversa com {rotulo} terminou sem resposta")
        if not isinstance(ack, dict):
            return unknown("o celular recebeu o pedido e nao respondeu")
        return self._classificar(ack)

    def _classificar(self, ack: dict) -> SubmitResult:
        if ack.get("ok") is False:
            erro = _texto(ack.get("error"))
            if RECUSA_DE_SEQUENCIA in erro.lower():
                return rejected("a sequencia do pedido esta atrasada no celular")
            return rejected(erro[:200] or "o celular recusou o pedido")
        referencia = _texto(ack.get("id"))
        if _texto(ack.get("status")).lower() == "repetido":
            return accepted("o celular ja tinha recebido este pedido", referencia)
        return accepted("pedido entregue ao celular", referencia)

    # --------------------------------------------------------------- comprovante

    def registrar_comprovante(self, referencia: object, estado: object, detalhe: str = "") -> bool:
        """Guarda o que o celular contou sobre um pedido. Estado desconhecido nao entra."""
        ref = _texto(referencia)
        nome = _ALIAS_DE_ESTADO.get(_texto(estado).lower())
        if not ref or nome is None:
            return False
        if ref in self._ordem:
            self._ordem.remove(ref)
        self._ordem.append(ref)
        self._comprovantes[ref] = nome
        while len(self._ordem) > LIMITE_COMPROVANTES:
            self._comprovantes.pop(self._ordem.pop(0), None)
        return True

    def abrir_comprovante(self, corpo: object) -> str:
        """Abre o comprovante cifrado que o app 1.7 POSTa e devolve o id do pedido."""
        blob = _texto(corpo)
        if not blob:
            return ""
        try:
            bruto = base64.b64decode(blob, validate=True)
        except Exception:
            return ""
        for _, segredo in self.settings.chaves():
            try:
                chave = crypto.key_from_base64(segredo)
                dados = json.loads(crypto.decrypt(chave, bruto).decode("utf-8"))
            except Exception:
                continue
            if not isinstance(dados, dict):
                continue
            referencia = _texto(dados.get("id"))
            if not referencia:
                return ""
            self.registrar_comprovante(referencia, dados.get("status"), _texto(dados.get("detail")))
            return referencia
        return ""

    def comprovante_de(self, referencia: object) -> str:
        return self._comprovantes.get(_texto(referencia), "")

    def resolve_uncertain(self, message: Message) -> SubmitResult | None:
        """Responde so o que o celular contou. Nunca reenvia para descobrir."""
        estado = self.comprovante_de(message.id)
        if not estado:
            return None
        if estado == ESTADO_FALHOU:
            return rejected("o celular informou que o SMS falhou")
        if estado == ESTADO_ENTREGUE:
            return accepted("o celular confirmou a entrega ao destinatario", message.id)
        return accepted("o celular confirmou que enviou o SMS", message.id)


# ------------------------------------------------------------------ quadros


class _Fecho:
    """Garante que o soquete fecha mesmo quando o caminho devolve cedo."""

    def __init__(self, sock: object) -> None:
        self._sock = sock

    def __enter__(self) -> object:
        return self._sock

    def __exit__(self, *exc: object) -> None:
        fechar = getattr(self._sock, "close", None)
        if callable(fechar):
            try:
                fechar()
            except Exception:
                pass


def _ler_exato(sock: object, tamanho: int, prazo: float) -> bytes:
    pedacos = bytearray()
    while len(pedacos) < tamanho:
        try:
            sock.settimeout(prazo)  # type: ignore[attr-defined]
            parte = sock.recv(tamanho - len(pedacos))  # type: ignore[attr-defined]
        except OSError:
            break
        if not parte:
            break
        pedacos.extend(parte)
    return bytes(pedacos)


def _ler_ack(sock: object, chave: bytes, prazo: float) -> dict | None:
    """Le o quadro de resposta. Sem resposta, ou resposta torta, devolve None."""
    try:
        cabecalho = _ler_exato(sock, 4, prazo)
        if len(cabecalho) != 4:
            return None
        tamanho = struct.unpack(">I", cabecalho)[0]
        if tamanho <= 0 or tamanho > protocol.MAX_FRAME:
            return None
        corpo = _ler_exato(sock, tamanho, prazo)
        if len(corpo) != tamanho:
            return None
        dados = json.loads(crypto.decrypt(chave, corpo).decode("utf-8"))
    except Exception:
        return None
    return dados if isinstance(dados, dict) else None


def _descobrir_padrao() -> list[tuple[str, int]]:
    return discover(port=PORTA_DESCOBERTA)
