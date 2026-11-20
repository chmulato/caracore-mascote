"""Motor que tira o pedido da fila e entrega ao motorista escolhido.

Aqui mora a unica chance automatica de reenvio. Ela so existe enquanto o meio
garante que nada saiu (``recusado``/``indisponivel``). Depois que o pedido passou
da mao ao meio fisico - ou o meio nao soube dizer - o pedido vira ``incerto`` e
espera conferencia humana: reenviar sozinho duplica a mensagem e a cobranca da
operadora, e trocar de meio sozinho pode mandar duas vezes.
"""

from __future__ import annotations

import threading

from .model import (
    ORIGENS,
    STATUS_ENVIADO,
    STATUS_FALHOU,
    STATUS_FILA,
    STATUS_INCERTO,
    Message,
    MessageBrief,
)
from .transport import (
    OUTCOME_ACCEPTED,
    OUTCOME_REJECTED,
    OUTCOME_UNAVAILABLE,
    OUTCOME_UNKNOWN,
    Health,
    InboundReply,
    SubmitResult,
)
from .transports import TransportRegistry

MOTIVO_MEIO_OFF = "meio desligado ou sem aparelho"
MOTIVO_RECUSA = "o meio recusou o pedido"
MOTIVO_DUVIDA = "o meio nao soube confirmar"
MOTIVO_DESCONHECIDO = "o meio devolveu um resultado que nao existe"
MOTIVO_EXCECAO = "falha ao entregar ao meio"
MOTIVO_RESPOSTA = "resposta do cliente"

_EVENTO_ENVIO = "mensageria_envio"
_EVENTO_RESPOSTA = "mensageria_resposta"


