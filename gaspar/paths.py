"""Localizacao de recursos empacotados e da pasta de dados do usuario."""

from __future__ import annotations

import os
import sys
from pathlib import Path

LOG_FILENAME = "cycle_log.txt"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def asset_path(name: str) -> Path:
    candidates = [project_root() / "assets" / name]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "assets" / name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def data_dir() -> Path:
    override = os.environ.get("GASPAR_HOME")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "CaraCore" / "Gaspar" if appdata else Path.home() / "AppData" / "Roaming" / "CaraCore" / "Gaspar"
    else:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = (Path(config_home) if config_home else Path.home() / ".config") / "caracore" / "gaspar"
    base.mkdir(parents=True, exist_ok=True)
    return base


def log_path() -> Path:
    return data_dir() / LOG_FILENAME


def config_path() -> Path:
    return data_dir() / "config.json"
