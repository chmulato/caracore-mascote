"""Fila de envios com estado persistido e trilha local."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .audit import AuditLog

STATUS_QUEUED = "fila"
STATUS_SENDING = "enviando"
STATUS_SENT = "enviado"
STATUS_DELIVERED = "entregue"
STATUS_FAILED = "falhou"


def mask_number(number: str) -> str:
    text = str(number or "")
    if len(text) <= 4:
        return "****"
    return "*" * (len(text) - 4) + text[-4:]


@dataclass
class SmsJob:
    id: str
    number: str
    message: str
    created_at: float
    updated_at: float
    status: str = STATUS_QUEUED
    attempts: int = 0
    error: str = ""
    venda_id: str = ""
    confirmed: bool = False
    sent_at: float = 0.0
    delivered_at: float = 0.0
    receipt_detail: str = ""
    recipient_tag: str = ""
    content_tag: str = ""
    template: str = ""
    actor: str = ""
    sealed: bool = False
    envelope: str = ""
    reason: str = ""

    @classmethod
    def create(cls, number: str, message: str, venda_id: str = "") -> "SmsJob":
        now = time.time()
        return cls(
            id=uuid.uuid4().hex,
            number=number,
            message=message,
            created_at=now,
            updated_at=now,
            venda_id=venda_id,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_public_dict(self) -> dict:
        """Versao para o PDV: sem numero, sem texto e sem o envelope cifrado."""
        data = asdict(self)
        for key in ("number", "message", "envelope", "receipt_detail"):
            data.pop(key, None)
        return data


class SmsStore:
    def __init__(self, state_path: Path, audit: AuditLog, max_jobs: int = 500):
        self.state_path = Path(state_path)
        self.audit = audit
        self.max_jobs = max_jobs
        self._lock = threading.RLock()
        self._jobs: dict[str, SmsJob] = {}
        self._order: list[str] = []
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, list):
            return
        known = {item.name for item in fields(SmsJob)}
        for entry in raw[-self.max_jobs :]:
            if not isinstance(entry, dict):
                continue
            try:
                job = SmsJob(**{key: value for key, value in entry.items() if key in known})
            except (TypeError, ValueError):
                continue
            self._jobs[job.id] = job
            self._order.append(job.id)

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [self._jobs[job_id].to_dict() for job_id in self._order if job_id in self._jobs]
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def _audit(self, job: SmsJob) -> None:
        self.audit.record(
            job.status,
            id=job.id,
            venda=job.venda_id,
            modelo=job.template,
            destino=job.recipient_tag,
            conteudo=job.content_tag,
            status=job.status,
            motivo=job.reason,
            tentativa=job.attempts,
            selado=job.sealed,
            origem=job.actor or "pdv",
        )

    def add(self, job: SmsJob) -> SmsJob:
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self.max_jobs:
                old = self._order.pop(0)
                self._jobs.pop(old, None)
            self._persist()
            self._audit(job)
        return job

    def update(self, job_id: str, **changes) -> SmsJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in changes.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()
            self._persist()
            self._audit(job)
            return job

    def clear(self) -> int:
        """Apaga os pedidos guardados (o historico de auditoria e apagado a parte)."""
        with self._lock:
            removed = len(self._jobs)
            self._jobs.clear()
            self._order.clear()
            self._persist()
            return removed

    def get(self, job_id: str) -> SmsJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def find_by_venda(self, venda_id: str, max_age: float = 86400) -> SmsJob | None:
        if not venda_id:
            return None
        limit = time.time() - max_age
        with self._lock:
            for job_id in reversed(self._order):
                job = self._jobs.get(job_id)
                if job and job.venda_id == venda_id and job.created_at >= limit and job.status != STATUS_FAILED:
                    return job
        return None

    def recent(self, limit: int = 10) -> list[SmsJob]:
        with self._lock:
            ids = list(reversed(self._order))[: max(0, limit)]
            return [self._jobs[job_id] for job_id in ids if job_id in self._jobs]

    def counts(self) -> dict:
        with self._lock:
            result = {
                STATUS_QUEUED: 0,
                STATUS_SENDING: 0,
                STATUS_SENT: 0,
                STATUS_DELIVERED: 0,
                STATUS_FAILED: 0,
            }
            for job in self._jobs.values():
                if job.status in result:
                    result[job.status] += 1
            return result
