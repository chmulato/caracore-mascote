"""Preferencias persistentes do Gaspar."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .paths import config_path

KEY_CHOICES = {
    "f15": "F15",
    "shift": "Shift",
    "space": "Espaço",
    "none": "Nenhuma",
}

MIN_INTERVAL = 10
MAX_INTERVAL = 3600
MIN_IDLE = 10
MAX_IDLE = 3600


@dataclass
class Settings:
    interval: int = 300
    sound: bool = False
    overlay: bool = True
    opacity: int = 82
    simulate_mouse: bool = True
    press_key: str = "f15"
    keep_teams: bool = True
    system_telemetry: bool = False
    logging: bool = True
    auto_start: bool = True
    only_when_idle: bool = True
    idle_seconds: int = 60
    pause_fullscreen: bool = True


def _clamp_interval(value: object, fallback: int = 300) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(MIN_INTERVAL, min(MAX_INTERVAL, parsed))


def load_settings(path: Path | None = None) -> Settings:
    target = path or config_path()
    settings = Settings()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings
    if not isinstance(raw, dict):
        return settings

    known = {field.name for field in fields(Settings)}
    for key, value in raw.items():
        if key not in known:
            continue
        if key == "interval":
            settings.interval = _clamp_interval(value)
        elif key == "idle_seconds":
            try:
                settings.idle_seconds = max(MIN_IDLE, min(MAX_IDLE, int(value)))
            except (TypeError, ValueError):
                settings.idle_seconds = 60
        elif key == "opacity":
            try:
                settings.opacity = max(50, min(100, int(value)))
            except (TypeError, ValueError):
                settings.opacity = 82
        elif key == "press_key":
            settings.press_key = value if value in KEY_CHOICES else "f15"
        elif isinstance(getattr(settings, key), bool):
            setattr(settings, key, bool(value))
        else:
            setattr(settings, key, value)
    return settings


def save_settings(settings: Settings, path: Path | None = None) -> None:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(settings)
    payload["interval"] = _clamp_interval(payload["interval"])
    payload["opacity"] = max(50, min(100, int(payload["opacity"])))
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp, target)
