#!/usr/bin/env python3
"""
Mascote BlackBox - Bloqueio de telemetria na rede (hosts)

Versão do Mascote que roda como Administrador e bloqueia domínios de telemetria
(Microsoft / VS Code / Cursor / Azure) no arquivo hosts do Windows.
Interface gráfica no estilo MascoteApp.

Uso: Executar como Administrador (duplo clique ou o app pode solicitar elevação).
Soberania do Código — Cara Core Informática.
"""
from __future__ import annotations

import os
import re
import sys
import tkinter as tk
from tkinter import messagebox
import subprocess

HOSTS_PATH = os.path.join(
    os.environ.get("SystemRoot", "C:\\Windows"),
    "System32", "drivers", "etc", "hosts"
)
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


def run_as_admin():
    """Reabre o script como administrador (Windows). Retorna True se relançou."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin() != 0:
            return False
        # Relançar com elevação
        exe = sys.executable
        args = " ".join(repr(a) for a in sys.argv)
        # 0 = SW_HIDE, 1 = SW_NORMAL
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, args, None, 1
        )
        if ret > 32:
            return True
    except Exception:
        pass
    return False


def hosts_has_block(content: str) -> bool:
    return MARKER_START in content and MARKER_END in content


def read_hosts() -> tuple[str, str | None]:
    """Lê o conteúdo do hosts. Retorna (conteúdo, erro)."""
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), None
    except OSError as e:
        return "", str(e)


def apply_block() -> str | None:
    """Aplica o bloqueio no hosts. Retorna None em sucesso, senão mensagem de erro."""
    content, err = read_hosts()
    if err:
        return f"Não foi possível ler o arquivo hosts: {err}"

    # Remove bloco antigo se existir
    if hosts_has_block(content):
        content = re.sub(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\r?\n?",
            "",
            content,
            flags=re.DOTALL,
        )
        content = content.rstrip()

    domains_to_add = [d for d in DOMAINS if not d.startswith("*.")]
    block = "\n\n" + MARKER_START + "\n"
    for d in domains_to_add:
        block += f"0.0.0.0 {d}\n"
    block += MARKER_END + "\n"
    new_content = content + block

    try:
        with open(HOSTS_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
    except OSError as e:
        return f"Não foi possível escrever o arquivo hosts: {e}"

    return None


def remove_block() -> str | None:
    """Remove o bloqueio do hosts. Retorna None em sucesso, senão mensagem de erro."""
    content, err = read_hosts()
    if err:
        return f"Não foi possível ler o arquivo hosts: {err}"
    if not hosts_has_block(content):
        return None  # já está removido

    new_content = re.sub(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\r?\n?",
        "",
        content,
        flags=re.DOTALL,
    )
    new_content = new_content.rstrip()

    try:
        with open(HOSTS_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
    except OSError as e:
        return f"Não foi possível escrever o arquivo hosts: {e}"

    return None


def flush_dns() -> str | None:
    """Executa ipconfig /flushdns. Retorna None em sucesso, senão mensagem de erro."""
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return None
    except Exception as e:
        return str(e)


class MascoteBlackBoxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mascote BlackBox — Bloqueio de telemetria")
        self.root.geometry("420x320")
        self.root.resizable(False, False)

        try:
            self.root.iconbitmap("mascote.ico")
        except Exception:
            pass

        # Título
        tk.Label(
            root,
            text="Bloqueio de telemetria (rede)",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(12, 4))
        self.lbl_status = tk.Label(root, text="Verificando...", fg="gray")
        self.lbl_status.pack(pady=(0, 12))

        # Botões
        self.btn_apply = tk.Button(
            root,
            text="Aplicar bloqueio",
            command=self.on_apply,
            width=22,
            font=("Segoe UI", 10),
        )
        self.btn_apply.pack(pady=6)

        self.btn_remove = tk.Button(
            root,
            text="Remover bloqueio",
            command=self.on_remove,
            width=22,
            font=("Segoe UI", 10),
        )
        self.btn_remove.pack(pady=6)

        self.btn_flush = tk.Button(
            root,
            text="Atualizar DNS (flush)",
            command=self.on_flush,
            width=22,
            font=("Segoe UI", 10),
        )
        self.btn_flush.pack(pady=6)

        tk.Label(root, text="", font=("Segoe UI", 8)).pack(pady=4)
        tk.Label(
            root,
            text="Hosts: " + HOSTS_PATH,
            font=("Segoe UI", 8),
            fg="gray",
        ).pack()

        self.refresh_status()

    def refresh_status(self):
        content, err = read_hosts()
        if err:
            self.lbl_status.config(text="Erro ao ler hosts", fg="red")
            return
        if hosts_has_block(content):
            self.lbl_status.config(text="Bloqueio ativo", fg="green")
        else:
            self.lbl_status.config(text="Bloqueio inativo", fg="gray")

    def on_apply(self):
        err = apply_block()
        if err:
            messagebox.showerror("Erro", err)
            return
        self.refresh_status()
        messagebox.showinfo(
            "Sucesso",
            "Bloqueio aplicado no arquivo hosts.\n\nRecomendado: clique em \"Atualizar DNS (flush)\".",
        )

    def on_remove(self):
        err = remove_block()
        if err:
            messagebox.showerror("Erro", err)
            return
        self.refresh_status()
        messagebox.showinfo("Sucesso", "Bloqueio removido do arquivo hosts.")

    def on_flush(self):
        err = flush_dns()
        if err:
            messagebox.showerror("Erro", f"Falha ao atualizar DNS:\n{err}")
            return
        messagebox.showinfo("Sucesso", "Cache DNS atualizado (ipconfig /flushdns).")


def main():
    if sys.platform == "win32" and not is_admin():
        if run_as_admin():
            sys.exit(0)
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Requer administrador",
            "Execute este programa como Administrador.\n\n"
            "Clique com o botão direito no ícone e escolha \"Executar como administrador\".",
        )
        sys.exit(1)

    root = tk.Tk()
    app = MascoteBlackBoxApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
