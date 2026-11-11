"""Inicializacao automatica com o sistema operacional."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .paths import project_root

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "GasparCaraCore"


def _quote(path: str) -> str:
    return f'"{path}"'


def command_line() -> str:
    if sys.platform == "win32":
        if getattr(sys, "frozen", False):
            return f"{_quote(sys.executable)} --minimized"
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
        return f"{_quote(str(executable))} {_quote(str(project_root() / 'run.py'))} --minimized"

    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return f"{_quote(appimage)} --minimized"
    if getattr(sys, "frozen", False):
        return f"{_quote(sys.executable)} --minimized"
    return f"{_quote(sys.executable)} {_quote(str(project_root() / 'run.py'))} --minimized"


def _linux_desktop_file() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "autostart" / "gaspar.desktop"


def is_enabled() -> bool:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, VALUE_NAME)
            return True
        except OSError:
            return False
    return _linux_desktop_file().exists()


def enable() -> str | None:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command_line())
            return None
        except OSError as exc:
            return f"Nao foi possivel gravar a inicializacao automatica: {exc}"

    target = _linux_desktop_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Gaspar - Mascote Cara Core\n"
            "Comment=Presenca ativa e mascote flutuante da Cara Core\n"
            f"Exec={command_line()}\n"
            "Icon=gaspar\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
        return None
    except OSError as exc:
        return f"Nao foi possivel criar o autostart: {exc}"


def disable() -> str | None:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
            return None
        except FileNotFoundError:
            return None
        except OSError as exc:
            return f"Nao foi possivel remover a inicializacao automatica: {exc}"

    try:
        _linux_desktop_file().unlink(missing_ok=True)
        return None
    except OSError as exc:
        return f"Nao foi possivel remover o autostart: {exc}"
