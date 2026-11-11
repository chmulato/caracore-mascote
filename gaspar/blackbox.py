"""Gaspar BlackBox - interface para bloqueio de telemetria no arquivo hosts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from . import COMPANY, __version__
from .paths import asset_path
from .telemetry_hosts import (
    DOMAINS,
    apply_block,
    flush_dns,
    has_block,
    hosts_path,
    is_admin,
    read_hosts,
    remove_block,
)


def _relaunch_elevated() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes

            if getattr(sys, "frozen", False):
                parameters = ""
            else:
                parameters = "-m gaspar.blackbox"
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, parameters, None, 1
            )
            return result > 32
        except Exception:
            return False

    try:
        target = os.environ.get("APPIMAGE") or sys.executable
        if os.environ.get("APPIMAGE") or getattr(sys, "frozen", False):
            command = [target]
        else:
            command = [target, "-m", "gaspar.blackbox"]
        if not shutil.which("pkexec"):
            return False
        subprocess.Popen(["pkexec", *command])
        return True
    except Exception:
        return False


def _show_error(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


class BlackBoxApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Gaspar BlackBox - Bloqueio de telemetria")
        self.root.geometry("500x380")
        self.root.resizable(False, False)
        self._set_icon()

        header = ttk.Frame(root, padding=(20, 16, 20, 4))
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="Gaspar BlackBox",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text=f"{COMPANY} - bloqueio de telemetria na rede",
            foreground="#4b5563",
        ).pack(anchor=tk.W)

        body = ttk.Frame(root, padding=(20, 12))
        body.pack(fill=tk.BOTH, expand=True)

        self.status = ttk.Label(body, text="Verificando...", font=("Segoe UI", 11, "bold"))
        self.status.pack(anchor=tk.W, pady=(0, 2))
        self.detail = ttk.Label(
            body,
            text=f"{len(DOMAINS)} dominios monitorados",
            foreground="#6b7280",
        )
        self.detail.pack(anchor=tk.W, pady=(0, 14))

        ttk.Button(
            body,
            text="Aplicar bloqueio",
            command=self.on_apply,
            width=30,
        ).pack(pady=4)
        ttk.Button(
            body,
            text="Remover bloqueio",
            command=self.on_remove,
            width=30,
        ).pack(pady=4)
        ttk.Button(
            body,
            text="Atualizar cache DNS",
            command=self.on_flush,
            width=30,
        ).pack(pady=4)

        ttk.Label(
            body,
            text=f"Arquivo hosts: {hosts_path()}",
            foreground="#6b7280",
            wraplength=450,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(16, 0))
        ttk.Label(
            body,
            text="Requer privilegios de administrador (o app solicita elevacao).",
            foreground="#6b7280",
            wraplength=450,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 0))

        self.refresh_status()

    def _set_icon(self) -> None:
        try:
            icon = tk.PhotoImage(file=str(asset_path("gaspar.png")))
            self.root.iconphoto(True, icon)
            self.root._icon_ref = icon
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                self.root.iconbitmap(str(asset_path("gaspar.ico")))
            except Exception:
                pass

    def refresh_status(self) -> None:
        content, error = read_hosts()
        if error:
            self.status.configure(text="Erro ao ler o arquivo hosts", foreground="#b91c1c")
            return
        if has_block(content):
            self.status.configure(text="Bloqueio ativo", foreground="#15803d")
        else:
            self.status.configure(text="Bloqueio inativo", foreground="#6b7280")

    def on_apply(self) -> None:
        error = apply_block()
        if error:
            messagebox.showerror("Erro", error)
            return
        self.refresh_status()
        messagebox.showinfo(
            "Bloqueio aplicado",
            "Os dominios de telemetria agora apontam para 0.0.0.0.\n\n"
            "Recomendado: clique em 'Atualizar cache DNS'.",
        )

    def on_remove(self) -> None:
        error = remove_block()
        if error:
            messagebox.showerror("Erro", error)
            return
        self.refresh_status()
        messagebox.showinfo("Bloqueio removido", "O bloco de telemetria foi removido do arquivo hosts.")

    def on_flush(self) -> None:
        error = flush_dns()
        if error:
            messagebox.showerror("Erro", error)
            return
        messagebox.showinfo("DNS atualizado", "O cache DNS do sistema foi atualizado.")


def main() -> int:
    if not is_admin():
        if _relaunch_elevated():
            return 0
        _show_error(
            "Requer administrador",
            "Execute o Gaspar BlackBox como Administrador.\n\n"
            + ("No Windows: clique com o botao direito no icone e escolha "
               "'Executar como administrador'."
               if sys.platform == "win32"
               else "No Linux: execute com sudo ou instale o pkexec/policykit."),
        )
        return 1

    root = tk.Tk()
    BlackBoxApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
