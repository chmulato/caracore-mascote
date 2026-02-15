#!/usr/bin/env python3
"""
Bloqueia domínios de telemetria Microsoft / VS Code / Cursor no arquivo hosts do Windows.
Soberania do Código — Cara Core Informática.

Uso: Executar como Administrador (ex.: python block-telemetry-hosts.py).
      Opção --dry-run ou -n: simula sem escrever e sem exigir admin (para testar).
Depois: ipconfig /flushdns
"""

import os
import re
import sys

HOSTS_PATH = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "drivers", "etc", "hosts")
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


def is_admin() -> bool:
    """Retorna True se o processo está rodando com privilégios de administrador (Windows)."""
    if sys.platform != "win32":
        return os.geteuid() == 0
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def main() -> None:
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    if not dry_run and not is_admin():
        print("ERRO: Execute como Administrador (clique direito no terminal -> Executar como administrador).", file=sys.stderr)
        sys.exit(1)

    # hosts não suporta wildcard; lista já contém apenas literais
    domains_to_add = [d for d in DOMAINS if not d.startswith("*.")]

    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print(f"ERRO ao ler {HOSTS_PATH}: {e}", file=sys.stderr)
        sys.exit(1)

    if MARKER_START in content:
        content = re.sub(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\r?\n?",
            "",
            content,
            flags=re.DOTALL,
        )
        content = content.rstrip()

    block = "\n\n" + MARKER_START + "\n"
    for d in domains_to_add:
        block += f"0.0.0.0 {d}\n"
    block += MARKER_END + "\n"

    new_content = content + block

    if dry_run:
        print(f"[DRY-RUN] Seriam escritas {len(domains_to_add)} entradas em {HOSTS_PATH}.")
        print("[DRY-RUN] Últimas linhas do bloco que seria adicionado:")
        for line in block.strip().split("\n")[-5:]:
            print(" ", line)
        print("OK (simulação). Para aplicar de fato, execute como Administrador sem --dry-run.")
        return

    try:
        with open(HOSTS_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
    except OSError as e:
        print(f"ERRO ao escrever {HOSTS_PATH}: {e}", file=sys.stderr)
        sys.exit(1)

    print("Hosts atualizado. Entradas de telemetria adicionadas/atualizadas.")
    print("Execute: ipconfig /flushdns")


if __name__ == "__main__":
    main()
