"""Orquestra a fila, os limites e o envio para o celular."""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from collections import deque
from datetime import date

from . import e2e
from .client import PhoneClient, PhoneOffline, SendResult
from .config import SmsConfig
from .crypto import key_from_base64
from .discovery import discover
from .store import (
    SmsJob,
    SmsStore,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_SENDING,
    STATUS_SENT,
)
from .templates import render_template


class BridgeError(Exception):
    """Falha ao aceitar um pedido de envio."""


class InvalidMessage(BridgeError):
    pass


class RateLimited(BridgeError):
    pass


class QueueFull(BridgeError):
    pass


def normalize_number(raw: object) -> str:
    if raw is None:
        raise InvalidMessage("numero ausente")
    text = str(raw).strip()
    if not text:
        raise InvalidMessage("numero ausente")
    cleaned = re.sub(r"[^0-9+]", "", text)
    if cleaned.count("+") > 1 or ("+" in cleaned and not cleaned.startswith("+")):
        raise InvalidMessage("numero invalido")
    digits = cleaned[1:] if cleaned.startswith("+") else cleaned
    if not digits.isdigit() or not 10 <= len(digits) <= 15:
        raise InvalidMessage("numero invalido")
    return f"+{digits}" if cleaned.startswith("+") else digits


def normalize_message(raw: object) -> str:
    if raw is None:
        raise InvalidMessage("mensagem ausente")
    text = str(raw)
    if not text.strip():
        raise InvalidMessage("mensagem ausente")
    if len(text) > 480:
        raise InvalidMessage("mensagem acima de 480 caracteres")
    return text


