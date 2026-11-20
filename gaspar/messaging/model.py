"""Modelos e validacoes do contrato de mensageria.

O texto fica em portugues porque e o que o lojista ve na tela. Os campos de
identificacao (``origem`` e ``id_externo``) sao obrigatorios em todo pedido: e
por eles que a resposta volta para o sistema certo quando PDV e Hub rodam no
mesmo computador de balcao.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ORIGIN_PDV = "PDV"
ORIGIN_HUB = "HUB"
ORIGENS: tuple[str, ...] = (ORIGIN_PDV, ORIGIN_HUB)

STATUS_FILA = "fila"
STATUS_ENVIANDO = "enviando"
STATUS_ENVIADO = "enviado"
STATUS_ENTREGUE = "entregue"
STATUS_FALHOU = "falhou"
STATUS_INCERTO = "incerto"

STATUS: tuple[str, ...] = (
    STATUS_FILA,
    STATUS_ENVIANDO,
    STATUS_ENVIADO,
    STATUS_ENTREGUE,
    STATUS_FALHOU,
    STATUS_INCERTO,
)

# Estados que nao se mexem mais sem a decisao explicita do operador.
STATUS_TERMINAIS: frozenset[str] = frozenset({STATUS_ENTREGUE, STATUS_FALHOU})

EVENTO_CRIADA = "criada"
EVENTO_ENVIADA = "enviada"
EVENTO_ENTREGUE = "entregue"
EVENTO_FALHA = "falha"
EVENTO_INCERTA = "incerta"
EVENTO_RECEBIDA = "recebida"

MAX_TEXTO = 480
MIN_DIGITOS = 10
MAX_DIGITOS = 15
MAX_ID_EXTERNO = 64
MAX_CHAVE_REPETICAO = 96

_NON_DIGITS = re.compile(r"[^0-9+]")


def validar_origem(origem: object) -> str:
    """Aceita so as origens conhecidas, em qualquer grafia, e devolve a canonical."""
    text = str(origem or "").strip().upper()
    if text not in ORIGENS:
        raise ValueError(f"origem desconhecida: use {' ou '.join(ORIGENS)}")
    return text


def normalizar_destino(valor: object) -> str:
    """Deixa o numero no formato E.164 sem espaco nem simbolo sobrando."""
    if valor is None:
        raise ValueError("destino ausente")
    text = _NON_DIGITS.sub("", str(valor).strip())
    if not text:
        raise ValueError("destino ausente")
    prefix = "+" if text.startswith("+") else ""
    digits = text[1:] if prefix else text
    if not digits.isdigit() or not MIN_DIGITOS <= len(digits) <= MAX_DIGITOS:
        raise ValueError("destino invalido")
    return f"{prefix}{digits}"


def normalizar_texto(valor: object) -> str:
    if valor is None:
        raise ValueError("mensagem ausente")
    text = str(valor).strip()
    if not text:
        raise ValueError("mensagem ausente")
    if len(text) > MAX_TEXTO:
        raise ValueError(f"mensagem longa demais (maximo {MAX_TEXTO} caracteres)")
    return text


def normalizar_identificador(valor: object, campo: str, limite: int) -> str:
    text = str(valor or "").strip()
    if not text:
        raise ValueError(f"{campo} ausente")
    if len(text) > limite:
        raise ValueError(f"{campo} longo demais (maximo {limite} caracteres)")
    return text


def mascara_destino(numero: str) -> str:
    """Ultimos quatro digitos, o resto vira asterisco."""
    text = str(numero or "")
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) <= 4:
        return "****"
    return "*" * (len(digits) - 4) + digits[-4:]


@dataclass
class Message:
    """Um pedido de envio, ja com o conteudo aberto para quem pode ler."""

    id: str
    origem: str
    external_id: str
    idempotency_key: str
    recipient: str
    text: str
    status: str = STATUS_FILA
    motivo: str = ""
    transport: str = ""
    device_id: str = ""
    attempts: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    sent_at: float = 0.0
    delivered_at: float = 0.0
    finished_at: float = 0.0
    recipient_tag: str = ""

    def to_public_dict(self) -> dict:
        """Versao para o cliente: sem numero completo e sem o texto do SMS."""
        return {
            "id_mensagem": self.id,
            "origem": self.origem,
            "id_externo": self.external_id,
            "status": self.status,
            "motivo": self.motivo,
            "transporte": self.transport,
            "dispositivo": self.device_id,
            "tentativas": self.attempts,
            "destino": mascara_destino(self.recipient),
            "criado_em": self.created_at,
            "atualizado_em": self.updated_at,
            "enviado_em": self.sent_at,
            "entregue_em": self.delivered_at,
        }


@dataclass
class MessageBrief:
    """Resumo de pedido usado para casar uma resposta recebida."""

    id: str
    origem: str
    external_id: str
    created_at: float
    status: str


@dataclass
class Event:
    """Item da trilha de notificacoes de uma origem."""

    seq: int
    message_id: str
    event: str
    status: str
    motivo: str
    transport: str
    created_at: float
    external_id: str = ""

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "id_mensagem": self.message_id,
            "id_externo": self.external_id,
            "evento": self.event,
            "status": self.status,
            "motivo": self.motivo,
            "transporte": self.transport,
            "quando": self.created_at,
        }


@dataclass
class Inbound:
    """Mensagem chegada do meio fisico, possivelmente sem dono.

    Um SMS comum da operadora nao carrega ``origem`` nem ``id_externo``. Quando
    o Gaspar nao consegue provar a que pedido aquela resposta pertence, ela
    fica aqui, sem entrega a nenhum produto.
    """

    id: str
    transport: str
    device_id: str
    sender_tag: str
    text: str
    received_at: float
    origem: str = ""
    message_id: str = ""
    routed_at: float = 0.0
    reference: str = ""
    sender: str = field(default="", repr=False)

    @property
    def roteada(self) -> bool:
        return bool(self.origem)

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "transporte": self.transport,
            "dispositivo": self.device_id,
            "remetente": mascara_destino(self.sender) if self.sender else "",
            "etiqueta_remetente": self.sender_tag,
            "referencia": self.reference,
            "recebido_em": self.received_at,
            "origem": self.origem,
            "id_mensagem": self.message_id,
            "roteada": self.roteada,
        }
