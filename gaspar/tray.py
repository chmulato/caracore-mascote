"""Icone de bandeja opcional (requer pystray)."""

from __future__ import annotations

import threading

from PIL import Image

from .paths import asset_path


def create_tray(app):
    try:
        import pystray
    except Exception as exc:
        return None, f"pystray indisponivel ({exc})"

    try:
        with Image.open(asset_path("gaspar.png")) as image:
            icon_image = image.convert("RGBA").copy()
    except Exception:
        icon_image = Image.new("RGBA", (64, 64), (155, 212, 10, 255))

    menu = pystray.Menu(
        pystray.MenuItem("Abrir painel", lambda _icon, _item: app.ui(app.show_panel), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Simulacao ativa",
            lambda _icon, _item: app.ui(app.toggle_simulation),
            checked=lambda _item: app.engine.is_running,
        ),
        pystray.MenuItem(
            "Gaspar flutuante",
            lambda _icon, _item: app.ui(app.toggle_overlay),
            checked=lambda _item: app.overlay_visible,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Gaspar BlackBox",
            lambda _icon, _item: app.ui(app.open_blackbox),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Atualizacao disponivel",
            lambda _icon, _item: app.ui(app.show_update),
            visible=lambda _item: getattr(app, "update_info", None) is not None,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", lambda _icon, _item: app.ui(app.quit)),
    )

    try:
        icon = pystray.Icon("gaspar", icon_image, "Gaspar - Mascote Cara Core", menu)
        thread = threading.Thread(target=icon.run, name="gaspar-tray", daemon=True)
        thread.start()
        return icon, None
    except Exception as exc:
        return None, f"nao foi possivel iniciar a bandeja ({exc})"
