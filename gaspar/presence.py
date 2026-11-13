"""Motor de simulacao de presenca (mouse, teclado e telemetria do sistema)."""

from __future__ import annotations

import math
import random
import threading
import time

from . import activity
from .config import KEY_CHOICES, Settings
from .paths import data_dir

MOVEMENT_LABELS = {
    "micro": "micro",
    "small": "curto",
    "medium": "curto-medio",
}


class PresenceEngine:
    def __init__(self, settings_provider, log_event, log_system, bell=None):
        self._settings = settings_provider
        self._log_event = log_event
        self._log_system = log_system
        self._bell = bell or (lambda: None)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._next_at: float | None = None
        self._backend = None
        self._backend_error: str | None = None
        self._last_defer_log = float("-inf")
        self.cycles = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def seconds_remaining(self) -> int | None:
        with self._lock:
            next_at = self._next_at
        if next_at is None:
            return None
        return max(0, math.ceil(next_at - time.monotonic()))

    def start(self) -> None:
        if self.is_running:
            return
        settings = self._settings()
        self._stop.clear()
        self.cycles = 0
        delay = min(10, max(1, settings.interval))
        with self._lock:
            self._next_at = time.monotonic() + delay
        self._thread = threading.Thread(target=self._run, name="gaspar-presence", daemon=True)
        self._thread.start()
        self._log_event(f"Simulacao ativada. Intervalo: {settings.interval}s; primeira acao em {delay}s.")
        if settings.only_when_idle and activity.idle_seconds() is None:
            self._log_system(
                "Deteccao de inatividade indisponivel neste sistema; "
                "os ciclos seguirao apenas o intervalo configurado."
            )

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None
        with self._lock:
            self._next_at = None
        self._log_event("Simulacao desativada.")

    def _load_backend(self):
        if self._backend is not None:
            return self._backend
        if self._backend_error is not None:
            return None
        try:
            import pyautogui

            pyautogui.PAUSE = 0
            self._backend = pyautogui
        except Exception as exc:
            self._backend_error = str(exc)
            self._log_system(f"Automacao de mouse/teclado indisponivel: {exc}")
        return self._backend

    def _run(self) -> None:
        backend = self._load_backend()
        while not self._stop.is_set():
            with self._lock:
                next_at = self._next_at
            if next_at is None:
                break
            remaining = next_at - time.monotonic()
            if remaining > 0:
                self._stop.wait(min(0.5, remaining))
                continue

            settings = self._settings()
            reason = self._defer_reason(settings)
            if reason is not None:
                self._defer(reason, settings)
                continue

            self._execute_cycle(backend)
            self.cycles += 1
            self._log_event(f"Total de ciclos: {self.cycles}")
            with self._lock:
                self._next_at = time.monotonic() + max(1, settings.interval)

        with self._lock:
            self._next_at = None

    def _defer_reason(self, settings: Settings) -> str | None:
        if settings.pause_fullscreen and activity.fullscreen_app_active():
            return "aplicativo em tela cheia em primeiro plano"
        if settings.only_when_idle:
            idle = activity.idle_seconds()
            if idle is not None and idle < settings.idle_seconds:
                return "usuario ativo no computador"
        return None

    def _defer(self, reason: str, settings: Settings) -> None:
        now = time.monotonic()
        retry = min(max(10, settings.interval), 30)
        with self._lock:
            self._next_at = now + retry
        if now - self._last_defer_log >= 300:
            self._last_defer_log = now
            self._log_system(f"Ciclo adiado: {reason}. Nova tentativa em {retry}s.")

    def _execute_cycle(self, backend) -> None:
        settings: Settings = self._settings()
        actions = 0
        essentials = 0

        if settings.simulate_mouse:
            essentials += 1
            try:
                if backend is None:
                    raise RuntimeError(self._backend_error or "biblioteca de automacao ausente")
                kind, origin, target = self._move_mouse(backend)
                actions += 1
                self._log_event(f"Mouse movido ({MOVEMENT_LABELS[kind]}).")
                self._restore_cursor(backend, settings, origin, target)
            except Exception as exc:
                self._log_event(f"Falha no movimento do mouse: {exc}")

        if settings.press_key != "none" or settings.keep_teams:
            essentials += 1
            try:
                if backend is None:
                    raise RuntimeError(self._backend_error or "biblioteca de automacao ausente")
                self._send_activity(backend, settings)
                actions += 1
            except Exception as exc:
                self._log_event(f"Falha ao simular teclado: {exc}")

        if settings.sound:
            try:
                self._bell()
            except Exception:
                pass

        if settings.system_telemetry:
            self._system_snapshot()

        if essentials == 0:
            self._log_event("Nenhuma acao esta habilitada; o ciclo nao simulou atividade.")
            return

        outcome = "com sucesso" if actions == essentials else "com falhas"
        self._log_event(
            f"Ciclo automatico #{self.cycles + 1} executado {outcome} "
            f"({actions}/{essentials} operacoes)."
        )

    def _move_mouse(self, pyautogui) -> tuple[str, tuple[int, int], tuple[int, int]]:
        current = pyautogui.position()
        width, height = pyautogui.size()
        x0, y0 = int(current[0]), int(current[1])
        margin = 8
        kind = random.choices(
            ["micro", "small", "medium"],
            weights=[45, 40, 15],
            k=1,
        )[0]

        if kind == "micro":
            x1 = x0 + random.randint(-3, 3)
            y1 = y0 + random.randint(-3, 3)
            duration = random.uniform(0.25, 0.45)
        elif kind == "small":
            x1 = x0 + random.randint(-20, 20)
            y1 = y0 + random.randint(-20, 20)
            duration = random.uniform(0.45, 0.75)
        else:
            x1 = x0 + random.randint(-55, 55)
            y1 = y0 + random.randint(-55, 55)
            duration = random.uniform(0.8, 1.2)

        # Distancia curta e previsivel: o cursor nao sai da area de trabalho
        # do usuario nem percorre a tela inteira.
        x1 = min(max(margin, x1), max(margin, width - margin))
        y1 = min(max(margin, y1), max(margin, height - margin))

        points = self._sample_path(x0, y0, x1, y1)
        self._glide(pyautogui, points, duration)
        return kind, (x0, y0), (x1, y1)

    def _restore_cursor(self, pyautogui, settings: Settings, origin, target) -> None:
        if not settings.only_when_idle or origin == target:
            return
        idle = activity.idle_seconds()
        if idle is None or idle < settings.idle_seconds:
            return
        self._stop.wait(0.6)
        if self._stop.is_set():
            return
        current = pyautogui.position()
        if math.hypot(current[0] - target[0], current[1] - target[1]) > 12:
            return  # o usuario assumiu o controle; nao puxar o cursor de volta
        points = self._sample_path(current[0], current[1], origin[0], origin[1])
        self._glide(pyautogui, points, 0.7)
        self._log_event("Cursor devolvido a posicao original.")

    @staticmethod
    def _sample_path(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
        steps = 36
        points: list[tuple[int, int]] = []
        for index in range(1, steps + 1):
            t = index / steps
            eased = t * t * (3 - 2 * t)
            x = x0 + (x1 - x0) * eased
            y = y0 + (y1 - y0) * eased
            points.append((int(round(x)), int(round(y))))
        return points

    def _glide(self, pyautogui, points: list[tuple[int, int]], duration: float) -> None:
        if not points:
            return
        delay = max(0.004, duration / len(points))
        for x, y in points:
            if self._stop.is_set():
                return
            pyautogui.moveTo(x, y, _pause=False)
            time.sleep(delay)

    def _send_activity(self, pyautogui, settings: Settings) -> None:
        if settings.press_key != "none":
            pyautogui.press(settings.press_key)
            label = KEY_CHOICES.get(settings.press_key, settings.press_key)
            self._log_event(f"Tecla {label} pressionada.")

        if settings.keep_teams:
            position = pyautogui.position()
            pyautogui.moveTo(position[0] + 1, position[1], _pause=False)
            pyautogui.moveTo(position[0], position[1], _pause=False)
            if settings.press_key == "none":
                pyautogui.press("f15")
            self._log_event("Toque de atividade enviado (Teams/Slack).")

    def _system_snapshot(self) -> None:
        try:
            import psutil
        except ImportError:
            self._log_system("psutil nao instalado; telemetria do sistema ignorada.")
            return
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            memory = psutil.virtual_memory().percent
            disk = psutil.disk_usage(str(data_dir())).percent
            self._log_system(
                f"CPU {cpu:.0f}%, Memoria {memory:.0f}%, Disco {disk:.0f}%"
            )
        except Exception as exc:
            self._log_system(f"Erro ao obter telemetria do sistema: {exc}")
