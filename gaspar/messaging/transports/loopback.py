"""Motorista de referencia: grava o que recebeu e devolve o resultado pedido.

Nao envia nada por meio fisico algum. Serve para tres coisas:

1. provar o contrato da fila nos testes e na Fase Alpha;
2. deixar o PDV e o Hub integrando enquanto os motoristas reais chegam;
3. simular os quatro resultados (aceito, recusado, incerto, indisponivel) sem
   depender de celular, modem ou caixa postal.
"""

from __future__ import annotations

import time
from collections import deque

from gaspar.messaging.model import Message
from gaspar.messaging.transport import (
    OUTCOME_ACCEPTED,
    OUTCOME_REJECTED,
    OUTCOME_UNAVAILABLE,
    OUTCOME_UNKNOWN,
    Health,
    InboundReply,
    SmsTransportDriver,
    SubmitResult,
)

_ALIAS = {
    "aceito": OUTCOME_ACCEPTED,
    "recusado": OUTCOME_REJECTED,
    "incerto": OUTCOME_UNKNOWN,
    "indisponivel": OUTCOME_UNAVAILABLE,
}


class LoopbackTransportDriver(SmsTransportDriver):
    """Guarda os pedidos em memoria e responde o que estiver escalado."""

    name = "loopback"
    supports_reception = True
    supports_delivery_report = True

    def __init__(
        self,
        device_id: str = "loopback-0",
        available: bool = True,
        outcomes: list[SubmitResult | str] | None = None,
    ) -> None:
        self.device_id = device_id
        self.available = available
        self.submitted: list[Message] = []
        self._outcomes: deque[SubmitResult] = deque()
        self._inbound: deque[InboundReply] = deque()
        for outcome in outcomes or []:
            self.script(outcome)

    def script(self, outcome: SubmitResult | str) -> None:
        """Proximos resultados, na ordem. Nome simples vira o resultado correspondente."""
        if isinstance(outcome, SubmitResult):
            self._outcomes.append(outcome)
            return
        name = _ALIAS.get(str(outcome or "").strip(), OUTCOME_ACCEPTED)
        self._outcomes.append(SubmitResult(name, "" if name == OUTCOME_ACCEPTED else str(outcome)))

    def receive(self, sender: str, text: str, reference: str = "", when: float | None = None) -> None:
        """Atalho de teste: faz uma resposta chegar por este meio."""
        self._inbound.append(
            InboundReply(self.device_id, sender, text, time.time() if when is None else when, reference)
        )

    def health(self) -> Health:
        if not self.available:
            return Health(False, "meio desligado na configuracao")
        return Health(True, "", self.device_id)

    def submit(self, message: Message) -> SubmitResult:
        if not self.available:
            return SubmitResult(OUTCOME_UNAVAILABLE, "meio desligado na configuracao")
        self.submitted.append(message)
        if self._outcomes:
            return self._outcomes.popleft()
        return SubmitResult(OUTCOME_ACCEPTED, "loopback", message.id)

    def poll_inbound(self) -> list[InboundReply]:
        pending = list(self._inbound)
        self._inbound.clear()
        return pending
