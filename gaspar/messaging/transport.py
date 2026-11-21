"""Interface unica dos meios de envio (padrao Strategy).

O nucleo da fila nao conhece celular, modem nem caixa postal: conhece apenas este
contrato. Entram e saem quatro resultados possiveis, e o quarto e o mais
importante:

- ``aceito``: o meio assumiu o pedido e vai devolver comprovante;
- ``recusado``: o meio garante que nada foi enviado;
- ``incerto``: o meio pode ter enviado, mas nao soube confirmar;
- ``indisponivel``: o meio esta desligado ou sem aparelho.

Depois de ``incerto`` a fila nunca reenvia sozinha e nunca troca de meio
automaticamente: isso duplicaria o SMS e a cobranca da operadora. Primeiro se
confere o que aconteceu.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .model import Message, MessageBrief

OUTCOME_ACCEPTED = "aceito"
OUTCOME_REJECTED = "recusado"
OUTCOME_UNKNOWN = "incerto"
OUTCOME_UNAVAILABLE = "indisponivel"

OUTCOMES: tuple[str, ...] = (
    OUTCOME_ACCEPTED,
    OUTCOME_REJECTED,
    OUTCOME_UNKNOWN,
    OUTCOME_UNAVAILABLE,
)


@dataclass(frozen=True)
class Health:
    """Resultado da checagem de disponibilidade de um meio."""

    available: bool
    reason: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {"disponivel": self.available, "motivo": self.reason, "detalhe": self.detail}


@dataclass(frozen=True)
class SubmitResult:
    """O que o meio devolve para a fila."""

    outcome: str
    reason: str = ""
    reference: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"resultado desconhecido: {self.outcome}")


def accepted(reason: str = "", reference: str = "") -> SubmitResult:
    return SubmitResult(OUTCOME_ACCEPTED, reason, reference)


def rejected(reason: str = "") -> SubmitResult:
    return SubmitResult(OUTCOME_REJECTED, reason)


def unknown(reason: str = "") -> SubmitResult:
    return SubmitResult(OUTCOME_UNKNOWN, reason)


def unavailable(reason: str = "") -> SubmitResult:
    return SubmitResult(OUTCOME_UNAVAILABLE, reason)


@dataclass(frozen=True)
class InboundReply:
    """Mensagem que chegou pelo meio fisico.

    O meio devolve o que ele de fato observa: numero de quem respondeu, texto,
    horario e o identificador do aparelho. ``origem`` e ``id_externo`` nao vem
    de um SMS comum - quem decide o dono e a fila, com prova.
    """

    device_id: str
    sender: str
    text: str
    received_at: float
    reference: str = ""


class SmsTransportDriver(ABC):
    """Contrato que todo motorista de envio precisa cumprir."""

    #: nome curto que aparece na configuracao e na fila (``android_lan``, ``smtp_email``, ``usb_modem``)
    name: str = "indefinido"
    #: identificador do aparelho, chip ou caixa postal que este motorista usa
    device_id: str = ""
    #: True quando o meio consegue receber mensagem (resposta do cliente)
    supports_reception: bool = False
    #: True quando o meio devolve comprovante de entrega do destinatario
    supports_delivery_report: bool = False

    @abstractmethod
    def health(self) -> Health:
        """Diz se o meio esta pronto e, se nao esta, por que nao esta."""

    @abstractmethod
    def submit(self, message: Message) -> SubmitResult:
        """Entrega o pedido ao meio fisico.

        Deve retornar ``incerto`` sempre que nao der para garantir o resultado -
        inclusive ao capturar excecao propria.
        """

    def testar_acesso(self) -> Health:
        """Prova de acesso de verdade, sem efeito colateral.

        O padrao devolve o que a configuracao diz, porque ha meio que nao tem o que
        conferir de fora (o ensaio de bancada) e meio que so saberia mentir: um envio
        de prova chegaria ao cliente. Quem tem um teste honesto - abrir conexao e
        fechar sem mandar nada - reimplementa este metodo.
        """
        return self.health()

    def poll_inbound(self) -> list[InboundReply]:
        """Mensagens recebidas desde a ultima chamada. Vazio quando nao ha recepcao."""
        return []

    def correlate(self, reply: InboundReply, candidates: list[MessageBrief]) -> MessageBrief | None:
        """Escolhe a que pedido uma resposta pertence, se o meio tiver como provar.

        O padrao devolve None: sem prova, a mensagem vai para a caixa de
        respostas por identificar, nunca para um chute.
        """
        return None

    def resolve_uncertain(self, message: Message) -> SubmitResult | None:
        """Consulta o meio sobre um envio incerto. None quando ele nao sabe dizer."""
        return None

    def shutdown(self) -> None:
        """Libera porta serial, conexoes e recursos do meio."""
        return None

    def describe(self) -> dict:
        return {
            "nome": self.name,
            "dispositivo": self.device_id,
            "recepcao": self.supports_reception,
            "comprovante_entrega": self.supports_delivery_report,
        }