class SmsBridge:
    def __init__(
        self,
        config: SmsConfig,
        store: SmsStore,
        client_factory=None,
        discovery_fn=discover,
        retry_delay: float = 5.0,
        max_attempts: int = 2,
        max_queue: int = 100,
        on_log=None,
    ):
        self.config = config
        self.store = store
        self.retry_delay = max(0.0, retry_delay)
        self.max_attempts = max(1, max_attempts)
        self.max_queue = max(1, max_queue)
        self.discovery_timeout = 1.6
        self._client_factory = client_factory or (lambda host, port, key: PhoneClient(host, port, key))
        self._discovery = discovery_fn
        self._on_log = on_log
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._lock = threading.RLock()
        self._request_times: deque[float] = deque()
        self._day = date.today()
        self._day_count = 0
        self._online = False
        self._last_seen = 0.0
        self.base_url = ""
        self.store.audit.purge()
        self._restore_pending()

    def _restore_pending(self) -> None:
        for job in reversed(self.store.recent(self.store.max_jobs)):
            if job.status == STATUS_SENDING:
                self.store.update(job.id, status=STATUS_FAILED, error="envio interrompido ao fechar o Gaspar")
            elif job.status == STATUS_QUEUED:
                self._queue.put(job.id)

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="gaspar-sms", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        worker = self._worker
        if worker is not None:
            worker.join(timeout=3.0)
        self._worker = None

    def enqueue(
        self,
        number: object,
        message: object = None,
        venda_id: object = "",
        template: object = "",
        variables: object = None,
        manual: bool = False,
    ) -> SmsJob:
        normalized_number = normalize_number(number)
        sale_id = str(venda_id or "").strip()[:64]
        existing = self.store.find_by_venda(sale_id)
        if existing is not None:
            return existing
        template_id = str(template or "").strip()[:32]
        if template_id:
            try:
                normalized_message = render_template(template_id, variables)
            except ValueError as exc:
                raise InvalidMessage(str(exc)) from exc
        elif self.config.only_templates and not manual:
            raise InvalidMessage("envio fora do modelo de mensagem nao permitido")
        else:
            normalized_message = normalize_message(message)
        # A trilha compara rotulos, nao o numero nem o texto.
        audit_key = self.config.audit_key()
        recipient_tag = e2e.tag(audit_key, normalized_number)
        content_tag = e2e.tag(audit_key, normalized_message)
        with self._lock:
            if self._queue.qsize() >= self.max_queue:
                raise QueueFull("fila cheia")
            duplicate = self._check_limits(recipient_tag, content_tag, manual)
            if duplicate is not None:
                self._log(f"Pedido repetido ({recipient_tag[:8]}) ignorado.")
                return duplicate
            job = SmsJob.create(normalized_number, normalized_message, sale_id)
            job.recipient_tag = recipient_tag
            job.content_tag = content_tag
            job.template = template_id
            job.actor = "painel" if manual else "pdv"
            if self.config.has_phone_key():
                self._seal(job, normalized_number, normalized_message)
            elif self.config.e2e_required:
                raise InvalidMessage("celular sem chave de criptografia; pareie o celular de novo")
            self.store.add(job)
            self._queue.put(job.id)
        self._log(f"Pedido {job.id[:8]} entrou na fila ({recipient_tag[:8]}).")
        return job

    def _seal(self, job: SmsJob, number: str, message: str) -> None:
        """Fecha o conteudo no envelope do celular e descarta o texto local."""
        peer = self.config.phone_public_key()
        if not peer:
            raise InvalidMessage("celular sem chave de criptografia; pareie o celular de novo")
        payload = json.dumps(
            {"number": number, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            envelope = e2e.seal(peer, payload, job.id.encode("ascii"))
        except e2e.E2EError as exc:
            raise InvalidMessage(str(exc)) from exc
        key = self.config.audit_key()
        job.envelope = envelope
        job.sealed = True
        job.recipient_tag = job.recipient_tag or e2e.tag(key, number)
        job.content_tag = job.content_tag or e2e.tag(key, message)
        job.number = ""
        job.message = ""

    def erase_history(self) -> dict:
        """Direito ao esquecimento: apaga pedidos e trilha de auditoria."""
        with self._lock:
            removed = self.store.clear()
            self.store.audit.erase()
        self._log("Historico de SMS apagado a pedido do operador.")
        return {"jobs": removed}

    def refresh_phone(self) -> dict:
        found = self._discovery(self.discovery_timeout)
        if not found:
            self._online = False
            self._log("Nenhum celular respondeu na rede.")
            return {"found": False, "count": 0}
        host, port = found[0]
        with self._lock:
            self.config.phone_host = host
            self.config.phone_port = port
        self.config.save()
        self._mark_online()
        self._log(f"Celular encontrado em {host}:{port}.")
        return {"found": True, "count": len(found), "host": host, "port": port}

    def stats(self) -> dict:
        with self._lock:
            online = self._online
            last_seen = self._last_seen
        return {
            "enabled": self.config.enabled,
            "phone": {
                "host": self.config.phone_host,
                "port": self.config.phone_port,
                "online": online,
                "last_seen": last_seen,
            },
            "queue": self._queue.qsize(),
            "counts": self.store.counts(),
            "e2e": {
                "required": bool(self.config.e2e_required),
                "phone_key": self.config.has_phone_key(),
                "fingerprint": self.config.phone_key_fingerprint(),
            },
        }

    def _log(self, message: str) -> None:
        if self._on_log is not None:
            try:
                self._on_log(message)
            except Exception:
                pass

    def _mark_online(self) -> None:
        with self._lock:
            self._online = True
            self._last_seen = time.time()

    def _check_limits(self, recipient_tag: str, content_tag: str, manual: bool) -> SmsJob | None:
        now = time.time()
        while self._request_times and now - self._request_times[0] >= 60:
            self._request_times.popleft()
        if len(self._request_times) >= self.config.max_per_minute:
            raise RateLimited("limite por minuto atingido")
        today = date.today()
        if today != self._day:
            self._day = today
            self._day_count = 0
        if self._day_count >= self.config.max_per_day:
            raise RateLimited("limite diario atingido")
        if not manual:
            recent = self.store.recent(self.store.max_jobs)
            duplicate_window = max(0, self.config.duplicate_window_minutes) * 60
            if duplicate_window:
                for job in recent:
                    if job.recipient_tag != recipient_tag or job.content_tag != content_tag:
                        continue
                    if job.status == STATUS_FAILED:
                        continue
                    if now - job.created_at <= duplicate_window:
                        return job
            hour_count = sum(
                1
                for job in recent
                if job.recipient_tag == recipient_tag and now - job.created_at < 3600
            )
            if hour_count >= self.config.per_number_per_hour:
                raise RateLimited("limite por numero por hora atingido")
            day_count = sum(
                1
                for job in recent
                if job.recipient_tag == recipient_tag and now - job.created_at < 86400
            )
            if day_count >= self.config.per_number_per_day:
                raise RateLimited("limite por numero por dia atingido")
        self._request_times.append(now)
        self._day_count += 1
        return None

    def _target(self) -> tuple[str, int]:
        with self._lock:
            host = (self.config.phone_host or "").strip()
            port = self.config.phone_port
        if host:
            return host, port
        if self.refresh_phone().get("found"):
            return self.config.phone_host, self.config.phone_port
        raise PhoneOffline("celular nao encontrado na rede")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if job_id is None:
                break
            job = self.store.get(job_id)
            if job is None or job.status not in (STATUS_QUEUED,):
                continue
            self._attempt(job)

    def _label(self, job: SmsJob) -> str:
        return job.recipient_tag[:8] or job.id[:8]

    def _attempt(self, job: SmsJob) -> None:
        attempts = job.attempts + 1
        self.store.update(job.id, status=STATUS_SENDING, attempts=attempts, error="", reason="")
        try:
            if not job.envelope and self.config.has_phone_key():
                if not job.number or not job.message:
                    raise InvalidMessage("pedido sem conteudo para enviar")
                try:
                    self._seal(job, job.number, job.message)
                except InvalidMessage as exc:
                    self.store.update(job.id, status=STATUS_FAILED, error=str(exc), reason="sem_chave")
                    self._log(f"Pedido {self._label(job)} nao enviado: {exc}.")
                    return
                self.store.update(
                    job.id,
                    envelope=job.envelope,
                    sealed=True,
                    number="",
                    message="",
                    recipient_tag=job.recipient_tag,
                    content_tag=job.content_tag,
                )
            host, port = self._target()
            key = key_from_base64(self.config.shared_secret_b64)
            client = self._client_factory(host, port, key)
            result = client.send(
                job.envelope,
                job.id,
                job.created_at,
                base_url=self.base_url,
                sequence=self.config.next_command_sequence(),
                number="" if job.sealed else job.number,
                message="" if job.sealed else job.message,
            )
            if not isinstance(result, SendResult):
                result = SendResult(acknowledged=bool(result))
            ack = result.ack if isinstance(result.ack, dict) else None
            self._learn_phone_key(ack)
            if ack is not None and ack.get("ok") is False:
                reason = str(ack.get("error") or "celular recusou o pedido")[:200]
                self.store.update(job.id, status=STATUS_FAILED, confirmed=False, error=reason, reason="recusado")
                self._mark_online()
                self._log(f"Celular recusou o pedido {self._label(job)}: {reason}.")
                return
            current = self.store.get(job.id)
            if current is not None and current.status in (STATUS_DELIVERED, STATUS_FAILED):
                self._mark_online()
                return
            self.store.update(
                job.id,
                status=STATUS_SENT,
                confirmed=result.acknowledged,
                sent_at=time.time(),
                error="",
            )
            self._mark_online()
            suffix = "com confirmacao" if result.acknowledged else "sem confirmacao do celular"
            self._log(f"Pedido {self._label(job)} entregue ao celular ({suffix}).")
        except PhoneOffline as exc:
            self._online = False
            if attempts < self.max_attempts and time.time() - job.created_at < 600:
                self.store.update(job.id, status=STATUS_QUEUED, error=str(exc), reason="celular_fora")
                self._log(f"Celular sem resposta; nova tentativa em {self.retry_delay:.0f}s.")
                self._stop.wait(self.retry_delay)
                if not self._stop.is_set():
                    self._queue.put(job.id)
            else:
                self.store.update(job.id, status=STATUS_FAILED, error=str(exc), reason="celular_fora")
                self._log(f"Falha ao enviar o pedido {self._label(job)}: {exc}.")
        except Exception as exc:
            self.store.update(job.id, status=STATUS_FAILED, error=str(exc), reason="falha_envio")
            self._log(f"Falha ao enviar o pedido {self._label(job)}: {exc}.")

    def _learn_phone_key(self, ack: dict | None) -> None:
        """O celular devolve a chave publica no recibo; serve para reencontrar o aparelho."""
        if not isinstance(ack, dict):
            return
        key = ack.get("key")
        if not key or not self.config.set_phone_public_key(key):
            return
        self.config.save()
        self._log(f"Chave de criptografia do celular registrada ({self.config.phone_key_fingerprint()}).")

    def apply_receipt(self, job_id: str, event: str, detail: str = "") -> SmsJob | None:
        """Atualiza o pedido com o comprovante vindo do celular."""
        if event not in ("sent", "delivered", "failed"):
            return None
        job = self.store.get(job_id)
        if job is None:
            return None
        detail = str(detail or "").strip()[:200]
        now = time.time()
        if event == "delivered":
            if job.status == STATUS_FAILED:
                return job
            job = self.store.update(
                job_id,
                status=STATUS_DELIVERED,
                delivered_at=now,
                confirmed=True,
                receipt_detail=detail,
            )
            self._log(f"Operadora confirmou a entrega do pedido {self._label(job)}.")
            return job
        if event == "sent":
            if job.status in (STATUS_DELIVERED, STATUS_FAILED):
                return job
            job = self.store.update(
                job_id,
                status=STATUS_SENT,
                confirmed=True,
                sent_at=job.sent_at or now,
                receipt_detail=detail,
            )
            self._log(f"Celular aceitou o pedido {self._label(job)}.")
            return job
        if job.status == STATUS_DELIVERED:
            return job
        job = self.store.update(
            job_id,
            status=STATUS_FAILED,
            confirmed=False,
            receipt_detail=detail,
            error=detail or "celular nao conseguiu enviar",
            reason="recusado",
        )
        self._log(
            f"Celular nao conseguiu enviar o pedido {self._label(job)}: {detail or 'sem detalhe'}."
        )
        return job
