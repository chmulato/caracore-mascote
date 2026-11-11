#!/usr/bin/env python3
"""Teste de fumaca do Gaspar: configuracao, hosts, motor e overlay real.

Uso: python tests/smoke_test.py
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["GASPAR_HOME"] = tempfile.mkdtemp(prefix="gaspar-smoke-")

from gaspar import activity  # noqa: E402
from gaspar import telemetry_hosts as hosts  # noqa: E402
from gaspar.config import Settings, load_settings, save_settings  # noqa: E402
from gaspar.paths import log_path  # noqa: E402
from gaspar.presence import PresenceEngine  # noqa: E402

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    status = "OK" if condition else "FALHA"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


def test_config() -> None:
    original = Settings(
        interval=42,
        opacity=77,
        press_key="space",
        simulate_mouse=False,
        only_when_idle=False,
        idle_seconds=45,
        pause_fullscreen=False,
    )
    save_settings(original)
    loaded = load_settings()
    check(loaded.interval == 42, "config: intervalo persistido")
    check(loaded.opacity == 77, "config: opacidade persistida")
    check(loaded.press_key == "space", "config: tecla persistida")
    check(loaded.simulate_mouse is False, "config: booleanos persistidos")
    check(loaded.only_when_idle is False, "config: modo discreto persistido")
    check(loaded.idle_seconds == 45, "config: tempo de ausencia persistido")
    check(loaded.pause_fullscreen is False, "config: pausa em tela cheia persistida")


def test_activity() -> None:
    idle = activity.idle_seconds()
    check(idle is None or idle >= 0, "atividade: leitura de inatividade")
    check(isinstance(activity.fullscreen_app_active(), bool), "atividade: deteccao de tela cheia")


def test_hosts() -> None:
    target = Path(tempfile.mkdtemp(prefix="gaspar-hosts-")) / "hosts"
    target.write_text("# hosts\n127.0.0.1 localhost\n", encoding="utf-8")
    check(hosts.apply_block(target) is None, "hosts: aplicar bloco")
    text = target.read_text(encoding="utf-8")
    check(text.count(hosts.MARKER_START) == 1, "hosts: marcador unico")
    check(text.count("0.0.0.0 ") == len(hosts.DOMAINS), "hosts: todos os dominios")
    check(hosts.apply_block(target) is None, "hosts: reaplicar e idempotente")
    check(target.read_text(encoding="utf-8").count(hosts.MARKER_START) == 1, "hosts: sem duplicata")
    check(hosts.remove_block(target) is None, "hosts: remover bloco")
    final = target.read_text(encoding="utf-8")
    check(hosts.MARKER_START not in final and "127.0.0.1 localhost" in final, "hosts: conteudo original preservado")


def test_engine_noop() -> None:
    settings = Settings(
        simulate_mouse=False,
        press_key="none",
        keep_teams=False,
        system_telemetry=False,
        sound=False,
        only_when_idle=False,
        pause_fullscreen=False,
    )
    events: list[str] = []
    engine = PresenceEngine(lambda: settings, events.append, lambda _message: None)
    engine._execute_cycle(None)
    check(any("Nenhuma acao" in event for event in events), "motor: ciclo sem acoes e registrado")


def _win32_overlay_checks(app) -> None:
    overlay = app.overlay
    overlay.win.update_idletasks()
    if overlay._cursor_job is not None:
        overlay.win.after_cancel(overlay._cursor_job)
        overlay._cursor_job = None
    overlay._set_dimmed(False)
    user32 = ctypes.windll.user32
    hwnd = user32.GetAncestor(wintypes.HWND(overlay.win.winfo_id()), 2) or overlay.win.winfo_id()

    chroma = str(overlay.win.attributes("-transparentcolor")).lower()
    check(chroma == "#ff00ff", "overlay: chroma key #ff00ff")
    check(
        overlay._panel_visible and not bool(int(overlay.win.attributes("-topmost"))),
        "overlay: fica atras do painel aberto",
    )
    overlay.set_panel_visible(False)
    check(bool(int(overlay.win.attributes("-topmost"))), "overlay: always-on-top com o painel fechado")

    get_long = user32.GetWindowLongPtrW
    get_long.restype = ctypes.c_ssize_t
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    style = get_long(hwnd, -20)
    check(bool(style & 0x00080000), "overlay: WS_EX_LAYERED")
    check(bool(style & 0x00000020), "overlay: WS_EX_TRANSPARENT")
    check(bool(style & 0x08000000), "overlay: WS_EX_NOACTIVATE")

    user32.GetLayeredWindowAttributes.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.COLORREF),
        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(wintypes.DWORD),
    ]

    def layered():
        key = wintypes.COLORREF()
        alpha = ctypes.c_ubyte()
        flags = wintypes.DWORD()
        ok = user32.GetLayeredWindowAttributes(
            hwnd, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(flags)
        )
        return bool(ok), key.value, alpha.value, flags.value

    ok, key_value, alpha_value, flag_bits = layered()
    check(ok and bool(flag_bits & 0x1), "overlay: LWA_COLORKEY ativo")
    check(ok and bool(flag_bits & 0x2), "overlay: LWA_ALPHA ativo")
    check(ok and key_value == 0x00FF00FF, "overlay: cor chave 0x00FF00FF")
    check(ok and abs(alpha_value - round(0.82 * 255)) <= 1, f"overlay: alpha {alpha_value}/255 (~82%)")

    overlay._set_dimmed(True)
    _, _, dim_alpha, _ = layered()
    check(abs(dim_alpha - round(0.12 * 255)) <= 1, f"overlay: clareia com o cursor perto ({dim_alpha}/255)")
    overlay._set_dimmed(False)
    _, _, restored_alpha, _ = layered()
    check(abs(restored_alpha - round(0.82 * 255)) <= 1, "overlay: opacidade restaurada ao afastar o cursor")

    point = wintypes.POINT(
        overlay.win.winfo_rootx() + 105,
        overlay.win.winfo_rooty() + 105,
    )
    under = user32.WindowFromPoint(point)
    check(under != hwnd, "overlay: clique atravessa o mascote")
    overlay.set_panel_visible(True)


def _x11_is_above(window_a, window_b) -> bool:
    """Consulta a ordem real de empilhamento no X11 (independe de -topmost)."""
    display = None
    try:
        from Xlib import display as xdisplay

        display = xdisplay.Display()
        screen_root = display.screen().root

        def top_level(window_id: int):
            window = display.create_resource_object("window", window_id)
            parent = window.query_tree().parent
            while parent and parent.id != screen_root.id:
                window = parent
                parent = window.query_tree().parent
            return window.id

        order = [child.id for child in screen_root.query_tree().children]
        return order.index(top_level(window_a.winfo_id())) > order.index(
            top_level(window_b.winfo_id())
        )
    except Exception:
        return False
    finally:
        if display is not None:
            try:
                display.close()
            except Exception:
                pass


def test_gui() -> None:
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("[SKIP] GUI sem servidor grafico")
        return

    import tkinter as tk

    from gaspar import overlay as overlay_module
    from gaspar.app import GasparApp

    save_settings(
        Settings(
            auto_start=False,
            overlay=True,
            simulate_mouse=False,
            press_key="none",
            keep_teams=False,
            system_telemetry=False,
            sound=False,
            interval=10,
            opacity=82,
            only_when_idle=False,
            pause_fullscreen=False,
        )
    )
    Path(os.environ["GASPAR_HOME"], "sms_config.json").write_text(
        json.dumps({"enabled": False}),
        encoding="utf-8",
    )
    root = tk.Tk()
    app = GasparApp(root)
    initial = (app.overlay.win.winfo_rootx(), app.overlay.win.winfo_rooty())

    def first_check() -> None:
        check(root.winfo_exists() == 1, "app: painel criado")
        check(app.overlay is not None and app.overlay_visible, "app: Gaspar flutuante visivel")
        check(app.sim_var.get() == "Parada", "app: simulacao parada (auto_start=False)")
        app.open_sms_panel()
        root.update_idletasks()
        check(app._sms_window is not None and app._sms_window.winfo_exists(), "sms: janela Celular/SMS abre")
        check(app.sms_status_var.get() == "Ponte de SMS desligada", "sms: ponte desligada no teste")
        app._close_sms_window()

        app.overlay_button.invoke()
        root.update_idletasks()
        check(not app.overlay_visible and not app.var_overlay.get(), "app: botao tira o Gaspar da tela")
        check(
            app.overlay_button.cget("text") == "Trazer o Gaspar de volta",
            "app: botao oferece trazer o Gaspar de volta",
        )
        app.overlay_button.invoke()
        root.update_idletasks()
        check(app.overlay_visible and app.var_overlay.get(), "app: botao traz o Gaspar de volta")

        if sys.platform == "win32":
            _win32_overlay_checks(app)

        overlay = app.overlay
        previous = overlay._current_index
        overlay._pause_until = 0.0
        overlay._travel_to = None
        overlay._begin_travel(time.monotonic())
        delta = (overlay._current_index - previous) % len(overlay._positions)
        check(delta in (1, 3), "overlay: trajeto entre cantos vizinhos (sem cruzar o centro)")

        real_fullscreen = overlay_module.activity.fullscreen_app_active
        if overlay._fullscreen_job is not None:
            overlay.win.after_cancel(overlay._fullscreen_job)
            overlay._fullscreen_job = None
        overlay.set_pause_fullscreen(True)
        overlay_module.activity.fullscreen_app_active = lambda: True
        overlay._watch_fullscreen()
        check(overlay._auto_hidden, "overlay: some durante tela cheia")
        overlay_module.activity.fullscreen_app_active = lambda: False
        overlay._watch_fullscreen()
        check(not overlay._auto_hidden, "overlay: volta ao sair da tela cheia")
        overlay_module.activity.fullscreen_app_active = real_fullscreen
        overlay.set_pause_fullscreen(False)

        app.hide_window()
        root.update_idletasks()
        if sys.platform == "win32":
            check(
                not app._panel_visible and bool(int(overlay.win.attributes("-topmost"))),
                "app: mascote assume o topo ao esconder o painel",
            )
        else:
            # No X11 o mascote e override-redirect e fica acima das janelas
            # gerenciadas pelo WM; o Tk 8.6 ignora -topmost.
            rival = tk.Toplevel(root)
            rival.geometry("220x160+40+40")
            rival.update()
            rival.focus_force()
            root.update_idletasks()
            acima_rival = _x11_is_above(overlay.win, rival)
            check(
                not app._panel_visible
                and not overlay._panel_visible
                and overlay._visible
                and overlay.win.winfo_ismapped() == 1
                and root.winfo_ismapped() == 0
                and acima_rival,
                "app: mascote fica visivel e acima de outra janela ao esconder o painel "
                f"(painel={app._panel_visible}, overlay_painel={overlay._panel_visible}, "
                f"visivel={overlay._visible}, mapeado={overlay.win.winfo_ismapped()}, "
                f"painel_mapeado={root.winfo_ismapped()}, acima={acima_rival})",
            )
            rival.destroy()
        app.show_panel()
        root.update_idletasks()
        if sys.platform == "win32":
            topmost = overlay.win.attributes("-topmost")
            atras = not bool(int(topmost))
            detalhe = f"topo={topmost}"
        else:
            # No X11 provamos a ordem real de empilhamento, nao -topmost.
            atras = _x11_is_above(root, overlay.win)
            detalhe = f"painel_acima={atras}"
        check(
            app._panel_visible and atras,
            "app: mascote volta para tras do painel aberto "
            f"(painel={app._panel_visible}, overlay_painel={overlay._panel_visible}, "
            f"visivel={overlay._visible}, auto={overlay._auto_hidden}, {detalhe})",
        )

    def second_check(attempt: int = 0) -> None:
        current = (app.overlay.win.winfo_rootx(), app.overlay.win.winfo_rooty())
        if current != initial:
            check(True, "overlay: flutuou para outro ponto")
        elif attempt < 20:
            root.after(250, lambda: second_check(attempt + 1))
            return
        else:
            check(False, "overlay: flutuou para outro ponto")
        app.quit()

    root.after(1200, first_check)
    root.after(5500, second_check)
    root.mainloop()

    check(log_path().exists(), "app: cycle_log.txt criado")


def main() -> int:
    print(f"GASPAR_HOME={os.environ['GASPAR_HOME']}")
    test_config()
    test_hosts()
    test_activity()
    test_engine_noop()
    test_gui()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} falha(s):")
        for failure in FAILURES:
            print(f" - {failure}")
        return 1
    print("Todos os testes passaram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
