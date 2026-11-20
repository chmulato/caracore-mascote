"""Ponte de e-mail: a caixa postal da loja faz de fila ate o celular.

Nao ha gateway de operadora nem servico pago no meio do caminho. O computador do
balcao escreve o pedido dentro da caixa postal da loja, o aplicativo Android 2.0
le essa caixa (pelo 4G, fora do Wi-Fi, ou pela rede local) e dispara o SMS pelo
chip proprio. O comprovante e a resposta do cliente voltam pelo mesmo caminho.

O que viaja dentro do e-mail esta cifrado e autenticado com AES-GCM
(``gaspar.sms.crypto``) usando uma chave que so o computador e o aplicativo tem.
No cabecalho fica apenas o identificador da fila - um numero sem relacao com o
cliente. Senha de app (Gmail e o exemplo) e chave da ponte entram seladas pelo
cofre da fila (``vault.py``): no disco nao ha texto claro.

Tres coisas deste modulo sao de proposito e valem a leitura:

* ``health()`` nao abre conexao nenhuma. Ela diz o que a configuracao permite
  ver; quem prova que a caixa postal esta viva e o primeiro envio ou leitura.
* com a ponte desligada, nada neste modulo toca em soquete - nem ``health``,
  nem ``submit``, nem ``poll_inbound``. Os testes amarram um alarme nos tres
  protocolos e na resolucao de nome para provar isso.
* depois de uma entrega que nao deu para confirmar, o resultado e ``incerto``:
  a fila nunca reenvia sozinha, porque reenviar duplicaria o SMS do cliente.

As conexoes entram por fabricas (``smtp_factory``, ``imap_factory``,
``pop3_factory``). O produto usa as de verdade; os testes usam as de mentirinha
e assim nenhuma linha daqui depende da internet para rodar.
"""

from __future__ import annotations

import base64
import imaplib
import json
import os
import poplib
import smtplib
import time
from dataclasses import dataclass
from email import message_from_bytes
from email.message import EmailMessage
from hashlib import sha256
from pathlib import Path
from typing import Callable

from gaspar.messaging.errors import MessagingError
from gaspar.messaging.model import (
    MAX_TEXTO,
    Message,
    MessageBrief,
    normalizar_destino,
    normalizar_texto,
    validar_origem,
)
from gaspar.messaging.transport import (
    Health,
    InboundReply,
    SmsTransportDriver,
    SubmitResult,
    accepted,
    rejected,
    unavailable,
    unknown,
)
from gaspar.messaging.vault import Vault
from gaspar.sms import crypto

#: marca no assunto: o que nao comeca assim e correspondencia de outra pessoa
ASSUNTO_PREFIXO = "GASPAR"

#: os tres tipos de envelope que circulam pela caixa postal
TIPO_PEDIDO = "pedido"
TIPO_COMPROVANTE = "comprovante"
TIPO_RESPOSTA = "resposta"
TIPOS: tuple[str, ...] = (TIPO_PEDIDO, TIPO_COMPROVANTE, TIPO_RESPOSTA)

#: o que o celular devolve como estado de um pedido
ESTADO_ENVIADO = "enviado"
ESTADO_ENTREGUE = "entregue"
ESTADO_FALHOU = "falhou"
ESTADOS: tuple[str, ...] = (ESTADO_ENVIADO, ESTADO_ENTREGUE, ESTADO_FALHOU)

VERSAO_ENVELOPE = 1
TIMEOUT_SEGUNDOS = 20
LIMITE_LIDOS = 400
LIMITE_RECIBOS = 200

#: etapa em que a conversa com o servidor caiu
ETAPA_CONEXAO = "conexao"
ETAPA_LOGIN = "login"
#: recusa dita pelo servidor com codigo: ele garante que o pedido nao entrou
ETAPA_RECUSA = "recusa"
#: o pedido foi empurrado e a resposta nao voltou: pode ter entrado
ETAPA_ENTREGA = "entrega"

ConexaoFactory = Callable[..., object]


class EmailBridgeError(MessagingError):
    """A ponte de e-mail nao tem como falar com a caixa postal pedida."""


