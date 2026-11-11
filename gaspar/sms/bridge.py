"""Orquestra a fila, os limites e o envio para o celular."""

from __future__ import annotations

import queue
import re
import threading
import time
from collections import deque
from datetime import date

from .client import PhoneClient, PhoneOffline, SendResult
from .config import SmsConfig
from .crypto import key_from_base64
from .discovery import discover
from .store import SmsJob, SmsStore, STATUS_FAILED, STATUS_QUEUED, STATUS_SENDING, STATUS_SENT, mask_number


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

    def enqueue(self, number: object, message: object, venda_id: object = "") -> SmsJob:
        normalized_number = normalize_number(number)
        normalized_message = normalize_message(message)
        sale_id = str(venda_id or "").strip()[:64]
        existing = self.store.find_by_venda(sale_id)
        if existing is not None:
            return existing
        self._check_limits()
        if self._queue.qsize() >= self.max_queue:
            raise QueueFull("fila cheia")
        job = SmsJob.create(normalized_number, normalized_message, sale_id)
        self.store.add(job)
        self._queue.put(job.id)
        self._log(f"SMS para {mask_number(normalized_number)} entrou na fila.")
        return job

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

    def _check_limits(self) -> None:
        now = time.time()
        with self._lock:
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
            self._request_times.append(now)
            self._day_count += 1

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

    def _attempt(self, job: SmsJob) -> None:
        attempts = job.attempts + 1
        self.store.update(job.id, status=STATUS_SENDING, attempts=attempts, error="")
        try:
            host, port = self._target()
            key = key_from_base64(self.config.shared_secret_b64)
            client = self._client_factory(host, port, key)
            result = client.send(job.number, job.message, job.id, job.created_at)
            if not isinstance(result, SendResult):
                result = SendResult(acknowledged=bool(result))
            self.store.update(job.id, status=STATUS_SENT, confirmed=result.acknowledged, error="")
            self._mark_online()
            suffix = "com confirmacao" if result.acknowledged else "sem confirmacao do celular"
            self._log(f"SMS para {mask_number(job.number)} entregue ao celular ({suffix}).")
        except PhoneOffline as exc:
            self._online = False
            if attempts < self.max_attempts and time.time() - job.created_at < 600:
                self.store.update(job.id, status=STATUS_QUEUED, error=str(exc))
                self._log(f"Celular sem resposta; nova tentativa em {self.retry_delay:.0f}s.")
                self._stop.wait(self.retry_delay)
                if not self._stop.is_set():
                    self._queue.put(job.id)
            else:
                self.store.update(job.id, status=STATUS_FAILED, error=str(exc))
                self._log(f"Falha ao enviar para {mask_number(job.number)}: {exc}.")
        except Exception as exc:
            self.store.update(job.id, status=STATUS_FAILED, error=str(exc))
            self._log(f"Falha ao enviar para {mask_number(job.number)}: {exc}.")
