"""Fila de envios com estado persistido e trilha local."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

STATUS_QUEUED = "fila"
STATUS_SENDING = "enviando"
STATUS_SENT = "enviado"
STATUS_DELIVERED = "entregue"
STATUS_FAILED = "falhou"

LOG_MAX_BYTES = 1_000_000


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


class SmsStore:
    def __init__(self, state_path: Path, log_path: Path, max_jobs: int = 500):
        self.state_path = Path(state_path)
        self.log_path = Path(log_path)
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

    def _append_log(self, job: SmsJob) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.log_path.exists() and self.log_path.stat().st_size >= LOG_MAX_BYTES:
                backup = self.log_path.with_suffix(self.log_path.suffix + ".1")
                os.replace(self.log_path, backup)
        except OSError:
            pass
        line = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "id": job.id,
            "status": job.status,
            "number": mask_number(job.number),
            "error": job.error,
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def add(self, job: SmsJob) -> SmsJob:
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self.max_jobs:
                old = self._order.pop(0)
                self._jobs.pop(old, None)
            self._persist()
            self._append_log(job)
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
            self._append_log(job)
            return job

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
