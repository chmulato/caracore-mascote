"""Janela flutuante do Gaspar: chroma key, translucidez, topmost e click-through."""

from __future__ import annotations

import math
import random
import sys
import time
import tkinter as tk

from PIL import Image, ImageTk

from . import activity
from .paths import asset_path

TRANSPARENT_KEY = "#ff00ff"
SIDE = 220  # mesmo tamanho dos quadros de gaspar_flutuando.gif
TICK_MS = 33
FRAME_MS = 100
CURSOR_PADDING = 28
CURSOR_ALPHA = 0.12
FULLSCREEN_POLL_MS = 1500
CURSOR_POLL_MS = 120


class GasparOverlay:
    def __init__(
        self,
        root: tk.Misc,
        log=None,
        opacity: float = 0.82,
        pause_fullscreen: bool = True,
    ):
        self.root = root
        self.log = log or (lambda _message: None)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-toolwindow", True)
        except tk.TclError:
            pass

        self.transparent = sys.platform == "win32"
        if self.transparent:
            try:
                self.win.attributes("-transparentcolor", TRANSPARENT_KEY)
            except tk.TclError:
                self.transparent = False

        # No Linux o fundo do canvas nao e chaveado; o recorte X11 esconde o retangulo.
        background = TRANSPARENT_KEY if self.transparent else "#0a0f0a"
        self.canvas = tk.Canvas(
            self.win,
            width=SIDE,
            height=SIDE,
            bg=background,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self._frames: list[ImageTk.PhotoImage] = []
        self._raw_frames: list[Image.Image] = []
        self._shape_bytes: list[bytes] = []
        self._image_item = None
        self._frame_index = 0
        self._anim_job = None
        self._float_job = None
        self._cursor_job = None
        self._fullscreen_job = None
        self._visible = False
        self._auto_hidden = False
        self._panel_visible = True
        self._dimmed = False
        self._pause_fullscreen = pause_fullscreen
        self._x11 = None
        self._xdisplay = None
        self._opacity = max(0.40, min(1.0, opacity))

        self._load_frames()
        self._set_alpha(opacity)
        self._init_positions()
        self.win.withdraw()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def _load_frames(self) -> None:
        try:
            with Image.open(asset_path("gaspar_flutuando.gif")) as image:
                total = getattr(image, "n_frames", 1)
                for index in range(total):
                    image.seek(index)
                    frame = image.convert("RGBA").copy()
                    self._raw_frames.append(frame)
                    self._frames.append(ImageTk.PhotoImage(frame, master=self.win))
                    self._shape_bytes.append(self._bitmap_bytes(frame))
        except Exception as exc:
            self.log(f"Nao foi possivel carregar gaspar_flutuando.gif: {exc}")

        if not self._frames:
            try:
                with Image.open(asset_path("gaspar.png")) as image:
                    preview = image.convert("RGBA")
                    preview.thumbnail((SIDE - 30, SIDE - 30))
                    canvas = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
                    canvas.paste(preview, ((SIDE - preview.width) // 2, (SIDE - preview.height) // 2), preview)
                    self._raw_frames.append(canvas)
                    self._frames.append(ImageTk.PhotoImage(canvas, master=self.win))
                    self._shape_bytes.append(self._bitmap_bytes(canvas))
            except Exception as exc:
                self.log(f"Nao foi possivel carregar gaspar.png: {exc}")

        if self._frames:
            self._image_item = self.canvas.create_image(
                SIDE / 2, SIDE / 2, image=self._frames[0]
            )
        else:
            self.canvas.create_text(
                SIDE / 2,
                SIDE / 2,
                text="Gaspar",
                fill="#9bd40a",
                font=("Segoe UI", 18, "bold"),
            )

    @staticmethod
    def _bitmap_bytes(frame: Image.Image) -> bytes:
        mask = frame.getchannel("A").point(lambda value: 255 if value >= 128 else 0).convert("1")
        raw = mask.tobytes()
        bytes_per_line = (SIDE + 7) // 8
        output = bytearray()
        for row in range(SIDE):
            line = raw[row * bytes_per_line : (row + 1) * bytes_per_line]
            for byte in line:
                output.append(int(f"{byte:08b}"[::-1], 2))
        return bytes(output)

    def _init_positions(self) -> None:
        self._screen_width = self.win.winfo_screenwidth()
        self._screen_height = self.win.winfo_screenheight()
        self._positions = self._corner_positions()
        self._current_index = random.randrange(len(self._positions))
        self._current = self._positions[self._current_index]
        self._travel_from = self._current
        self._travel_to = None
        self._current_target_x, self._current_target_y = self._current
        self._travel_start = 0.0
        self._travel_duration = 0.0
        self._pause_until = time.monotonic() + 2.0
        self._x, self._y = self._current
        self._place(self._x, self._y)

    def _corner_positions(self) -> list[tuple[int, int]]:
        margin = 18
        bottom_margin = 64
        max_x = max(margin, self._screen_width - SIDE - margin)
        max_y = max(margin, self._screen_height - SIDE - bottom_margin)
        return [
            (margin, margin),
            (max_x, margin),
            (max_x, max_y),
            (margin, max_y),
        ]

    def _place(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y)
        self.win.geometry(f"{SIDE}x{SIDE}+{self._x}+{self._y}")

    def _set_alpha(self, opacity: float) -> None:
        self._opacity = max(0.40, min(1.0, opacity))
        if sys.platform != "win32" and not self._dimmed:
            try:
                self.win.attributes("-alpha", self._opacity)
            except tk.TclError:
                pass

    def _effective_alpha(self) -> float:
        return CURSOR_ALPHA if self._dimmed else self._opacity

    def _apply_window_alpha(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.SetLayeredWindowAttributes.argtypes = [
                    wintypes.HWND,
                    wintypes.COLORREF,
                    ctypes.c_ubyte,
                    wintypes.DWORD,
                ]
                user32.SetLayeredWindowAttributes(
                    self._hwnd(),
                    0x00FF00FF,
                    int(round(self._effective_alpha() * 255)),
                    0x00000001 | 0x00000002,
                )
            except Exception as exc:
                self.log(f"Nao foi possivel ajustar a opacidade: {exc}")
            return
        try:
            self.win.attributes("-alpha", self._effective_alpha())
        except tk.TclError:
            pass

    def _set_dimmed(self, dimmed: bool) -> None:
        if dimmed == self._dimmed:
            return
        self._dimmed = dimmed
        self._apply_window_alpha()

    def set_opacity(self, opacity: float) -> None:
        self._set_alpha(opacity)
        if sys.platform == "win32":
            self.win.after(30, self._apply_window_alpha)
        elif self._x11 is not None:
            self.win.after(30, self._apply_x11_frame)

    def set_panel_visible(self, visible: bool) -> None:
        if visible == self._panel_visible:
            return
        self._panel_visible = visible
        if self._visible and not self._auto_hidden:
            self._apply_topmost()

    def set_pause_fullscreen(self, enabled: bool) -> None:
        self._pause_fullscreen = enabled
        if not enabled:
            if self._auto_hidden:
                self._set_auto_hidden(False)
            return
        if self._visible and not self._auto_hidden and activity.fullscreen_app_active():
            self._set_auto_hidden(True)

    def show(self) -> None:
        if self._visible:
            return
        self._visible = True
        self._auto_hidden = self._pause_fullscreen and activity.fullscreen_app_active()
        if self._auto_hidden:
            self.win.withdraw()
        else:
            self.win.deiconify()
            self.win.lift()
            self._apply_topmost()
            self._animate()
            self._float_tick()
            self.win.after(80, self._apply_click_through)
            self.win.after(150, self._init_x11_shape)
        self._watch_cursor()
        self._watch_fullscreen()

    def hide(self) -> None:
        if not self._visible:
            return
        self._visible = False
        self._auto_hidden = False
        self._dimmed = False
        self._cancel_jobs()
        self.win.withdraw()

    def destroy(self) -> None:
        self._visible = False
        self._auto_hidden = False
        self._cancel_jobs()
        if self._x11 is not None:
            try:
                self._x11["x11"].XCloseDisplay(self._x11["display"])
            except Exception:
                pass
            self._x11 = None
        if self._xdisplay is not None:
            try:
                self._xdisplay.close()
            except Exception:
                pass
            self._xdisplay = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def _cancel_motion(self) -> None:
        for job in (self._anim_job, self._float_job):
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except tk.TclError:
                    pass
        self._anim_job = None
        self._float_job = None

    def _cancel_jobs(self) -> None:
        self._cancel_motion()
        for job in (self._cursor_job, self._fullscreen_job):
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except tk.TclError:
                    pass
        self._cursor_job = None
        self._fullscreen_job = None

    def _watch_cursor(self) -> None:
        if not self._visible:
            return
        if not self._auto_hidden:
            try:
                pointer_x, pointer_y = self.win.winfo_pointerxy()
            except tk.TclError:
                pointer_x, pointer_y = -1, -1
            if pointer_x >= 0:
                inside = (
                    self._x - CURSOR_PADDING <= pointer_x <= self._x + SIDE + CURSOR_PADDING
                    and self._y - CURSOR_PADDING <= pointer_y <= self._y + SIDE + CURSOR_PADDING
                )
                self._set_dimmed(inside)
        self._cursor_job = self.win.after(CURSOR_POLL_MS, self._watch_cursor)

    def _watch_fullscreen(self) -> None:
        if not self._visible:
            return
        hidden = self._pause_fullscreen and activity.fullscreen_app_active()
        self._set_auto_hidden(hidden)
        self._fullscreen_job = self.win.after(FULLSCREEN_POLL_MS, self._watch_fullscreen)

    def _set_auto_hidden(self, hidden: bool) -> None:
        if hidden == self._auto_hidden:
            return
        self._auto_hidden = hidden
        if hidden:
            self._cancel_motion()
            self.win.withdraw()
            return
        if not self._visible:
            return
        self._dimmed = False
        self.win.deiconify()
        self.win.lift()
        self._apply_topmost()
        self._pause_until = time.monotonic() + 2.0
        self._travel_to = None
        self._animate()
        self._float_tick()
        self.win.after(50, self._apply_window_alpha)
        self.win.after(50, self._apply_click_through)
        if self._x11 is not None:
            self.win.after(50, self._apply_x11_frame)
        else:
            self.win.after(150, self._init_x11_shape)

    def _animate(self) -> None:
        if not self._visible or self._auto_hidden:
            return
        if self._frames and len(self._frames) > 1:
            self._frame_index = (self._frame_index + 1) % len(self._frames)
            self.canvas.itemconfigure(self._image_item, image=self._frames[self._frame_index])
            if self._x11 is not None:
                self._apply_x11_frame()
        self._anim_job = self.win.after(FRAME_MS, self._animate)

    def _float_tick(self) -> None:
        if not self._visible or self._auto_hidden:
            return
        now = time.monotonic()

        if self._travel_to is None:
            if now >= self._pause_until:
                self._begin_travel(now)
            else:
                self._place(self._current[0], self._current[1] + self._bob(now))
        else:
            progress = (now - self._travel_start) / self._travel_duration
            if progress >= 1.0:
                self._current = self._travel_to
                self._travel_to = None
                self._pause_until = now + random.uniform(4.0, 9.0)
                self._place(self._current[0], self._current[1] + self._bob(now))
            else:
                eased = progress * progress * (3 - 2 * progress)
                x = self._travel_from[0] + (self._current_target_x - self._travel_from[0]) * eased
                y = self._travel_from[1] + (self._current_target_y - self._travel_from[1]) * eased
                self._place(x, y + self._bob(now))

        self._float_job = self.win.after(TICK_MS, self._float_tick)

    @staticmethod
    def _bob(now: float) -> int:
        return int(round(3.0 * math.sin(now * 1.7)))

    def _begin_travel(self, now: float) -> None:
        # Apenas cantos vizinhos: o trajeto segue a borda da tela em vez de
        # cruzar o centro, onde o usuario trabalha.
        next_index = (self._current_index + random.choice((-1, 1))) % len(self._positions)
        self._travel_from = self._current
        self._travel_to = self._positions[next_index]
        self._current_target_x, self._current_target_y = self._travel_to
        self._current_index = next_index
        self._travel_start = now
        self._travel_duration = random.uniform(7.0, 13.0)

    def _apply_topmost(self) -> None:
        try:
            self.win.attributes("-topmost", not self._panel_visible)
        except tk.TclError:
            pass
        if self._panel_visible:
            self._lower_below_panel()
        else:
            try:
                self.win.lift()
            except tk.TclError:
                pass

    def _lower_below_panel(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
                user32.GetAncestor.restype = wintypes.HWND
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    wintypes.UINT,
                ]
                root_hwnd = (
                    user32.GetAncestor(wintypes.HWND(self.root.winfo_id()), 2)
                    or self.root.winfo_id()
                )
                user32.SetWindowPos(
                    self._hwnd(),
                    root_hwnd,
                    0, 0, 0, 0,
                    0x0001 | 0x0002 | 0x0010,
                )
            except Exception:
                pass
            return
        if self._restack_x11():
            return
        try:
            self.win.lower(self.root)
        except tk.TclError:
            pass

    def _restack_x11(self) -> bool:
        """Reempilha o mascote abaixo do painel no X11.

        O mascote e override-redirect: o Tk ignora 'lower' com janela irma nesse
        caso e ele ficaria sempre por cima do painel. O empilhamento real e feito
        entre os quadros (frames) que o gerenciador de janelas cria.
        """
        if not sys.platform.startswith("linux"):
            return False
        try:
            from Xlib import X
            from Xlib import display as xdisplay

            if self._xdisplay is None:
                self._xdisplay = xdisplay.Display()
            display = self._xdisplay
            screen_root = display.screen().root

            def top_level(window_id: int):
                window = display.create_resource_object("window", window_id)
                parent = window.query_tree().parent
                while parent and parent.id != screen_root.id:
                    window = parent
                    parent = window.query_tree().parent
                return window

            mascot = top_level(self.win.winfo_id())
            panel = top_level(self.root.winfo_id())
            if mascot.id == panel.id:
                return False
            mascot.configure(sibling=panel, stack_mode=X.Below)
            display.sync()
            return True
        except Exception as exc:
            self.log(f"Empilhamento X11 indisponivel: {exc}")
            return False

    def _hwnd(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        return user32.GetAncestor(wintypes.HWND(self.win.winfo_id()), 2) or self.win.winfo_id()

    def _apply_click_through(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            hwnd = self._hwnd()

            gwl_exstyle = -20
            ws_ex_layered = 0x00080000
            ws_ex_transparent = 0x00000020
            ws_ex_toolwindow = 0x00000080
            ws_ex_noactivate = 0x08000000
            flags = ws_ex_layered | ws_ex_transparent | ws_ex_toolwindow | ws_ex_noactivate

            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long = user32.GetWindowLongPtrW
                set_long = user32.SetWindowLongPtrW
                get_long.restype = ctypes.c_ssize_t
                set_long.restype = ctypes.c_ssize_t
                get_long.argtypes = [wintypes.HWND, ctypes.c_int]
                set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            else:
                get_long = user32.GetWindowLongW
                set_long = user32.SetWindowLongW
                get_long.restype = ctypes.c_long
                set_long.restype = ctypes.c_long
                get_long.argtypes = [wintypes.HWND, ctypes.c_int]
                set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

            style = get_long(hwnd, gwl_exstyle)
            set_long(hwnd, gwl_exstyle, style | flags)
            self._apply_topmost()

            # Chroma key #FF00FF + opacidade na mesma chamada (LWA_COLORKEY | LWA_ALPHA).
            self._apply_window_alpha()
        except Exception as exc:
            self.log(f"Nao foi possivel ativar click-through: {exc}")

    def _init_x11_shape(self) -> None:
        if not sys.platform.startswith("linux") or not self._shape_bytes:
            return
        try:
            import ctypes

            x11 = ctypes.CDLL("libX11.so.6")
            xext = ctypes.CDLL("libXext.so.6")
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            display = x11.XOpenDisplay(None)
            if not display:
                raise RuntimeError("XOpenDisplay falhou")

            x11.XCreateBitmapFromData.restype = ctypes.c_ulong
            x11.XCreateBitmapFromData.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint
            ]
            x11.XFreePixmap.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            x11.XFlush.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xext.XShapeCombineMask.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_ulong, ctypes.c_int,
            ]
            xext.XShapeCombineRectangles.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ]

            self._x11 = {"x11": x11, "xext": xext, "display": display}
            self._apply_x11_frame()
            # Regiao de entrada vazia: todo clique atravessa o mascote.
            xext.XShapeCombineRectangles(display, self.win.winfo_id(), 2, 0, 0, None, 0, 0, 0)
            x11.XFlush(display)
        except Exception as exc:
            self._x11 = None
            self.log(f"Recorte X11 indisponivel; usando transparencia simples: {exc}")

    def _apply_x11_frame(self) -> None:
        if self._x11 is None or not self._shape_bytes:
            return
        try:
            import ctypes

            x11 = self._x11["x11"]
            xext = self._x11["xext"]
            display = self._x11["display"]
            data = self._shape_bytes[self._frame_index]
            buffer = (ctypes.c_char * len(data)).from_buffer_copy(data)
            pixmap = x11.XCreateBitmapFromData(
                display, self.win.winfo_id(), buffer, SIDE, SIDE
            )
            if not pixmap:
                return
            xext.XShapeCombineMask(display, self.win.winfo_id(), 0, 0, 0, pixmap, 0)
            x11.XFreePixmap(display, pixmap)
            x11.XFlush(display)
        except Exception as exc:
            self._x11 = None
            self.log(f"Falha ao aplicar recorte X11: {exc}")
