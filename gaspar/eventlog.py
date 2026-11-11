"""Registro de eventos em arquivo, com rotacao simples."""

from __future__ import annotations

import datetime
import threading
from pathlib import Path

MAX_BYTES = 1_000_000


class EventLog:
    def __init__(self, path: Path, enabled: bool = True):
        self.path = Path(path)
        self.enabled = enabled
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            try:
                self.path.write_text("Log de ciclos iniciado (Gaspar).\n", encoding="utf-8")
            except OSError:
                pass

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def write(self, label: str, message: str) -> str:
        line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} - {label}: {message}"
        if not self.enabled:
            return line
        with self._lock:
            try:
                self._rotate_if_needed()
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError:
                pass
        return line

    def _rotate_if_needed(self) -> None:
        try:
            if self.path.stat().st_size < MAX_BYTES:
                return
            backup = self.path.with_suffix(self.path.suffix + ".1")
            if backup.exists():
                backup.unlink()
            self.path.rename(backup)
        except OSError:
            pass