class _Queda(Exception):
    """Falha classificada pela etapa: antes da entrega nada saiu; nela, duvida."""

    def __init__(self, etapa: str, motivo: str) -> None:
        super().__init__(motivo)
        self.etapa = etapa
        self.motivo = motivo[:200]


# ------------------------------------------------------------------- envelope


def selar_envelope(chave: bytes, corpo: dict) -> str:
    """JSON -> AES-GCM -> base64 de uma linha so, para caber num corpo de texto."""
    if not chave:
        raise EmailBridgeError("a ponte de e-mail precisa de uma chave")
    payload = json.dumps(corpo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(crypto.encrypt(chave, payload)).decode("ascii")


def abrir_envelope(chave: bytes, texto: object) -> dict:
    """O caminho inverso. Qualquer desvio vira erro: sem envelope aberto, nao ha prova."""
    compacto = "".join(str(texto or "").split())
    if not compacto:
        raise ValueError("corpo de e-mail vazio")
    bruto = base64.b64decode(compacto, validate=True)
    dados = json.loads(crypto.decrypt(chave, bruto).decode("utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("envelope da ponte nao e um objeto")
    if int(dados.get("v") or 0) != VERSAO_ENVELOPE:
        raise ValueError("versao de envelope desconhecida")
    if str(dados.get("tipo") or "") not in TIPOS:
        raise ValueError("tipo de envelope desconhecido")
    return dados


# ---------------------------------------------------------------- configuracao


def _texto(valor: object) -> str:
    return str(valor if valor is not None else "").strip()


def _porta(valor: object, padrao: int) -> int:
    try:
        numero = int(float(str(valor)))
    except (TypeError, ValueError):
        return padrao
    return numero if 1 <= numero <= 65535 else padrao


def _numero(valor: object) -> float:
    try:
        return float(str(valor))
    except (TypeError, ValueError):
        return 0.0


@dataclass
class EmailSettings:
    """Opcoes da ponte. O que e segredo chega aqui ja selado pelo cofre da fila."""

    enabled: bool = False
    #: endereco da caixa postal da loja (a mesma que o celular le)
    user: str = ""
    #: senha de app, selada por ``Vault.seal``
    password_sealed: str = ""
    #: chave da ponte em base64, selada por ``Vault.seal``
    bridge_key_sealed: str = ""
    from_address: str = ""
    #: para quem o pedido e escrito; por padrao, a propria caixa
    queue_address: str = ""
    message_id_domain: str = "gaspar.local"
    smtp_host: str = ""
    smtp_port: int = 465
    #: ssl (465) | starttls (587) | plano (so para tubo de teste local)
    smtp_security: str = "ssl"
    imap_host: str = ""
    imap_port: int = 993
    pop3_host: str = ""
    pop3_port: int = 995
    mailbox: str = "INBOX"
    #: quantos recados a mais da caixa uma leitura por POP3 pode examinar
    max_poll_messages: int = 25
    #: onde ficam o cursor de leitura e os comprovantes ja vistos
    state_path: str = ""

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)
        for campo in (
            "user",
            "password_sealed",
            "bridge_key_sealed",
            "from_address",
            "queue_address",
            "message_id_domain",
            "smtp_host",
            "smtp_security",
            "imap_host",
            "pop3_host",
            "mailbox",
            "state_path",
        ):
            setattr(self, campo, _texto(getattr(self, campo)))
        self.smtp_security = (self.smtp_security or "ssl").lower()
        if self.smtp_security not in ("ssl", "starttls", "plano"):
            self.smtp_security = "ssl"
        self.smtp_port = _porta(self.smtp_port, 465)
        self.imap_port = _porta(self.imap_port, 993)
        self.pop3_port = _porta(self.pop3_port, 995)
        self.max_poll_messages = min(max(int(_numero(self.max_poll_messages) or 25), 1), 200)

    @property
    def endereco_remetente(self) -> str:
        return self.from_address or self.user

    @property
    def endereco_fila(self) -> str:
        return self.queue_address or self.user

    @property
    def protocolo_de_leitura(self) -> str:
        """IMAP e o preferido; POP3 e a reserva para caixa que so sabe baixar."""
        if self.imap_host:
            return "imap"
        if self.pop3_host:
            return "pop3"
        return ""

    def faltando(self) -> list[str]:
        """O que impede a ponte de funcionar - nomes de campo, nunca valores."""
        faltando = []
        if not self.user:
            faltando.append("conta")
        if not self.password_sealed:
            faltando.append("senha selada")
        if not self.bridge_key_sealed:
            faltando.append("chave da ponte selada")
        if not self.smtp_host:
            faltando.append("servidor de saida")
        return faltando

    def to_dict(self) -> dict:
        """Forma gravavel: os segredos continuam selados."""
        return {
            "enabled": self.enabled,
            "user": self.user,
            "password_sealed": self.password_sealed,
            "bridge_key_sealed": self.bridge_key_sealed,
            "from_address": self.from_address,
            "queue_address": self.queue_address,
            "message_id_domain": self.message_id_domain,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_security": self.smtp_security,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "pop3_host": self.pop3_host,
            "pop3_port": self.pop3_port,
            "mailbox": self.mailbox,
            "max_poll_messages": self.max_poll_messages,
            "state_path": self.state_path,
        }

    @classmethod
    def from_dict(cls, dados: object) -> "EmailSettings":
        itens = dados if isinstance(dados, dict) else {}
        conhecidos = {chave: valor for chave, valor in itens.items() if chave in cls.__dataclass_fields__}
        return cls(**conhecidos)


# --------------------------------------------------------------------- estado


class BridgeState:
    """O que a ponte aprendeu entre uma leitura e outra.

    Guardamos tres coisas: ate onde a caixa ja foi lida, quais recados ja
    viraram resposta (para nao repetir) e o que o celular informou sobre cada
    pedido - a prova que desfaz um ``incerto`` sem precisar reenviar nada.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.uid_imap = 0
        self.lidos: list[str] = []
        self.recibos: dict[str, str] = {}
        self._vistos: set[str] = set()
        if self.path is not None and self.path.exists():
            self._ler()

    def _ler(self) -> None:
        try:
            dados = json.loads(self.path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        except (OSError, ValueError):
            return
        if not isinstance(dados, dict):
            return
        self.uid_imap = max(0, int(_numero(dados.get("uid_imap"))))
        vistos = dados.get("lidos")
        if isinstance(vistos, list):
            self._marcar([_texto(item) for item in vistos])
        recibos = dados.get("recibos")
        if isinstance(recibos, dict):
            self.recibos = {
                _texto(chave): _texto(valor)
                for chave, valor in list(recibos.items())[-LIMITE_RECIBOS:]
                if _texto(chave) and _texto(valor) in ESTADOS
            }

    def _marcar(self, ids: list[str]) -> None:
        for identificador in ids:
            if identificador and identificador not in self._vistos:
                self._vistos.add(identificador)
                self.lidos.append(identificador)
        excesso = len(self.lidos) - LIMITE_LIDOS
        if excesso > 0:
            for descartado in self.lidos[:excesso]:
                self._vistos.discard(descartado)
            self.lidos = self.lidos[excesso:]

    def ja_lido(self, identificador: str) -> bool:
        return bool(identificador) and identificador in self._vistos

    def marcar_lido(self, identificador: str) -> None:
        self._marcar([_texto(identificador)])

    def registrar_recibo(self, referencia: str, estado: str) -> None:
        referencia, estado = _texto(referencia), _texto(estado)
        if not referencia or estado not in ESTADOS:
            return
        self.recibos[referencia] = estado
        excesso = len(self.recibos) - LIMITE_RECIBOS
        if excesso > 0:
            for chave in list(self.recibos)[:excesso]:
                self.recibos.pop(chave, None)

    def recibo_de(self, referencia: str) -> str:
        return self.recibos.get(_texto(referencia), "")

    def gravar(self) -> bool:
        if self.path is None:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(
                    {"uid_imap": self.uid_imap, "lidos": self.lidos, "recibos": self.recibos},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
        except OSError:
            return False
        return True


# ------------------------------------------------------------------ motorista


def _smtp_ssl(host: str, porta: int):
    return smtplib.SMTP_SSL(host, porta, timeout=TIMEOUT_SEGUNDOS)


def _smtp_plano(host: str, porta: int):
    return smtplib.SMTP(host, porta, timeout=TIMEOUT_SEGUNDOS)


def _imap_ssl(host: str, porta: int):
    return imaplib.IMAP4_SSL(host, porta, timeout=TIMEOUT_SEGUNDOS)


def _pop3_ssl(host: str, porta: int):
    return poplib.POP3_SSL(host, porta, timeout=TIMEOUT_SEGUNDOS)


class EmailBridgeDriver(SmsTransportDriver):
    """Escreve o pedido na caixa postal da loja e le dela o que o celular responde."""

    name = "smtp_email"
    device_id = ""
    supports_reception = True
    #: o comprovante chega quando o celular avisa que a operadora entregou
    supports_delivery_report = True

    def __init__(
        self,
        settings: EmailSettings | None = None,
        *,
        vault: Vault | None = None,
        smtp_factory: ConexaoFactory | None = None,
        imap_factory: ConexaoFactory | None = None,
        pop3_factory: ConexaoFactory | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.settings = settings if settings is not None else EmailSettings()
        self._vault = vault
        self._smtp_factory = smtp_factory
        self._imap_factory = imap_factory
        self._pop3_factory = pop3_factory
        self._clock = clock
        self.device_id = f"email:{self.settings.user}" if self.settings.user else "email"
        self.estado = BridgeState(Path(self.settings.state_path) if self.settings.state_path else None)
        #: a ultima conversa com a caixa postal falhou? o motivo fica aqui, vazio quando nao
        self.ultimo_erro = ""
        #: recados com a nossa marca: quantos eram nossos e quantos nao abriram
        self.recados_da_ponte = 0
        self.corpos_sem_abertura = 0

    # ------------------------------------------------------------------ saude

    def health(self) -> Health:
        """Checagem local de proposito: sem abrir conexao com nada."""
        if not self.settings.enabled:
            return Health(False, "ponte de e-mail desligada na configuracao")
        faltando = self.settings.faltando()
        if faltando:
            return Health(False, "ponte de e-mail incompleta: falta " + ", ".join(faltando))
        if self.ultimo_erro:
            return Health(True, f"a ultima conversa com a caixa postal falhou: {self.ultimo_erro[:160]}")
        return Health(True, "", self.device_id)

    @property
    def ligada(self) -> bool:
        return bool(self.settings.enabled) and not self.settings.faltando()

    def _senha(self) -> str:
        return self._abrir_segredo(self.settings.password_sealed, "a senha de app")

    def _chave(self) -> bytes:
        texto = self._abrir_segredo(self.settings.bridge_key_sealed, "a chave da ponte")
        return crypto.key_from_base64(texto)

    def _abrir_segredo(self, selado: str, nome: str) -> str:
        if not selado:
            raise EmailBridgeError(f"falta {nome} selada na configuracao da ponte")
        if self._vault is None:
            raise EmailBridgeError(f"o cofre da fila nao esta montado para abrir {nome}")
        return self._vault.open(selado)

    # ------------------------------------------------------------------ envio

    def submit(self, message: Message) -> SubmitResult:
        saude = self.health()
        if not saude.available:
            return unavailable(saude.reason or "ponte de e-mail indisponivel")
        try:
            envelope = selar_envelope(self._chave(), self._corpo_do_pedido(message))
            mail = self._mensagem(message, envelope)
            cliente = self._conectar()
        except (MessagingError, ValueError) as exc:
            # nada foi entregue ao servidor: a fila pode tentar de novo
            return rejected(str(exc)[:200])
        except _Queda as queda:
            return rejected(queda.motivo)
        try:
            self._entregar(cliente, mail)
        except _Queda as queda:
            if queda.etapa == ETAPA_ENTREGA:
                return unknown(queda.motivo)
            return rejected(queda.motivo)
        finally:
            _fechar(cliente)
        self.ultimo_erro = ""
        return accepted("pedido gravado na caixa postal da loja", message.id)

    def _corpo_do_pedido(self, message: Message) -> dict:
        """Os mesmos porteiros do resto da barra: numero e texto validos ou nada sai."""
        origem = validar_origem(message.origem)
        destino = normalizar_destino(message.recipient)
        texto = normalizar_texto(message.text)
        return {
            "v": VERSAO_ENVELOPE,
            "tipo": TIPO_PEDIDO,
            "referencia": str(message.id),
            "origem": origem,
            "id_externo": str(message.external_id or ""),
            "para": destino,
            "texto": texto,
            "quando": float(message.created_at or self._clock()),
        }

    def _mensagem(self, message: Message, envelope: str) -> EmailMessage:
        mail = EmailMessage()
        mail["Subject"] = f"{ASSUNTO_PREFIXO} {message.origem} {message.id}"
        mail["From"] = self.settings.endereco_remetente
        mail["To"] = self.settings.endereco_fila
        mail["Message-ID"] = f"<{message.id}@{self.settings.message_id_domain}>"
        mail.set_content(envelope)
        return mail

    def _conectar(self):
        """Abre, sobe para TLS e autentica. Cai com etapa de conexao ou de login."""
        senha = self._senha()
        host, porta = self.settings.smtp_host, self.settings.smtp_port
        seguranca = self.settings.smtp_security
        try:
            if self._smtp_factory is not None:
                cliente = self._smtp_factory(host, porta)
            elif seguranca == "ssl":
                cliente = _smtp_ssl(host, porta)
            else:
                cliente = _smtp_plano(host, porta)
            if seguranca == "starttls":
                cliente.starttls()  # type: ignore[attr-defined]
        except Exception as exc:
            raise _Queda(ETAPA_CONEXAO, f"nao deu para falar com o servidor de saida: {str(exc)[:150]}") from exc
        try:
            cliente.login(self.settings.user, senha)  # type: ignore[attr-defined]
        except Exception as exc:
            _fechar(cliente)
            raise _Queda(ETAPA_LOGIN, f"o servidor de saida recusou a credencial: {str(exc)[:150]}") from exc
        return cliente

    def _entregar(self, cliente, mail: EmailMessage) -> None:
        """Uma tentativa de entrega, classificada pelo que o servidor respondeu."""
        try:
            cliente.send_message(mail)  # type: ignore[attr-defined]
        except (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError,
            smtplib.SMTPResponseException,
        ) as exc:
            raise _Queda(ETAPA_RECUSA, f"o servidor de saida recusou o pedido: {str(exc)[:150]}") from exc
        except Exception as exc:
            # o pedido pode ter entrado sem que a resposta voltasse: duvida, nao reenvio
            raise _Queda(ETAPA_ENTREGA, f"a entrega do pedido nao deu para confirmar: {str(exc)[:150]}") from exc

    # ---------------------------------------------------------------- recepcao

    def poll_inbound(self) -> list[InboundReply]:
        if not self.ligada or not self.settings.protocolo_de_leitura:
            return []
        try:
            chave = self._chave()
            brutos, cursor = self._ler_caixa()
        except MessagingError as exc:
            self.ultimo_erro = str(exc)[:200]
            return []
        except Exception as exc:  # o motorista nunca derruba a ronda
            self.ultimo_erro = f"falha ao ler a caixa postal: {str(exc)[:180]}"
            return []
        replies: list[InboundReply] = []
        for identificador, bruto in brutos:
            carimbo = identificador or _impressao(bruto)
            if self.estado.ja_lido(carimbo):
                continue
            self.estado.marcar_lido(carimbo)
            corpo = self._abrir_mail(bruto, chave)
            reply = self._resposta_de(corpo)
            if reply is not None:
                replies.append(reply)
        if cursor is not None:
            self.estado.uid_imap = max(self.estado.uid_imap, int(cursor))
        self.estado.gravar()
        self.ultimo_erro = ""
        return replies

    def _ler_caixa(self) -> tuple[list[tuple[str, bytes]], int | None]:
        if self.settings.protocolo_de_leitura == "imap":
            return self._ler_imap()
        return self._ler_pop3(), None

    def _ler_imap(self) -> tuple[list[tuple[str, bytes]], int]:
        cliente = None
        try:
            cliente = (self._imap_factory or _imap_ssl)(self.settings.imap_host, self.settings.imap_port)
            cliente.login(self.settings.user, self._senha())  # type: ignore[attr-defined]
            cliente.select(self.settings.mailbox)  # type: ignore[attr-defined]
            alvo = f"{self.estado.uid_imap + 1}:*" if self.estado.uid_imap else "1:*"
            resposta, dados = cliente.uid("SEARCH", None, "UID", alvo)  # type: ignore[attr-defined]
            if resposta != "OK":
                raise EmailBridgeError("a caixa postal nao respondeu a busca por mensagens novas")
            brutos: list[tuple[str, bytes]] = []
            maior = self.estado.uid_imap
            for numero in _inteiros(dados):
                maior = max(maior, numero)
                bruto = _buscar_uid(cliente, numero)
                if bruto is None:
                    raise EmailBridgeError("a caixa postal nao devolveu o conteudo de um recado novo")
                brutos.append(_carimbo_de(bruto))
            return brutos, maior
        except EmailBridgeError:
            raise
        except (imaplib.IMAP4.error, OSError, ValueError) as exc:
            raise EmailBridgeError(f"falha na leitura por IMAP: {str(exc)[:180]}") from exc
        finally:
            if cliente is not None:
                try:
                    cliente.logout()  # type: ignore[attr-defined]
                except Exception:
                    pass

    def _ler_pop3(self) -> list[tuple[str, bytes]]:
        cliente = None
        try:
            cliente = (self._pop3_factory or _pop3_ssl)(self.settings.pop3_host, self.settings.pop3_port)
            cliente.user(self.settings.user)  # type: ignore[attr-defined]
            cliente.pass_(self._senha())  # type: ignore[attr-defined]
            total = int(cliente.stat()[0])  # type: ignore[attr-defined]
            primeiro = max(1, total - self.settings.max_poll_messages + 1)
            brutos: list[tuple[str, bytes]] = []
            for numero in range(primeiro, total + 1):
                linhas = cliente.retr(numero)[1]  # type: ignore[attr-defined]
                brutos.append(_carimbo_de(b"\r\n".join(linhas)))
            return brutos
        except (poplib.error_proto, OSError, ValueError) as exc:
            raise EmailBridgeError(f"falha na leitura por POP3: {str(exc)[:180]}") from exc
        finally:
            if cliente is not None:
                try:
                    cliente.quit()  # type: ignore[attr-defined]
                except Exception:
                    pass

    def _abrir_mail(self, bruto: bytes, chave: bytes) -> dict | None:
        """Devolve o envelope aberto so quando ele tem a nossa marca e confere com a chave."""
        try:
            mail = message_from_bytes(bruto)
        except Exception:
            return None
        if not _assunto_de(mail).startswith(ASSUNTO_PREFIXO):
            return None
        self.recados_da_ponte += 1
        try:
            corpo = abrir_envelope(chave, _texto_do_email(mail))
        except Exception:
            # assunto nosso com corpo que nao abre: alguem se passando pelo celular
            self.corpos_sem_abertura += 1
            return None
        if corpo.get("tipo") == TIPO_PEDIDO:
            # o pedido que nos mesmos escrevemos na caixa nao e resposta de ninguem
            return None
        return corpo

    def _resposta_de(self, corpo: dict | None) -> InboundReply | None:
        """Transforma um envelope aberto em resposta. O que nao confere fica na caixa."""
        if not corpo:
            return None
        tipo = _texto(corpo.get("tipo"))
        if tipo not in (TIPO_RESPOSTA, TIPO_COMPROVANTE):
            return None
        referencia = _texto(corpo.get("referencia"))
        quando = _numero(corpo.get("quando")) or self._clock()
        dispositivo = _texto(corpo.get("dispositivo")) or self.device_id
        try:
            if tipo == TIPO_RESPOSTA:
                remetente = normalizar_destino(corpo.get("de") or "")
                # resposta longa de cliente nao se joga fora: entra ate o tamanho da fila
                texto = normalizar_texto(str(corpo.get("texto") or "").strip()[:MAX_TEXTO])
                return InboundReply(dispositivo, remetente, texto, quando, referencia)
            destino = normalizar_destino(corpo.get("para") or "")
            estado = _texto(corpo.get("estado"))
            if estado not in ESTADOS:
                return None
            self.estado.registrar_recibo(referencia, estado)
            return InboundReply(dispositivo, destino, estado, quando, referencia)
        except ValueError:
            return None

    # -------------------------------------------------------------- correlacao

    def correlate(self, reply: InboundReply, candidates: list[MessageBrief]) -> MessageBrief | None:
        """A referencia que veio dentro do envelope cifrado e a prova do dono."""
        referencia = _texto(reply.reference)
        if not referencia:
            return None
        for candidato in candidates:
            if candidato.id == referencia:
                return candidato
        return None

    def resolve_uncertain(self, message: Message) -> SubmitResult | None:
        """Um comprovante ja lido desfaz a duvida sem reenviar o SMS."""
        estado = self.estado.recibo_de(message.id)
        if not estado:
            return None
        if estado == ESTADO_FALHOU:
            return rejected("o celular informou que o pedido falhou")
        return accepted(f"comprovante {estado} ja lido na caixa postal", message.id)

    # ------------------------------------------------------------------ painel

    def describe(self) -> dict:
        base = super().describe()
        base.update(
            {
                "ligada": self.settings.enabled,
                "conta": self.settings.user,
                "leitura": self.settings.protocolo_de_leitura,
                "recados_da_ponte": self.recados_da_ponte,
                "corpos_que_nao_abriram": self.corpos_sem_abertura,
                "recibos_guardados": len(self.estado.recibos),
                "caixa_lida_ate": self.estado.uid_imap,
            }
        )
        return base

    def shutdown(self) -> None:
        """Nada fica aberto entre uma ronda e outra: cada leitura tem conexao propria."""
        self.estado.gravar()
        return None


# ----------------------------------------------------------------- utilidades


def _fechar(cliente) -> None:
    fechar = getattr(cliente, "quit", None) or getattr(cliente, "close", None)
    if callable(fechar):
        try:
            fechar()
        except Exception:
            pass


def _inteiros(dados: object) -> list[int]:
    """IMAP devolve os UIDs espalhados em itens de bytes; aqui viram numeros."""
    itens = dados if isinstance(dados, (list, tuple)) else [dados]
    saida: list[int] = []
    for item in itens:
        if isinstance(item, bytes):
            item = item.decode("ascii", "ignore")
        for pedaco in str(item or "").split():
            try:
                saida.append(int(pedaco))
            except ValueError:
                continue
    return saida


def _buscar_uid(cliente, numero: int) -> bytes | None:
    resposta, itens = cliente.uid("FETCH", str(numero), "(BODY.PEEK[])")  # type: ignore[attr-defined]
    if resposta != "OK":
        return None
    for item in itens or []:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _carimbo_de(bruto: bytes) -> tuple[str, bytes]:
    """O Message-ID e o recado inteiro: e pelo carimbo que nao relermos o mesmo."""
    try:
        mail = message_from_bytes(bruto)
    except Exception:
        return "", bruto
    return _texto(mail.get("Message-ID")), bruto


def _impressao(bruto: bytes) -> str:
    return sha256(bruto).hexdigest()[:32]


def _assunto_de(mail) -> str:
    """O assunto que a ponte escreve e ASCII; o que vier codificado de outro jeito nao e nosso."""
    return str(mail.get("Subject") or "")


def _decodificar(parte) -> str:
    bruto = parte.get_payload(decode=True)
    if isinstance(bruto, bytes):
        charset = parte.get_content_charset() or "utf-8"
        try:
            return bruto.decode(charset, "replace")
        except LookupError:
            return bruto.decode("utf-8", "replace")
    return str(bruto or "")


def _texto_do_email(mail) -> str:
    if mail.is_multipart():
        for parte in mail.walk():
            if parte.get_content_maintype() == "text" and parte.get_content_disposition() != "attachment":
                return _decodificar(parte)
        return ""
    return _decodificar(mail)