class Dispatcher:
    """Rodada justa: um pedido por origem cada vez, com o resultado do meio registrado."""

    def __init__(
        self,
        store,
        registry: TransportRegistry,
        *,
        max_attempts: int = 2,
        audit=None,
        on_log=None,
    ):
        self.store = store
        self.registry = registry
        self.max_attempts = max(1, int(max_attempts))
        self.audit = audit
        self.on_log = on_log
        self._cursor = 0
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- enviar

    def run_once(self) -> int:
        """Tenta um pedido de cada origem, alternando quem comeca. Devolve quantos tratou."""
        with self._lock:
            start = self._cursor % len(ORIGENS)
            self._cursor += 1
        handled = 0
        for origem in ORIGENS[start:] + ORIGENS[:start]:
            try:
                if self._pump(origem):
                    handled += 1
            except Exception as exc:  # a fila nao pode parar por causa de um pedido
                self._log(f"rodada da origem {origem} interrompida: {str(exc)[:120]}")
        return handled

    def _pump(self, origem: str) -> bool:
        driver = self.registry.driver_for(origem)
        if driver is None:
            return False
        message = self.store.claim_next(origem)
        if message is None:
            return False
        health = self._health_of(driver)
        if not health.available:
            self._retry_or_fail(message, health.reason or MOTIVO_MEIO_OFF, driver.name)
            return True
        try:
            result = driver.submit(message)
        except Exception as exc:
            result = SubmitResult(OUTCOME_UNKNOWN, MOTIVO_EXCECAO, str(exc)[:64])
        if not isinstance(result, SubmitResult):
            result = SubmitResult(OUTCOME_UNKNOWN, MOTIVO_DESCONHECIDO)
        self._apply(message, driver.name, result)
        return True

    def _health_of(self, driver) -> Health:
        try:
            return driver.health()
        except Exception as exc:
            return Health(False, MOTIVO_EXCECAO, str(exc)[:200])

    def _apply(self, message: Message, transport: str, result: SubmitResult) -> None:
        driver = self.registry.driver_for(message.origem)
        device = str(getattr(driver, "device_id", "") or "")
        reason = str(result.reason or "")[:200]
        reference = str(result.reference or "")[:64]
        if result.outcome == OUTCOME_ACCEPTED:
            self._set(message, STATUS_ENVIADO, reason, transport, device, reference)
            self._log(f"pedido {message.id} entregue ao meio {transport}")
            return
        if result.outcome in (OUTCOME_REJECTED, OUTCOME_UNAVAILABLE):
            self._retry_or_fail(message, reason or MOTIVO_RECUSA, transport, reference=reference)
            return
        if result.outcome == OUTCOME_UNKNOWN:
            self._set(message, STATUS_INCERTO, reason or MOTIVO_DUVIDA, transport, device, reference)
            self._log(f"pedido {message.id} ficou em duvida no meio {transport}")
            return
        self._set(message, STATUS_INCERTO, MOTIVO_DESCONHECIDO, transport, device, reference)

    def _set(
        self,
        message: Message,
        status: str,
        motivo: str,
        transport: str,
        device_id: str,
        reference: str,
    ) -> None:
        self.store.mark(
            message.id,
            status,
            motivo=motivo,
            transport=transport,
            device_id=device_id,
            reference=reference,
        )
        self._record(
            _EVENTO_ENVIO,
            id=message.id,
            origem=message.origem,
            status=status,
            motivo=motivo,
            tentativa=message.attempts,
        )

    def _retry_or_fail(
        self,
        message: Message,
        motivo: str,
        transport: str,
        *,
        reference: str = "",
    ) -> None:
        """Recoloca na fila enquanto houver tentativas; quando acabam, fecha como falhou."""
        if message.attempts < self.max_attempts:
            self._set(message, STATUS_FILA, motivo, transport, "", reference)
            self._log(f"pedido {message.id} voltou para a fila ({motivo})")
            return
        self._set(message, STATUS_FALHOU, motivo, transport, "", reference)
        self._log(f"pedido {message.id} falhou depois de {message.attempts} tentativas")

    # -------------------------------------------------------------- receber

    def drain_inbound(self) -> int:
        """Puxa o que chegou pelo meio fisico e so entrega a quem tem prova do dono."""
        fresh = 0
        for driver in self.registry.drivers():
            if not driver.supports_reception:
                continue
            try:
                replies = driver.poll_inbound() or []
            except Exception as exc:
                self._log(f"falha ao ler respostas de {driver.name}: {str(exc)[:120]}")
                continue
            for reply in replies:
                if not isinstance(reply, InboundReply):  # pragma: no cover - motorista fora do contrato
                    continue
                inbound, created = self.store.record_inbound(reply, transport=driver.name)
                if not created:
                    continue
                fresh += 1
                target = self._attribute(driver, reply, inbound.sender_tag)
                if target is None:
                    self._log(f"resposta {inbound.id} sem dono provado: fica por identificar")
                    continue
                self.store.route_inbound(inbound.id, target.origem, target.id, motivo=MOTIVO_RESPOSTA)
                self._record(
                    _EVENTO_RESPOSTA,
                    id=target.id,
                    origem=target.origem,
                    status=target.status,
                    motivo=MOTIVO_RESPOSTA,
                    tentativa=0,
                )
        return fresh

    def _attribute(self, driver, reply: InboundReply, sender_tag: str) -> MessageBrief | None:
        """Um candidato e o dono natural; mais de um so com prova dada pelo proprio meio."""
        candidates = self.store.candidates(sender_tag)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        try:
            proven = driver.correlate(reply, candidates)
        except Exception:
            return None
        if proven is None:
            return None
        for candidate in candidates:
            if candidate.id == proven.id and candidate.origem == proven.origem:
                return candidate
        return None

    # --------------------------------------------------------------- ronda

    def run_forever(self, stop: threading.Event, *, interval: float = 2.0) -> None:
        """Laco do servico: envia, recebe e dorme ate mandarem parar."""
        while not stop.is_set():
            try:
                self.run_once()
                self.drain_inbound()
            except Exception as exc:  # pragma: no cover - protecao do laco
                self._log(f"ronda da fila interrompida: {str(exc)[:120]}")
            stop.wait(max(0.2, float(interval)))

    # --------------------------------------------------------------- apoio

    def _record(self, event: str, **fields) -> None:
        if self.audit is None:
            return
        try:
            self.audit.record(event, **fields)
        except Exception:
            pass

    def _log(self, message: str) -> None:
        if self.on_log is None:
            return
        try:
            self.on_log(message)
        except Exception:
            pass
