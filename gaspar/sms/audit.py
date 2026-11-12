"""Trilha de auditoria sem conteudo (LGPD).

Cada linha guarda apenas metadados: quando, qual pedido, qual venda, qual
modelo, rotulos (tags) de destino e de conteudo, situacao e motivo em codigo.
Numero, mensagem, envelope e endereco de rede nunca sao gravados aqui.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RETENTION_DAYS = 90
AUDIT_MAX_BYTES = 2_000_000
DEFAULT_FILENAME = "sms_audit.jsonl"

# Campos que nunca podem entrar na trilha.
FORBIDDEN_FIELDS = frozenset(
    {"number", "numero", "message", "mensagem", "envelope", "blob", "ip", "detail", "detalhe"}
)
ALLOWED_FIELDS = frozenset(
    {
        "id",
        "venda",
        "modelo",
        "destino",
        "conteudo",
        "status",
        "motivo",
        "tentativa",
        "selado",
        "origem",
        "operador",
    }
)


def _iso(moment: float) -> str:
    return datetime.fromtimestamp(moment, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(text: object) -> float:
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return 0.0


class AuditLog:
    def __init__(self, path: Path, retention_days: int = DEFAULT_RETENTION_DAYS, max_bytes: int = AUDIT_MAX_BYTES):
        self.path = Path(path)
        self.retention_days = max(1, int(retention_days))
        self.max_bytes = max(4096, int(max_bytes))
        self._lock = threading.Lock()

    def record(self, event: str, **fields) -> None:
        unknown = set(fields) - ALLOWED_FIELDS
        if unknown:
            raise ValueError(f"campo nao permitido na auditoria: {sorted(unknown)[0]}")
        if set(fields) & FORBIDDEN_FIELDS:
            raise ValueError("a auditoria nao registra conteudo")
        line = {"ts": _iso(time.time()), "evento": str(event or "")[:24]}
        for key in ALLOWED_FIELDS:
            if key not in fields:
                continue
            value = fields[key]
            if isinstance(value, bool):
                line[key] = value
            elif isinstance(value, int):
                line[key] = int(value)
            elif isinstance(value, str) and value:
                line[key] = value[:64]
        payload = json.dumps(line, ensure_ascii=False)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                    backup = self.path.with_suffix(self.path.suffix + ".1")
                    os.replace(self.path, backup)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(payload + "\n")
            except OSError:
                pass

    def entries(self, limit: int = 20) -> list[dict]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        result = []
        for raw in lines[-max(0, limit) :]:
            try:
                item = json.loads(raw)
            except ValueError:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    def count(self) -> int:
        try:
            return sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            return 0

    def purge(self, now: float | None = None) -> int:
        """Apaga o que passou do prazo de retencao. Devolve quantas linhas ficaram."""
        cutoff = (now if now is not None else time.time()) - self.retention_days * 86400
        with self._lock:
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return 0
            kept = []
            for raw in lines:
                try:
                    item = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(item, dict):
                    continue
                if _parse_iso(item.get("ts")) >= cutoff:
                    kept.append(raw)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                tmp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                return len(kept)
            return len(kept)

    def erase(self) -> None:
        """Direito ao esquecimento: apaga a trilha inteira."""
        with self._lock:
            for target in (self.path, self.path.with_suffix(self.path.suffix + ".1")):
                try:
                    target.unlink()
                except OSError:
                    pass
