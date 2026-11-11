"""Deteccao de atividade do usuario e de aplicativos em tela cheia."""

from __future__ import annotations

import ctypes
import os
import sys

# O Xlib encerra o processo quando uma janela informada pelo gerenciador ja nao
# existe (BadWindow). Nas leituras best-effort abaixo o erro e esperado.
_XErrorHandler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
_IGNORE_X_ERRORS = _XErrorHandler(lambda _display, _event: 0)


def _ignore_x_errors(x11):
    x11.XSetErrorHandler.argtypes = [_XErrorHandler]
    x11.XSetErrorHandler.restype = ctypes.c_void_p
    return x11.XSetErrorHandler(_IGNORE_X_ERRORS)


def _restore_x_errors(x11, previous) -> None:
    x11.XSetErrorHandler(previous)


def idle_seconds() -> float | None:
    """Segundos desde o ultimo mouse/teclado. None quando nao ha deteccao."""
    if sys.platform == "win32":
        return _windows_idle()
    if sys.platform.startswith("linux"):
        return _linux_idle()
    return None


def fullscreen_app_active() -> bool:
    """True quando um aplicativo em tela cheia esta em primeiro plano."""
    if sys.platform == "win32":
        return _windows_fullscreen()
    if sys.platform.startswith("linux"):
        return _linux_fullscreen()
    return False


def _windows_idle() -> float | None:
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        kernel32 = ctypes.windll.kernel32
        kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        elapsed = kernel32.GetTickCount64() - info.dwTime
        return max(0.0, elapsed / 1000.0)
    except Exception:
        return None


def _windows_fullscreen() -> bool:
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        hwnd = user32.GetForegroundWindow()
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return False

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False

        screen = info.rcMonitor
        covers = (
            rect.left <= screen.left + 2
            and rect.top <= screen.top + 2
            and rect.right >= screen.right - 2
            and rect.bottom >= screen.bottom - 2
        )
        if not covers:
            return False

        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        return name.value not in {"Progman", "WorkerW", "Shell_TrayWnd"}
    except Exception:
        return False


def _linux_idle() -> float | None:
    if not os.environ.get("DISPLAY"):
        return None
    display = None
    try:
        class XScreenSaverInfo(ctypes.Structure):
            _fields_ = [
                ("window", ctypes.c_ulong),
                ("state", ctypes.c_int),
                ("kind", ctypes.c_int),
                ("til_or_since", ctypes.c_ulong),
                ("idle", ctypes.c_ulong),
                ("eventMask", ctypes.c_ulong),
            ]

        x11 = ctypes.CDLL("libX11.so.6")
        xss = ctypes.CDLL("libXss.so.1")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XFree.argtypes = [ctypes.c_void_p]
        xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
        xss.XScreenSaverQueryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(XScreenSaverInfo),
        ]

        display = x11.XOpenDisplay(None)
        if not display:
            return None
        info = xss.XScreenSaverAllocInfo()
        if not info:
            return None
        try:
            root = x11.XDefaultRootWindow(display)
            if not xss.XScreenSaverQueryInfo(display, root, info):
                return None
            return max(0.0, info.contents.idle / 1000.0)
        finally:
            x11.XFree(info)
    except Exception:
        return None
    finally:
        _close_display(display)


def _close_display(display) -> None:
    if not display:
        return
    try:
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay(display)
    except Exception:
        pass


def _linux_fullscreen() -> bool:
    if not os.environ.get("DISPLAY"):
        return False
    display = None
    try:
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XGetWindowProperty.restype = ctypes.c_int
        x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

        display = x11.XOpenDisplay(None)
        if not display:
            return False
        root = x11.XDefaultRootWindow(display)
        previous = _ignore_x_errors(x11)
        try:
            active = _x11_property_ulong(x11, display, root, "_NET_ACTIVE_WINDOW", 33, 1)
            if not active:
                return False
            states = _x11_property_ulong(
                x11,
                display,
                active[0],
                "_NET_WM_STATE",
                4,
                64,
            )
            fullscreen_atom = x11.XInternAtom(display, b"_NET_WM_STATE_FULLSCREEN", 0)
            return bool(states) and fullscreen_atom in states
        finally:
            _restore_x_errors(x11, previous)
    except Exception:
        return False
    finally:
        _close_display(display)


def _x11_property_ulong(x11, display, window, name: str, req_type: int, length: int):
    atom = x11.XInternAtom(display, name.encode("ascii"), 0)
    actual_type = ctypes.c_ulong()
    actual_format = ctypes.c_int()
    count = ctypes.c_ulong()
    remaining = ctypes.c_ulong()
    data = ctypes.POINTER(ctypes.c_ubyte)()
    status = x11.XGetWindowProperty(
        display,
        window,
        atom,
        0,
        length,
        0,
        req_type,
        ctypes.byref(actual_type),
        ctypes.byref(actual_format),
        ctypes.byref(count),
        ctypes.byref(remaining),
        ctypes.byref(data),
    )
    if status != 0 or not data or actual_format.value != 32 or count.value == 0:
        if data:
            x11.XFree(data)
        return []
    try:
        values = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))
        return [values[index] for index in range(count.value)]
    finally:
        x11.XFree(data)
