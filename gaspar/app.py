"""Painel principal do Gaspar - Mascote Cara Core."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from . import COMPANY, __version__
from . import autostart, updates
from .config import (
    KEY_CHOICES,
    MAX_INTERVAL,
    MIN_INTERVAL,
    Settings,
    load_settings,
    save_settings,
)
from .eventlog import EventLog
from .overlay import GasparOverlay
from .paths import asset_path, data_dir, log_path, project_root
from .presence import PresenceEngine
from .tray import create_tray

try:
    from .sms.audit import AuditLog
    from .sms.bridge import InvalidMessage, QueueFull, RateLimited, SmsBridge
    from .sms.config import load_config as load_sms_config
    from .sms.network import lan_ip
    from .sms.qr import make_qr
    from .sms.server import SmsHttpServer
    from .sms.store import SmsStore

    SMS_AVAILABLE = True
    SMS_IMPORT_ERROR = ""
except Exception as _sms_import_error:
    SMS_AVAILABLE = False
    SMS_IMPORT_ERROR = str(_sms_import_error)

KEY_LABELS = list(KEY_CHOICES.values())
LABEL_TO_KEY = {label: key for key, label in KEY_CHOICES.items()}


class GasparApp:
    def __init__(self, root: tk.Tk, start_minimized: bool = False):
        self.root = root
        self.start_minimized = start_minimized
        self.closing = False
        self.settings: Settings = load_settings()
        self._panel_visible = not start_minimized
        self.log = EventLog(log_path(), enabled=self.settings.logging)
        self.tray_icon = None
        self.overlay: GasparOverlay | None = None
        self._logo = None
        self._opacity_job = None
        self.sms_config = None
        self.sms_audit = None
        self.sms_store = None
        self.sms_bridge = None
        self.sms_server = None
        self._sms_qr_photo = None
        self._sms_poll_job = None
        self._sms_signature = None
        self._sms_window = None
        self._sms_qr_window = None
        self._sms_qr_image_label = None
        self._logs_window = None
        self.events_text = None
        self.system_text = None
        self._events_backlog: list[str] = []
        self._system_backlog: list[str] = []
        self.update_info = None
        self._update_vigia = None
        self._update_worker = None

        self.engine = PresenceEngine(
            settings_provider=lambda: self.settings,
            log_event=self.log_event,
            log_system=self.log_system,
            bell=self._bell,
        )

        self._build_ui()
        self._wire_events()
        self._apply_overlay_state()
        self._set_status()
        self.root.after(350, self._init_tray)
        self.root.after(700, self._maybe_auto_start)
        self.root.after(500, self._tick)
        self.root.after(450, self._init_sms)
        self.root.after(1200, self._init_updates)

        self.log_event("Aplicacao iniciada.")

    def _build_ui(self) -> None:
        self.root.title(f"{COMPANY} - Gaspar")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        height = min(760, max(560, screen_height - 80))
        x = max(0, (screen_width - 600) // 2)
        y = max(0, (screen_height - height) // 3)
        self.root.geometry(f"600x{height}+{x}+{y}")
        self.root.minsize(560, 520)
        self._set_window_icon()

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Brand.TLabel", font=("Segoe UI", 22, "bold"), foreground="#3f6b00")
        style.configure("Sub.TLabel", foreground="#4b5563")
        style.configure("Hint.TLabel", foreground="#6b7280")
        style.configure("Value.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("StatusOn.TLabel", font=("Segoe UI", 12, "bold"), foreground="#15803d")
        style.configure("StatusOff.TLabel", font=("Segoe UI", 12, "bold"), foreground="#6b7280")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))

        shell = ttk.Frame(self.root)
        shell.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(shell, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        container = ttk.Frame(canvas, padding=12)
        container_id = canvas.create_window((0, 0), window=container, anchor=tk.NW)
        container.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(container_id, width=event.width),
        )

        def scroll_panel(event) -> None:
            if event.widget.winfo_class() in ("Text", "TCombobox", "TSpinbox", "TScale", "Scale"):
                return
            step = -3 if getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4 else 3
            canvas.yview_scroll(step, "units")

        self.root.bind_all("<MouseWheel>", scroll_panel, add="+")
        self.root.bind_all("<Button-4>", scroll_panel, add="+")
        self.root.bind_all("<Button-5>", scroll_panel, add="+")
        self._canvas = canvas

        header = ttk.Frame(container)
        header.pack(fill=tk.X)
        try:
            with Image.open(asset_path("gaspar.png")) as image:
                preview = image.convert("RGBA")
                preview.thumbnail((92, 92))
                self._logo = ImageTk.PhotoImage(preview, master=self.root)
            ttk.Label(header, image=self._logo).pack(side=tk.LEFT, padx=(0, 14))
        except Exception as exc:
            self.log_system(f"Nao foi possivel carregar o logo do Gaspar: {exc}")

        titles = ttk.Frame(header)
        titles.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(titles, text="Gaspar", style="Brand.TLabel").pack(anchor=tk.W)
        ttk.Label(titles, text="Mascote Cara Core", style="Sub.TLabel").pack(anchor=tk.W)
        ttk.Label(
            titles,
            text="Presenca ativa, protetor de tela dinamico e bem-estar no trabalho.",
            style="Hint.TLabel",
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 0))

        status = ttk.LabelFrame(container, text="Status", padding=10)
        status.pack(fill=tk.X, pady=(10, 8))
        for column in (1, 3):
            status.columnconfigure(column, weight=1)

        ttk.Label(status, text="Simulacao", style="Hint.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(status, text="Proxima acao", style="Hint.TLabel").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        ttk.Label(status, text="Ciclos", style="Hint.TLabel").grid(row=0, column=4, sticky=tk.W, padx=(20, 0))

        self.sim_var = tk.StringVar(value="Parada")
        self.next_var = tk.StringVar(value="-")
        self.cycles_var = tk.StringVar(value="0")
        self.sim_label = ttk.Label(status, textvariable=self.sim_var, style="StatusOff.TLabel")
        self.sim_label.grid(row=1, column=0, sticky=tk.W)
        ttk.Label(status, textvariable=self.next_var, style="Value.TLabel").grid(row=1, column=2, sticky=tk.W, padx=(20, 0))
        ttk.Label(status, textvariable=self.cycles_var, style="Value.TLabel").grid(row=1, column=4, sticky=tk.W, padx=(20, 0))

        screen = ttk.Frame(container)
        screen.pack(fill=tk.X, pady=(0, 8))
        self.overlay_button = ttk.Button(screen, command=self.toggle_overlay)
        self.overlay_button.pack(side=tk.LEFT)
        ttk.Label(
            screen,
            text="A simulacao e a ponte de SMS continuam funcionando sem o mascote na tela.",
            style="Hint.TLabel",
            wraplength=360,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, padx=(10, 0))
        self._refresh_overlay_button()

        settings_frame = ttk.LabelFrame(container, text="Configuracao", padding=10)
        settings_frame.pack(fill=tk.X)
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(4, weight=1)

        ttk.Label(settings_frame, text="Intervalo").grid(row=0, column=0, sticky=tk.W)
        self.interval_var = tk.StringVar(value=str(self.settings.interval))
        self.interval_spin = ttk.Spinbox(
            settings_frame,
            from_=MIN_INTERVAL,
            to=MAX_INTERVAL,
            increment=10,
            width=7,
            textvariable=self.interval_var,
        )
        self.interval_spin.grid(row=0, column=1, sticky=tk.W, padx=(8, 4))
        ttk.Label(settings_frame, text="segundos", style="Hint.TLabel").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(settings_frame, text="Tecla").grid(row=0, column=3, sticky=tk.W, padx=(20, 0))
        self.key_var = tk.StringVar(value=KEY_CHOICES.get(self.settings.press_key, "Shift"))
        self.key_combo = ttk.Combobox(
            settings_frame,
            values=KEY_LABELS,
            textvariable=self.key_var,
            state="readonly",
            width=12,
        )
        self.key_combo.grid(row=0, column=4, sticky=tk.W, padx=(8, 0))

        self.var_mouse = tk.BooleanVar(value=self.settings.simulate_mouse)
        self.var_sound = tk.BooleanVar(value=self.settings.sound)
        self.var_overlay = tk.BooleanVar(value=self.settings.overlay)
        self.var_keep = tk.BooleanVar(value=self.settings.keep_teams)
        self.var_system = tk.BooleanVar(value=self.settings.system_telemetry)
        self.var_auto = tk.BooleanVar(value=self.settings.auto_start)
        self.var_startup = tk.BooleanVar(value=autostart.is_enabled())
        self.var_idle = tk.BooleanVar(value=self.settings.only_when_idle)
        self.var_fullscreen = tk.BooleanVar(value=self.settings.pause_fullscreen)

        options = ttk.Frame(settings_frame)
        options.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(10, 0))
        options.columnconfigure(1, weight=1)
        ttk.Checkbutton(options, text="Movimentar o mouse", variable=self.var_mouse, command=self._on_mouse_toggle).grid(row=0, column=0, sticky=tk.W, padx=(0, 24))
        ttk.Checkbutton(options, text="Sinal sonoro", variable=self.var_sound, command=self._on_sound_toggle).grid(row=0, column=1, sticky=tk.W)
        ttk.Checkbutton(options, text="Gaspar flutuante", variable=self.var_overlay, command=self._on_overlay_toggle).grid(row=1, column=0, sticky=tk.W, padx=(0, 24), pady=(4, 0))
        ttk.Checkbutton(options, text="Manter Teams/Slack ativo", variable=self.var_keep, command=self._on_keep_toggle).grid(row=1, column=1, sticky=tk.W, pady=(4, 0))
        ttk.Checkbutton(options, text="Registrar uso de CPU e memoria (local)", variable=self.var_system, command=self._on_system_toggle).grid(row=2, column=0, sticky=tk.W, padx=(0, 24), pady=(4, 0))
        ttk.Checkbutton(options, text="Iniciar simulacao ao abrir", variable=self.var_auto, command=self._on_auto_toggle).grid(row=2, column=1, sticky=tk.W, pady=(4, 0))
        ttk.Checkbutton(options, text="Agir somente quando eu estiver ausente", variable=self.var_idle, command=self._on_idle_toggle).grid(row=3, column=0, sticky=tk.W, padx=(0, 24), pady=(4, 0))
        ttk.Checkbutton(options, text="Pausar em tela cheia", variable=self.var_fullscreen, command=self._on_fullscreen_toggle).grid(row=3, column=1, sticky=tk.W, pady=(4, 0))
        ttk.Checkbutton(options, text="Iniciar com o sistema", variable=self.var_startup, command=self._on_startup_toggle).grid(row=4, column=0, sticky=tk.W, pady=(4, 0))

        opacity_row = ttk.Frame(settings_frame)
        opacity_row.grid(row=2, column=0, columnspan=5, sticky=tk.W, pady=(12, 0))
        ttk.Label(opacity_row, text="Opacidade do Gaspar").pack(side=tk.LEFT)
        self.opacity_var = tk.DoubleVar(value=self.settings.opacity)
        self.opacity_scale = ttk.Scale(
            opacity_row,
            from_=50,
            to=100,
            orient=tk.HORIZONTAL,
            length=200,
            variable=self.opacity_var,
            command=self._on_opacity_change,
        )
        self.opacity_scale.pack(side=tk.LEFT, padx=(10, 8))
        self.opacity_label = ttk.Label(
            opacity_row,
            text=f"{self.settings.opacity}%",
            style="Hint.TLabel",
        )
        self.opacity_label.pack(side=tk.LEFT)

        self.update_anchor = settings_frame
        self.update_frame = ttk.LabelFrame(container, text="Atualizacao", padding=10)
        self.update_text_var = tk.StringVar()
        ttk.Label(
            self.update_frame,
            textvariable=self.update_text_var,
            wraplength=470,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        self.update_status_var = tk.StringVar()
        ttk.Label(
            self.update_frame,
            textvariable=self.update_status_var,
            style="Hint.TLabel",
            wraplength=470,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        update_buttons = ttk.Frame(self.update_frame)
        update_buttons.pack(anchor=tk.W, pady=(8, 0))
        self.update_now_button = ttk.Button(
            update_buttons,
            text="Atualizar agora",
            style="Accent.TButton",
            command=self._on_update_now,
        )
        self.update_now_button.pack(side=tk.LEFT)
        self.update_later_button = ttk.Button(
            update_buttons,
            text="Depois",
            command=self._on_update_later,
        )
        self.update_later_button.pack(side=tk.LEFT, padx=(8, 0))
        self.update_skip_button = ttk.Button(
            update_buttons,
            text="Pular esta versao",
            command=self._on_update_skip,
        )
        self.update_skip_button.pack(side=tk.LEFT, padx=(8, 0))
        self.update_notes_button = ttk.Button(
            update_buttons,
            text="Ver novidades",
            command=self._on_update_notes,
        )
        self.update_notes_button.pack(side=tk.LEFT, padx=(8, 0))

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X, pady=8)
        self.action_button = ttk.Button(
            actions,
            text="Ativar",
            style="Accent.TButton",
            command=self.toggle_simulation,
        )
        self.action_button.pack(side=tk.LEFT)
        ttk.Button(actions, text="Ocultar", command=self.hide_window).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Celular / SMS", command=self.open_sms_panel).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Abrir logs", command=self.open_logs).pack(side=tk.LEFT, padx=(8, 0))

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(
            footer,
            text=f"v{__version__} - {COMPANY}",
            style="Hint.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(footer, text="Sair", command=self.quit).pack(side=tk.RIGHT)

    def _make_log_tab(self, notebook: ttk.Notebook, title: str) -> tk.Text:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(
            frame,
            height=7,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 9),
            background="#f8fafc",
            relief=tk.FLAT,
            padx=6,
            pady=6,
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=text.yview)
        return text

    # --- Ponte local de SMS -------------------------------------------------

    def open_sms_panel(self) -> None:
        if self._sms_window is not None and self._sms_window.winfo_exists():
            self._sms_window.deiconify()
            self._sms_window.lift()
            self._sms_window.focus_force()
            self._refresh_sms_ui()
            return
        window = tk.Toplevel(self.root)
        window.title("Gaspar - Celular / SMS")
        window.geometry("580x640")
        window.minsize(540, 580)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_sms_window)
        self._sms_window = window
        self._build_sms_window(window)
        self._refresh_sms_ui()

    def _close_sms_window(self) -> None:
        window, self._sms_window = self._sms_window, None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _build_sms_window(self, window: tk.Toplevel) -> None:
        outer = ttk.Frame(window, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky=tk.EW)
        header.columnconfigure(0, weight=1)
        self.sms_status_var = tk.StringVar(value="Verificando a ponte de SMS...")
        self.sms_detail_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.sms_status_var, style="Value.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.sms_enabled_var = tk.BooleanVar(value=bool(self.sms_config and self.sms_config.enabled))
        ttk.Checkbutton(
            header,
            text="Ponte ativa",
            variable=self.sms_enabled_var,
            command=self._on_sms_enabled,
        ).grid(row=0, column=1, sticky=tk.E)
        ttk.Label(
            header,
            textvariable=self.sms_detail_var,
            style="Hint.TLabel",
            wraplength=520,
            justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(actions, text="Procurar celular", command=self._on_find_phone).pack(side=tk.LEFT)
        ttk.Button(actions, text="Parear celular", command=self._on_show_qr).pack(side=tk.LEFT, padx=(8, 0))

        test = ttk.LabelFrame(outer, text="Envio de teste", padding=8)
        test.grid(row=2, column=0, sticky=tk.EW, pady=(10, 0))
        test.columnconfigure(1, weight=1)
        ttk.Label(test, text="Celular").grid(row=0, column=0, sticky=tk.W)
        self.sms_number_var = tk.StringVar(value="")
        ttk.Entry(test, textvariable=self.sms_number_var, width=22).grid(row=0, column=1, sticky=tk.W, padx=(8, 8))
        ttk.Button(test, text="Enviar teste", command=self._on_test_send).grid(row=0, column=2, sticky=tk.E)
        ttk.Label(test, text="Mensagem").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.sms_message_var = tk.StringVar(value="Teste do Gaspar: conexao com o celular funcionando.")
        ttk.Entry(test, textvariable=self.sms_message_var).grid(
            row=1, column=1, columnspan=2, sticky=tk.EW, padx=(8, 0), pady=(6, 0)
        )

        api = ttk.LabelFrame(outer, text="Integracao com o PDV", padding=8)
        api.grid(row=3, column=0, sticky=tk.EW, pady=(10, 0))
        api.columnconfigure(0, weight=1)
        self.sms_api_var = tk.StringVar(value="Ponte desligada")
        ttk.Label(
            api,
            textvariable=self.sms_api_var,
            style="Hint.TLabel",
            wraplength=520,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(api, text="Token", style="Hint.TLabel").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        token_row = ttk.Frame(api)
        token_row.grid(row=2, column=0, sticky=tk.EW, pady=(2, 0))
        token_row.columnconfigure(0, weight=1)
        self.sms_token_var = tk.StringVar(value="")
        ttk.Entry(token_row, textvariable=self.sms_token_var, state="readonly").grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(token_row, text="Copiar", command=self._on_copy_token).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(token_row, text="Gerar novo", command=self._on_rotate_token).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(
            api,
            text="Somente este computador pode pedir SMS, e cada pedido leva uma assinatura.",
            style="Hint.TLabel",
            wraplength=520,
            justify=tk.LEFT,
        ).grid(row=3, column=0, sticky=tk.W, pady=(6, 0))

        recent = ttk.LabelFrame(outer, text="Ultimos envios  |  ok entregue  + aceito pelo celular  ! falha", padding=8)
        recent.grid(row=4, column=0, sticky=tk.NSEW, pady=(10, 0))
        recent.columnconfigure(0, weight=1)
        recent.rowconfigure(0, weight=1)
        self.sms_text = tk.Text(
            recent,
            height=5,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 9),
            background="#f8fafc",
            relief=tk.FLAT,
            padx=6,
            pady=6,
        )
        self.sms_text.grid(row=0, column=0, sticky=tk.NSEW)

        footer = ttk.Frame(outer)
        footer.grid(row=5, column=0, sticky=tk.EW, pady=(10, 0))
        ttk.Label(
            footer,
            text="O conteudo vai cifrado de ponta a ponta; a auditoria guarda so metadados.",
            style="Hint.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(footer, text="Apagar historico", command=self._on_sms_erase).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Fechar", command=self._close_sms_window).pack(side=tk.RIGHT, padx=(0, 8))

        if not SMS_AVAILABLE:
            self.sms_status_var.set("Ponte de SMS indisponivel")
            self.sms_detail_var.set(f"Dependencia ausente: {SMS_IMPORT_ERROR}")

    def _init_sms(self) -> None:
        if not SMS_AVAILABLE:
            self.log_system(f"Ponte de SMS indisponivel: {SMS_IMPORT_ERROR}")
            return
        try:
            base = data_dir()
            self.sms_config = load_sms_config()
            self.sms_audit = AuditLog(base / "sms_audit.jsonl", self.sms_config.audit_retention_days)
            self.sms_store = SmsStore(base / "sms_state.json", self.sms_audit)
            self.sms_bridge = SmsBridge(self.sms_config, self.sms_store, on_log=self._on_sms_log)
            if self.sms_config.enabled:
                self._start_sms_services()
        except Exception as exc:
            self.log_system(f"Ponte de SMS indisponivel: {exc}")
            return
        self._sms_poll_job = self.root.after(2500, self._sms_tick)

    def _start_sms_services(self) -> None:
        if self.sms_bridge is None or self.sms_config is None:
            return
        self.sms_bridge.start()
        if self.sms_server is None:
            server = None
            try:
                server = SmsHttpServer(
                    self.sms_bridge,
                    self.sms_config,
                    on_diagnostic=self._on_sms_diagnostic,
                    on_log=self._on_sms_log,
                )
                server.start()
            except OSError as exc:
                if server is not None:
                    try:
                        server.stop()
                    except Exception:
                        pass
                self.sms_server = None
                self.log_system(f"Nao foi possivel abrir a porta {self.sms_config.http_port}: {exc}")
            else:
                self.sms_server = server
                self.sms_bridge.base_url = f"http://{lan_ip() or '127.0.0.1'}:{server.port}"
                self.log_event(f"Servidor local de SMS ativo na porta {server.port}.")
        self._update_sms_api()

    def _stop_sms_services(self) -> None:
        server, self.sms_server = self.sms_server, None
        if server is not None:
            try:
                server.stop()
            except Exception:
                pass
        if self.sms_bridge is not None:
            self.sms_bridge.base_url = ""
            try:
                self.sms_bridge.stop()
            except Exception:
                pass
        self._update_sms_api()

    def _sms_api_url(self) -> str:
        if self.sms_server is not None:
            port = self.sms_server.port
        elif self.sms_config is not None:
            port = self.sms_config.http_port
        else:
            port = 0
        return f"http://127.0.0.1:{port}"

    def _update_sms_api(self) -> None:
        if not hasattr(self, "sms_api_var"):
            return
        if self.sms_config is None:
            self.sms_api_var.set("Ponte desligada")
            self.sms_token_var.set("")
            return
        self.sms_token_var.set(self.sms_config.api_token)
        if self.sms_server is None or not self.sms_config.enabled:
            self.sms_api_var.set("Servidor local desligado")
            return
        self.sms_api_var.set(f"Endereco para o PDV (somente este computador): {self._sms_api_url()}/api/sms")

    def _on_sms_enabled(self) -> None:
        if self.sms_config is None:
            return
        enabled = bool(self.sms_enabled_var.get())
        self.sms_config.enabled = enabled
        self.sms_config.save()
        if enabled:
            self._start_sms_services()
            self.log_event("Ponte de SMS ligada.")
        else:
            self._stop_sms_services()
            self.log_event("Ponte de SMS desligada.")
        self._refresh_sms_ui()

    def _on_sms_log(self, message: str) -> None:
        self.log_event(f"SMS: {message}")

    def _on_sms_diagnostic(self, body: dict) -> None:
        self.ui(self._after_sms_diagnostic, bool(body.get("sms_ok")), bool(body.get("battery_ok")))

    def _after_sms_diagnostic(self, sms_ok: bool, battery_ok: bool) -> None:
        self._close_qr_window()
        message = "SMS ok" if sms_ok else "SMS negado"
        battery = "bateria ok" if battery_ok else "bateria otimizada"
        self.log_event(f"Celular pareado: {message}; {battery}.")
        self._refresh_sms_ui()

    def _on_find_phone(self) -> None:
        if self.sms_bridge is None or self.sms_config is None:
            messagebox.showinfo("Celular", "A ponte de SMS nao esta disponivel.", parent=self.root)
            return
        if not self.sms_config.enabled:
            messagebox.showinfo("Celular", "Ligue a ponte de SMS para procurar o celular.", parent=self.root)
            return
        self.sms_status_var.set("Procurando celular na rede...")
        threading.Thread(target=self._find_phone_worker, daemon=True).start()

    def _find_phone_worker(self) -> None:
        try:
            result = self.sms_bridge.refresh_phone()
        except Exception as exc:
            result = {"found": False, "error": str(exc)}
        self.ui(self._after_find_phone, result)

    def _after_find_phone(self, result: dict) -> None:
        if result.get("found"):
            self.sms_status_var.set(f"Celular encontrado em {result.get('host')}.")
        else:
            self.sms_status_var.set("Celular nao encontrado. Confira o app e a rede Wi-Fi.")
        self._refresh_sms_ui()

    def _on_show_qr(self) -> None:
        if self.sms_config is None or self.sms_server is None:
            messagebox.showinfo("Pareamento", "Ligue a ponte de SMS antes de parear o celular.", parent=self.root)
            return
        if self._sms_qr_window is not None and self._sms_qr_window.winfo_exists():
            self._sms_qr_window.deiconify()
            self._sms_qr_window.lift()
            self._sms_qr_window.focus_force()
            self._refresh_qr_window()
            return
        window = tk.Toplevel(self.root)
        window.title("Parear celular")
        window.transient(self.root)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self._close_qr_window)
        body = ttk.Frame(window, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            body,
            text=(
                "1. No celular, abra o aplicativo.\n"
                "2. Toque no botao de leitura de QR.\n"
                "3. Aponte para o codigo abaixo.\n"
                "O celular cria a propria chave e o conteudo passa a ir cifrado."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        self._sms_qr_image_label = ttk.Label(body, text="Gerando QR...")
        self._sms_qr_image_label.pack(pady=10)
        ttk.Label(body, text="O codigo vale por 15 minutos.", style="Hint.TLabel").pack(anchor=tk.W)
        row = ttk.Frame(body)
        row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(row, text="Gerar novo QR", command=self._refresh_qr_window).pack(side=tk.LEFT)
        ttk.Button(row, text="Fechar", command=self._close_qr_window).pack(side=tk.RIGHT)
        self._sms_qr_window = window
        self._refresh_qr_window()
        window.geometry("+%d+%d" % (self.root.winfo_rootx() + 120, self.root.winfo_rooty() + 80))

    def _refresh_qr_window(self) -> None:
        if self.sms_config is None:
            return
        window = self._sms_qr_window
        if window is None or not window.winfo_exists():
            return
        try:
            payload = self.sms_config.setup_payload(lan_ip())
            self.sms_config.save()
            image = make_qr(payload, box_size=5)
            photo = ImageTk.PhotoImage(image, master=window)
            self._sms_qr_photo = photo
            if self._sms_qr_image_label is not None:
                self._sms_qr_image_label.configure(image=photo, text="")
            self.log_event("QR de pareamento exibido.")
        except Exception as exc:
            if self._sms_qr_image_label is not None:
                self._sms_qr_image_label.configure(image="", text=f"Nao foi possivel gerar o QR:\n{exc}")

    def _close_qr_window(self) -> None:
        window, self._sms_qr_window = self._sms_qr_window, None
        self._sms_qr_image_label = None
        self._sms_qr_photo = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _on_test_send(self) -> None:
        if self.sms_bridge is None or self.sms_config is None:
            messagebox.showinfo("Envio de teste", "A ponte de SMS nao esta disponivel.", parent=self.root)
            return
        if not self.sms_config.enabled:
            messagebox.showinfo("Envio de teste", "Ligue a ponte de SMS primeiro.", parent=self.root)
            return
        try:
            job = self.sms_bridge.enqueue(self.sms_number_var.get(), self.sms_message_var.get(), manual=True)
        except (InvalidMessage, RateLimited, QueueFull) as exc:
            messagebox.showwarning("Envio de teste", str(exc), parent=self.root)
            return
        except Exception as exc:
            messagebox.showerror("Envio de teste", str(exc), parent=self.root)
            return
        self.log_event(f"Teste de SMS enfileirado ({job.id[:8]}).")
        self._refresh_sms_ui()

    def _on_sms_erase(self) -> None:
        if self.sms_bridge is None:
            return
        confirmar = messagebox.askyesno(
            "Apagar historico",
            "Apagar os envios e a trilha de auditoria de SMS deste computador?\n\n"
            "Um pedido que ja estava saindo ainda pode ser concluido pelo celular. "
            "Esta acao nao pode ser desfeita.",
            parent=self.root,
        )
        if not confirmar:
            return
        self.sms_bridge.erase_history()
        self._sms_signature = None
        self._refresh_sms_ui()

    def _on_copy_token(self) -> None:
        token = self.sms_config.api_token if self.sms_config is not None else ""
        if not token:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(token)
            self.log_event("Token da API copiado para a area de transferencia.")
        except tk.TclError as exc:
            messagebox.showerror("Token", f"Nao foi possivel copiar:\n{exc}", parent=self.root)

    def _on_rotate_token(self) -> None:
        if self.sms_config is None:
            return
        self.sms_config.rotate_api_token()
        self.sms_config.save()
        self._update_sms_api()
        self.log_event("Novo token da API gerado. Atualize o cadastro do PDV.")

    def _refresh_sms_ui(self) -> None:
        try:
            alive = self._sms_window is not None and bool(self._sms_window.winfo_exists())
        except tk.TclError:
            alive = False
        if not alive or self.sms_config is None or self.sms_bridge is None:
            return
        stats = self.sms_bridge.stats()
        phone = stats.get("phone", {})
        counts = stats.get("counts", {})
        if not self.sms_config.enabled:
            status = "Ponte de SMS desligada"
        elif phone.get("online"):
            status = f"Celular conectado - {phone.get('host') or 'rede local'}"
        elif phone.get("host"):
            status = f"Celular conhecido ({phone.get('host')}), sem resposta recente"
        else:
            status = "Celular ainda nao pareado"
        self.sms_status_var.set(status)
        details = [
            f"fila {counts.get('fila', 0)}",
            f"enviados {counts.get('enviado', 0)}",
            f"entregues {counts.get('entregue', 0)}",
            f"falhas {counts.get('falhou', 0)}",
        ]
        if self.sms_config.last_diagnostic_at:
            when = datetime.fromtimestamp(self.sms_config.last_diagnostic_at).strftime("%d/%m %H:%M")
            sms = "SMS ok" if self.sms_config.last_diagnostic_sms_ok else "SMS negado"
            battery = "bateria ok" if self.sms_config.last_diagnostic_battery_ok else "bateria otimizada"
            details.insert(0, f"pareado {when} ({sms}, {battery})")
        crypto = stats.get("e2e", {})
        if crypto.get("required"):
            if crypto.get("phone_key"):
                details.append(f"cifrado ponta a ponta ({str(crypto.get('fingerprint', ''))[:8]})")
            else:
                details.append("sem chave do celular")
        self.sms_detail_var.set(" - ".join(details))
        self._update_sms_api()
        recent = self.sms_bridge.store.recent(8)
        signature = tuple((job.id, job.status, job.updated_at) for job in recent)
        if signature != self._sms_signature:
            self._sms_signature = signature
            lines = []
            for job in recent:
                when = datetime.fromtimestamp(job.updated_at).strftime("%d/%m %H:%M")
                if job.status == "entregue":
                    mark = "ok"
                elif job.status == "falhou":
                    mark = "!"
                elif job.confirmed:
                    mark = "+"
                else:
                    mark = " "
                destino = job.recipient_tag[:8] if job.recipient_tag else "--------"
                rotulo = job.template or job.actor or ""
                lines.append(f"{when} {job.status:<9}{mark} #{destino:<8} {rotulo}")
            self._set_sms_text(lines)

    def _set_sms_text(self, lines: list[str]) -> None:
        try:
            self.sms_text.configure(state=tk.NORMAL)
            self.sms_text.delete("1.0", tk.END)
            self.sms_text.insert(tk.END, "\n".join(lines) if lines else "Nenhum envio registrado.")
            self.sms_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _sms_tick(self) -> None:
        if self.closing:
            return
        try:
            self._refresh_sms_ui()
        except Exception:
            pass
        self._sms_poll_job = self.root.after(2500, self._sms_tick)

    def _set_window_icon(self) -> None:
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

    def _wire_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.interval_spin.bind("<FocusOut>", lambda _event: self._commit_interval())
        self.interval_spin.bind("<Return>", lambda _event: self._commit_interval(focus=True))
        self.key_combo.bind("<<ComboboxSelected>>", self._on_key_change)

    def _persist(self) -> None:
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.log_system(f"Nao foi possivel salvar as preferencias: {exc}")

    def _commit_interval(self, focus: bool = False) -> bool:
        raw = self.interval_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            messagebox.showwarning(
                "Intervalo invalido",
                f"Informe um numero entre {MIN_INTERVAL} e {MAX_INTERVAL} segundos.",
                parent=self.root,
            )
            self.interval_var.set(str(self.settings.interval))
            return False

        clamped = max(MIN_INTERVAL, min(MAX_INTERVAL, value))
        if clamped != value:
            self.interval_var.set(str(clamped))
        self.settings.interval = clamped
        self._persist()
        if focus:
            self.root.focus_set()
        return True

    def _on_key_change(self, _event=None) -> None:
        label = self.key_var.get()
        self.settings.press_key = LABEL_TO_KEY.get(label, "shift")
        self._persist()
        self.log_event(f"Tecla de atividade alterada para {label}.")

    def _on_mouse_toggle(self) -> None:
        self.settings.simulate_mouse = bool(self.var_mouse.get())
        self._persist()
        self.log_event("Movimento do mouse " + ("ativado." if self.settings.simulate_mouse else "desativado."))

    def _on_sound_toggle(self) -> None:
        self.settings.sound = bool(self.var_sound.get())
        self._persist()
        self.log_event("Som " + ("ativado." if self.settings.sound else "desativado."))

    def _on_overlay_toggle(self) -> None:
        self.set_overlay(bool(self.var_overlay.get()))

    def _on_keep_toggle(self) -> None:
        self.settings.keep_teams = bool(self.var_keep.get())
        self._persist()
        self.log_event("Toque de atividade do Teams/Slack " + ("ativado." if self.settings.keep_teams else "desativado."))

    def _on_system_toggle(self) -> None:
        self.settings.system_telemetry = bool(self.var_system.get())
        self._persist()
        self.log_system("Registro de CPU e memoria " + ("ativado." if self.settings.system_telemetry else "desativado."))

    def _on_auto_toggle(self) -> None:
        self.settings.auto_start = bool(self.var_auto.get())
        self._persist()

    def _on_idle_toggle(self) -> None:
        self.settings.only_when_idle = bool(self.var_idle.get())
        self._persist()
        self.log_event(
            "Simulacao restrita aos periodos de ausencia "
            + ("ativada." if self.settings.only_when_idle else "desativada.")
        )

    def _on_fullscreen_toggle(self) -> None:
        self.settings.pause_fullscreen = bool(self.var_fullscreen.get())
        if self.overlay is not None:
            self.overlay.set_pause_fullscreen(self.settings.pause_fullscreen)
        self._persist()
        self.log_event(
            "Pausa em tela cheia "
            + ("ativada." if self.settings.pause_fullscreen else "desativada.")
        )

    def _on_opacity_change(self, value: str) -> None:
        try:
            percent = int(round(float(value)))
        except ValueError:
            return
        percent = max(50, min(100, percent))
        self.settings.opacity = percent
        self.opacity_label.configure(text=f"{percent}%")
        if self.overlay is not None:
            self.overlay.set_opacity(percent / 100)
        if self._opacity_job is not None:
            try:
                self.root.after_cancel(self._opacity_job)
            except tk.TclError:
                pass
        self._opacity_job = self.root.after(400, self._persist_opacity)

    def _persist_opacity(self) -> None:
        self._opacity_job = None
        self._persist()

    def _on_startup_toggle(self) -> None:
        wanted = bool(self.var_startup.get())
        error = autostart.enable() if wanted else autostart.disable()
        if error:
            self.var_startup.set(not wanted)
            messagebox.showerror("Inicializacao automatica", error, parent=self.root)
            return
        self.log_event("Inicializacao com o sistema " + ("ativada." if wanted else "desativada."))

    def set_overlay(self, enabled: bool) -> None:
        if enabled == self.settings.overlay:
            return
        self.settings.overlay = enabled
        self.var_overlay.set(enabled)
        self._apply_overlay_state()
        self._persist()
        self._refresh_overlay_button()
        self.log_event("Gaspar flutuante " + ("ativado." if enabled else "desativado."))

    def toggle_overlay(self) -> None:
        self.set_overlay(not self.settings.overlay)

    def _refresh_overlay_button(self) -> None:
        if self.settings.overlay:
            self.overlay_button.configure(text="Tirar o Gaspar da tela")
        else:
            self.overlay_button.configure(text="Trazer o Gaspar de volta")

    @property
    def overlay_visible(self) -> bool:
        return self.overlay is not None and self.overlay.is_visible

    def _apply_overlay_state(self) -> None:
        if self.settings.overlay:
            if self.overlay is None:
                try:
                    self.overlay = GasparOverlay(
                        self.root,
                        log=self.log_system,
                        opacity=self.settings.opacity / 100,
                        pause_fullscreen=self.settings.pause_fullscreen,
                    )
                except Exception as exc:
                    self.settings.overlay = False
                    self.var_overlay.set(False)
                    self._refresh_overlay_button()
                    self.log_system(f"Nao foi possivel criar o Gaspar flutuante: {exc}")
                    return
            self.overlay.set_panel_visible(self._panel_visible)
            self.overlay.show()
        elif self.overlay is not None:
            self.overlay.hide()

    def toggle_simulation(self) -> None:
        if self.engine.is_running:
            self.engine.stop()
        else:
            if not self._commit_interval():
                return
            active_actions = (
                self.settings.simulate_mouse
                or self.settings.press_key != "none"
                or self.settings.keep_teams
            )
            if not active_actions:
                messagebox.showwarning(
                    "Nada para simular",
                    "Ative ao menos o movimento do mouse ou uma tecla de atividade.",
                    parent=self.root,
                )
                return
            self.engine.start()
        self._set_status()

    def _set_status(self) -> None:
        running = self.engine.is_running
        self.sim_var.set("Ativa" if running else "Parada")
        self.sim_label.configure(style="StatusOn.TLabel" if running else "StatusOff.TLabel")
        self.action_button.configure(text="Desativar" if running else "Ativar")
        remaining = self.engine.seconds_remaining()
        self.next_var.set(f"{remaining}s" if remaining is not None else "-")
        self.cycles_var.set(str(self.engine.cycles))

    def _tick(self) -> None:
        if self.closing:
            return
        visible = self.root.state() == "normal" and bool(self.root.winfo_viewable())
        if visible != self._panel_visible:
            self._panel_visible = visible
            if self.overlay is not None:
                self.overlay.set_panel_visible(visible)
        self._set_status()
        self.root.after(500, self._tick)

    def _init_updates(self) -> None:
        if self.closing:
            return
        resultado = updates.ler_resultado_instalacao()
        if resultado is not None:
            pendente = str(updates.carregar_estado().get("pending_version") or "")
            updates.salvar_estado(pending_version="")
            if resultado.get("code") == 0:
                self.log_event(
                    f"Atualizacao para {pendente} concluida." if pendente else "Atualizacao concluida."
                )
            else:
                self.log_system(
                    f"A instalacao{f' de {pendente}' if pendente else ''} nao concluiu "
                    f"(codigo {resultado.get('code')}). O canal sera consultado de novo."
                )
        chave = updates.chave_publica()
        if chave is None:
            self.log_system("Canal de atualizacao desativado: chave publica ausente em assets/.")
            return
        self._update_vigia = updates.Vigia(self, chave)
        self._update_vigia.iniciar()

    def mostrar_atualizacao(self, info: updates.Disponivel) -> None:
        if self.closing:
            return
        pulada = str(updates.carregar_estado().get("skipped_version") or "")
        if pulada and pulada == info.versao and not info.mandatory:
            return
        self.update_info = info
        adiada = str(updates.carregar_estado().get("deferred_version") or "")
        if adiada == info.versao and not info.mandatory:
            if self.tray_icon is not None:
                try:
                    self.tray_icon.update_menu()
                except Exception:
                    pass
            return
        if info.mandatory:
            self.update_text_var.set(
                f"Versao {info.versao} necessaria para continuar recebendo correcoes. "
                "Voce escolhe quando instalar; a simulacao segue funcionando."
            )
        else:
            self.update_text_var.set(
                f"Versao {info.versao} disponivel. Voce escolhe quando instalar; "
                "a simulacao segue funcionando."
            )
        self.update_status_var.set("")
        if sys.platform != "win32":
            self.update_now_button.configure(text="Abrir download")
        self.update_skip_button.configure(state=tk.DISABLED if info.mandatory else tk.NORMAL)
        self.update_notes_button.configure(state=tk.NORMAL if info.notes_url else tk.DISABLED)
        self._pack_update_banner()
        self.log_event(
            f"Atualizacao {info.versao} disponivel "
            f"({'obrigatoria' if info.mandatory else 'opcional'})."
        )
        self._notificar_atualizacao(info)

    def _pack_update_banner(self) -> None:
        try:
            if self.update_frame.winfo_manager() != "pack":
                self.update_frame.pack(fill=tk.X, pady=(0, 8), before=self.update_anchor)
        except tk.TclError:
            pass

    def _notificar_atualizacao(self, info: updates.Disponivel) -> None:
        if str(updates.carregar_estado().get("notified_version") or "") == info.versao:
            return
        if self.tray_icon is not None:
            try:
                self.tray_icon.notify(f"Versao {info.versao} pronta para instalar.", "Gaspar")
            except Exception:
                pass
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass
            updates.salvar_estado(notified_version=info.versao)

    def show_update(self) -> None:
        if self.update_info is None:
            return
        self.show_panel()
        self._pack_update_banner()

    def _on_update_notes(self) -> None:
        info = self.update_info
        if info is None:
            return
        if updates.abrir_pagina(info.notes_url):
            self.log_event(f"Pagina de novidades da versao {info.versao} aberta.")

    def _on_update_later(self) -> None:
        info = self.update_info
        if info is not None:
            updates.salvar_estado(deferred_version=info.versao)
        try:
            self.update_frame.pack_forget()
        except tk.TclError:
            pass

    def _on_update_skip(self) -> None:
        info = self.update_info
        if info is None or info.mandatory:
            return
        updates.salvar_estado(skipped_version=info.versao, deferred_version="")
        self.update_info = None
        try:
            self.update_frame.pack_forget()
        except tk.TclError:
            pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass
        self.log_event(f"Atualizacao {info.versao} pulada.")

    def _on_update_now(self) -> None:
        info = self.update_info
        if info is None:
            return
        if sys.platform != "win32":
            if updates.abrir_pagina(info.notes_url or info.url):
                self.log_event(f"Pagina de download da versao {info.versao} aberta.")
            else:
                self.update_status_var.set(f"Baixe a versao {info.versao} em: {info.url}")
            return
        if self._update_worker is not None and self._update_worker.is_alive():
            return
        self._update_busy(True)
        self.update_status_var.set("Baixando e conferindo a atualizacao...")
        self._update_worker = threading.Thread(
            target=self._baixar_atualizacao,
            args=(info,),
            name="gaspar-update-download",
            daemon=True,
        )
        self._update_worker.start()

    def _baixar_atualizacao(self, info: updates.Disponivel) -> None:
        try:
            instalador = updates.baixar_instalador(info.url, info.sha256, data_dir() / "updates")
        except updates.FalhaAtualizacao as exc:
            self.ui(self._update_falhou, info.versao, str(exc))
            return
        except Exception as exc:
            self.ui(self._update_falhou, info.versao, f"erro inesperado ({exc.__class__.__name__})")
            return
        self.ui(self._aplicar_atualizacao, instalador, info)

    def _aplicar_atualizacao(self, instalador: Path, info: updates.Disponivel) -> None:
        if self.closing:
            return
        if self.update_info is None or self.update_info.versao != info.versao:
            self._update_busy(False)
            return
        updates.salvar_estado(pending_version=info.versao, deferred_version="")
        self.update_status_var.set("Instalando... o Gaspar vai reabrir sozinho.")
        app_exe = Path(sys.executable) if getattr(sys, "frozen", False) else None
        try:
            updates.aplicar_windows(instalador, app_exe, info.versao)
        except Exception as exc:
            self._update_falhou(info.versao, f"nao foi possivel iniciar o instalador ({exc.__class__.__name__})")
            return
        self.log_event(f"Instalacao da versao {info.versao} iniciada; o Gaspar vai reabrir.")
        self.quit()

    def _update_falhou(self, versao: str, motivo: str) -> None:
        if self.closing:
            return
        self._update_busy(False)
        updates.salvar_estado(deferred_version="")
        self.update_status_var.set(f"Nao foi possivel atualizar agora: {motivo}. Tente novamente.")
        self.log_system(f"Atualizacao {versao}: {motivo}.")

    def _update_busy(self, ocupado: bool) -> None:
        estado = tk.DISABLED if ocupado else tk.NORMAL
        self.update_now_button.configure(state=estado)
        self.update_later_button.configure(state=estado)
        if self.update_info is not None and self.update_info.mandatory:
            self.update_skip_button.configure(state=tk.DISABLED)
        else:
            self.update_skip_button.configure(state=estado)

    def _maybe_auto_start(self) -> None:
        if self.closing or self.engine.is_running or not self.settings.auto_start:
            return
        self.engine.start()
        self._set_status()

    def _init_tray(self) -> None:
        if self.closing:
            return
        self.tray_icon, error = create_tray(self)
        if error:
            self.log_system(f"Bandeja do sistema indisponivel: {error}.")
        if self.start_minimized:
            if self.tray_icon is not None:
                self.root.withdraw()
            else:
                self.show_panel()

    def ui(self, callback, *args) -> None:
        if self.closing:
            return
        try:
            self.root.after(0, lambda: None if self.closing else callback(*args))
        except tk.TclError:
            pass

    def log_event(self, message: str) -> None:
        line = self.log.write("EVENTO", message)
        self._remember(self._events_backlog, line)
        if self.events_text is not None:
            self.ui(self._append, self.events_text, line)

    def log_system(self, message: str) -> None:
        line = self.log.write("SISTEMA", message)
        self._remember(self._system_backlog, line)
        if self.system_text is not None:
            self.ui(self._append, self.system_text, line)

    @staticmethod
    def _remember(backlog: list[str], line: str) -> None:
        backlog.append(line)
        if len(backlog) > 500:
            del backlog[:100]

    @staticmethod
    def _append(widget: tk.Text, line: str) -> None:
        try:
            widget.configure(state=tk.NORMAL)
            widget.insert(tk.END, line + "\n")
            line_count = int(widget.index("end-1c").split(".")[0])
            if line_count > 2000:
                widget.delete("1.0", "500.0")
            widget.see(tk.END)
            widget.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _bell(self) -> None:
        if self.closing:
            return
        try:
            self.root.after(0, self.root.bell)
        except tk.TclError:
            pass

    def hide_window(self) -> None:
        if self.tray_icon is not None:
            self.root.withdraw()
            self.log_event("Painel oculto na bandeja do sistema.")
        else:
            self.root.iconify()
            self.log_event("Painel minimizado.")
        self._panel_visible = False
        if self.overlay is not None:
            self.overlay.set_panel_visible(False)

    def show_panel(self) -> None:
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass
        self._panel_visible = True
        if self.overlay is not None:
            self.overlay.set_panel_visible(True)

    def open_logs(self) -> None:
        if self._logs_window is not None and self._logs_window.winfo_exists():
            self._logs_window.deiconify()
            self._logs_window.lift()
            self._logs_window.focus_force()
            return
        window = tk.Toplevel(self.root)
        window.title("Gaspar - Registros")
        window.geometry("640x420")
        window.minsize(520, 320)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_logs_window)
        self._logs_window = window

        outer = ttk.Frame(window, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.events_text = self._make_log_tab(notebook, "Eventos")
        self.system_text = self._make_log_tab(notebook, "Sistema")
        for line in self._events_backlog:
            self._append(self.events_text, line)
        for line in self._system_backlog:
            self._append(self.system_text, line)

        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(actions, text="Abrir pasta de dados", command=self._open_data_folder).pack(side=tk.LEFT)
        ttk.Button(actions, text="Fechar", command=self._close_logs_window).pack(side=tk.RIGHT)

    def _close_logs_window(self) -> None:
        window, self._logs_window = self._logs_window, None
        self.events_text = None
        self.system_text = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _open_data_folder(self) -> None:
        target = data_dir()
        try:
            if sys.platform == "win32":
                os.startfile(target)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            messagebox.showerror("Abrir logs", f"Nao foi possivel abrir a pasta:\n{exc}", parent=self.root)

    def open_blackbox(self) -> None:
        try:
            if getattr(sys, "frozen", False):
                name = "gaspar_blackbox.exe" if sys.platform == "win32" else "gaspar_blackbox"
                base = Path(sys.executable).parent
                candidates = (
                    base / name,
                    base / "gaspar_blackbox" / name,
                    base / "blackbox" / name,
                    base.parent / "gaspar_blackbox" / name,
                )
                candidate = next((path for path in candidates if path.exists()), None)
                if candidate is None:
                    messagebox.showinfo(
                        "Gaspar BlackBox",
                        "O executavel do BlackBox nao foi encontrado nesta instalacao.",
                        parent=self.root,
                    )
                    return
                subprocess.Popen([str(candidate)], cwd=str(candidate.parent))
            else:
                subprocess.Popen(
                    [sys.executable, "-m", "gaspar.blackbox"],
                    cwd=str(project_root()),
                )
        except Exception as exc:
            messagebox.showerror("Gaspar BlackBox", f"Nao foi possivel abrir o BlackBox:\n{exc}", parent=self.root)

    def quit(self) -> None:
        if self.closing:
            return
        self.closing = True
        if self._sms_poll_job is not None:
            try:
                self.root.after_cancel(self._sms_poll_job)
            except Exception:
                pass
            self._sms_poll_job = None
        self._close_qr_window()
        self._close_sms_window()
        self._close_logs_window()
        self._stop_sms_services()
        if self._update_vigia is not None:
            self._update_vigia.parar()
        try:
            self.engine.stop()
        except Exception:
            pass
        if self.overlay is not None:
            try:
                self.overlay.destroy()
            except Exception:
                pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self._persist()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    start_minimized = "--minimized" in args
    if "--version" in args:
        print(f"Gaspar {__version__}")
        return 0

    enable_dpi_awareness()
    root = tk.Tk()
    if start_minimized:
        root.withdraw()
    GasparApp(root, start_minimized=start_minimized)
    root.mainloop()
    return 0
