"""Bloqueio de dominios de telemetria no arquivo hosts (Windows e Linux)."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MARKER_START = "# BLOCK TELEMETRIA - INICIO (Cara Core Black-Box)"
MARKER_END = "# BLOCK TELEMETRIA - FIM"

DOMAINS = [
    "vortex.data.microsoft.com",
    "vortex-win.data.microsoft.com",
    "settings.data.microsoft.com",
    "watson.telemetry.microsoft.com",
    "telemetry.microsoft.com",
    "dc.services.visualstudio.com",
    "dc.trafficmanager.net",
    "vscode.dev",
    "marketplace.visualstudio.com",
    "login.microsoftonline.com",
    "management.azure.com",
    "global.azure.microsoft.com",
    "flighting.onecollector.microsoft.com",
    "onecollector.microsoft.com",
    "mobile.events.data.microsoft.com",
    "self.events.data.microsoft.com",
    "v20.events.data.microsoft.com",
    "us-v20.events.data.microsoft.com",
    "oca.telemetry.microsoft.com",
    "reports.feedback.azure.com",
    "survey.watson.microsoft.com",
    "watson.microsoft.com",
    "telemetry.visualstudio.com",
    "default.exp-tas.com",
    "activity.windows.com",
    "t.telemetry.microsoft.com",
    "ceuswatcab01.blob.core.windows.net",
    "ceuswatcab02.blob.core.windows.net",
    "eaus2watcab01.blob.core.windows.net",
    "eaus2watcab02.blob.core.windows.net",
    "wus2watcab01.blob.core.windows.net",
    "wus2watcab02.blob.core.windows.net",
    "applicationinsights.microsoft.com",
    "monitor.azure.com",
]


def hosts_path() -> Path:
    if sys.platform == "win32":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        return Path(system_root) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def is_admin() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes

            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def read_hosts(path: Path | None = None) -> tuple[str, str | None]:
    target = path or hosts_path()
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(), None
    except OSError as exc:
        return "", str(exc)


def has_block(content: str) -> bool:
    return MARKER_START in content and MARKER_END in content


def _strip_block(content: str) -> str:
    pattern = re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\r?\n?"
    return re.sub(pattern, "", content, flags=re.DOTALL)


def _write_hosts(target: Path, content: str) -> str | None:
    try:
        with open(target, "w", encoding="utf-8", errors="replace", newline="") as handle:
            handle.write(content)
        return None
    except OSError as exc:
        return f"Nao foi possivel escrever {target}: {exc}"


def apply_block(path: Path | None = None) -> str | None:
    target = path or hosts_path()
    content, error = read_hosts(target)
    if error:
        return f"Nao foi possivel ler {target}: {error}"

    newline = "\r\n" if "\r\n" in content else "\n"
    cleaned = _strip_block(content).rstrip("\r\n")
    lines = [MARKER_START]
    lines.extend(f"0.0.0.0 {domain}" for domain in DOMAINS)
    lines.append(MARKER_END)
    new_content = cleaned + newline * 2 + newline.join(lines) + newline
    return _write_hosts(target, new_content)


def remove_block(path: Path | None = None) -> str | None:
    target = path or hosts_path()
    content, error = read_hosts(target)
    if error:
        return f"Nao foi possivel ler {target}: {error}"
    if not has_block(content):
        return None

    newline = "\r\n" if "\r\n" in content else "\n"
    new_content = _strip_block(content).rstrip("\r\n") + newline
    return _write_hosts(target, new_content)


def flush_dns() -> str | None:
    if sys.platform == "win32":
        commands = [["ipconfig", "/flushdns"]]
    else:
        commands = [
            ["resolvectl", "flush-caches"],
            ["systemd-resolve", "--flush-caches"],
            ["nscd", "-i", "hosts"],
        ]

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    attempts: list[str] = []
    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=creationflags,
            )
        except Exception as exc:
            attempts.append(f"{command[0]}: {exc}")
            continue
        if result.returncode == 0:
            return None
        attempts.append(f"{command[0]}: {result.stderr.strip() or result.returncode}")

    detail = "; ".join(attempts) if attempts else "nenhum comando disponivel"
    return f"Falha ao atualizar o cache DNS ({detail})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bloqueia dominios de telemetria no arquivo hosts."
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="simula sem escrever")
    parser.add_argument("--remove", action="store_true", help="remove o bloco de bloqueio")
    parser.add_argument("--status", action="store_true", help="mostra o estado atual")
    parser.add_argument("--hosts", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    target = args.hosts or hosts_path()
    content, error = read_hosts(target)
    if error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1

    if args.status:
        state = "ativo" if has_block(content) else "inativo"
        print(f"Bloqueio {state} em {target} ({len(DOMAINS)} dominios).")
        return 0

    if not args.dry_run and not is_admin():
        if sys.platform == "win32":
            print("ERRO: execute como Administrador.", file=sys.stderr)
        else:
            print("ERRO: execute como root (sudo).", file=sys.stderr)
        return 1

    if args.dry_run:
        if args.remove:
            action = "removeria o bloco" if has_block(content) else "nao encontrou bloco para remover"
        else:
            action = f"gravaria {len(DOMAINS)} dominios"
        print(f"[DRY-RUN] {action} em {target}.")
        return 0

    error = remove_block(target) if args.remove else apply_block(target)
    if error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1

    if args.remove:
        print(f"Bloqueio removido de {target}.")
    else:
        print(f"Hosts atualizado em {target} ({len(DOMAINS)} dominios).")
        print("Recomendado: atualizar o cache DNS (ipconfig /flushdns ou resolvectl flush-caches).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
