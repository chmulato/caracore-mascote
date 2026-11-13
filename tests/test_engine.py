"""Testes do motor de simulacao de presenca, com backend falso e sem mexer no mouse."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from gaspar import presence
from gaspar.config import Settings
from gaspar.presence import PresenceEngine


class FakeBackend:
    def __init__(self, posicao=(100, 100), tamanho=(1920, 1080)):
        self._posicao = posicao
        self._tamanho = tamanho
        self.movimentos: list[tuple[int, int]] = []
        self.teclas: list[str] = []

    def position(self):
        return self._posicao

    def size(self):
        return self._tamanho

    def moveTo(self, x, y, _pause=False):
        self.movimentos.append((int(x), int(y)))
        self._posicao = (int(x), int(y))

    def press(self, key):
        self.teclas.append(key)


def make_engine(settings: Settings | None = None):
    estado = settings or Settings()
    eventos: list[str] = []
    sistema: list[str] = []
    sinos: list[int] = []
    engine = PresenceEngine(
        lambda: estado,
        eventos.append,
        sistema.append,
        bell=lambda: sinos.append(1),
    )
    return engine, estado, eventos, sistema, sinos


class CycleTests(unittest.TestCase):
    def test_mouse_and_keyboard_run_together(self):
        engine, estado, eventos, _, _ = make_engine(
            Settings(simulate_mouse=True, press_key="f15", keep_teams=False, only_when_idle=False)
        )
        backend = FakeBackend()
        with mock.patch.object(presence.PresenceEngine, "_glide"):
            engine._execute_cycle(backend)
        self.assertEqual(backend.teclas, ["f15"])
        self.assertTrue(any("Mouse movido" in evento for evento in eventos))
        self.assertIn("Tecla F15 pressionada.", eventos)
        self.assertIn("Ciclo automatico #1 executado com sucesso (2/2 operacoes).", eventos)

    def test_mouse_stays_inside_the_screen(self):
        engine, estado, _, _, _ = make_engine(
            Settings(simulate_mouse=True, press_key="none", keep_teams=False, only_when_idle=False)
        )
        backend = FakeBackend(posicao=(12, 12), tamanho=(120, 90))
        with mock.patch.object(presence.time, "sleep"):
            engine._execute_cycle(backend)
        self.assertTrue(backend.movimentos)
        for x, y in backend.movimentos:
            self.assertGreaterEqual(x, 8)
            self.assertGreaterEqual(y, 8)
            self.assertLessEqual(x, 112)
            self.assertLessEqual(y, 82)

    def test_keep_teams_touches_activity_without_configured_key(self):
        engine, estado, eventos, _, _ = make_engine(
            Settings(simulate_mouse=False, press_key="none", keep_teams=True, only_when_idle=False)
        )
        backend = FakeBackend()
        engine._execute_cycle(backend)
        self.assertEqual(len(backend.movimentos), 2)
        self.assertEqual(backend.teclas, ["f15"])
        self.assertIn("Toque de atividade enviado (Teams/Slack).", eventos)

    def test_missing_backend_reports_both_failures(self):
        engine, estado, eventos, _, _ = make_engine(
            Settings(simulate_mouse=True, press_key="f15", keep_teams=False, only_when_idle=False)
        )
        engine._execute_cycle(None)
        self.assertTrue(any("Falha no movimento do mouse" in evento for evento in eventos))
        self.assertTrue(any("Falha ao simular teclado" in evento for evento in eventos))
        self.assertIn("Ciclo automatico #1 executado com falhas (0/2 operacoes).", eventos)

    def test_nothing_enabled_is_reported(self):
        engine, estado, eventos, _, _ = make_engine(
            Settings(simulate_mouse=False, press_key="none", keep_teams=False, only_when_idle=False)
        )
        engine._execute_cycle(FakeBackend())
        self.assertIn("Nenhuma acao esta habilitada; o ciclo nao simulou atividade.", eventos)

    def test_sound_uses_the_bell(self):
        engine, estado, _, _, sinos = make_engine(
            Settings(simulate_mouse=False, press_key="none", keep_teams=False, sound=True)
        )
        engine._execute_cycle(FakeBackend())
        self.assertEqual(sinos, [1])

    def test_system_telemetry_is_logged(self):
        fake = types.SimpleNamespace(
            cpu_percent=lambda interval=0: 12.0,
            virtual_memory=lambda: types.SimpleNamespace(percent=46.0),
            disk_usage=lambda _path: types.SimpleNamespace(percent=78.0),
        )
        engine, estado, _, sistema, _ = make_engine(
            Settings(simulate_mouse=False, press_key="none", keep_teams=False, system_telemetry=True)
        )
        with mock.patch.dict(sys.modules, {"psutil": fake}):
            engine._execute_cycle(FakeBackend())
        self.assertIn("CPU 12%, Memoria 46%, Disco 78%", sistema)

    def test_telemetry_without_psutil_and_with_error(self):
        engine, estado, _, sistema, _ = make_engine(
            Settings(simulate_mouse=False, press_key="none", keep_teams=False, system_telemetry=True)
        )
        with mock.patch.dict(sys.modules, {"psutil": None}):
            engine._execute_cycle(FakeBackend())
        self.assertIn("psutil nao instalado; telemetria do sistema ignorada.", sistema)

        quebrado = types.SimpleNamespace(
            cpu_percent=mock.Mock(side_effect=RuntimeError("sem leitura"))
        )
        with mock.patch.dict(sys.modules, {"psutil": quebrado}):
            engine._execute_cycle(FakeBackend())
        self.assertTrue(any("Erro ao obter telemetria" in linha for linha in sistema))


class DeferTests(unittest.TestCase):
    def test_fullscreen_has_priority(self):
        engine, estado, _, _, _ = make_engine(
            Settings(pause_fullscreen=True, only_when_idle=True, idle_seconds=60)
        )
        with mock.patch.object(presence.activity, "fullscreen_app_active", return_value=True), mock.patch.object(
            presence.activity, "idle_seconds", return_value=0
        ):
            self.assertIn("tela cheia", engine._defer_reason(estado))

    def test_active_user_defers_and_idle_user_does_not(self):
        engine, estado, _, _, _ = make_engine(
            Settings(pause_fullscreen=False, only_when_idle=True, idle_seconds=60)
        )
        with mock.patch.object(presence.activity, "idle_seconds", return_value=5):
            self.assertEqual(engine._defer_reason(estado), "usuario ativo no computador")
        with mock.patch.object(presence.activity, "idle_seconds", return_value=120):
            self.assertIsNone(engine._defer_reason(estado))
        with mock.patch.object(presence.activity, "idle_seconds", return_value=None):
            self.assertIsNone(engine._defer_reason(estado))

    def test_defer_reschedules_and_logs_only_once(self):
        with mock.patch.object(presence.time, "monotonic", return_value=100.0):
            engine, estado, _, sistema, _ = make_engine(Settings(interval=300, only_when_idle=True))
            engine._defer("usuario ativo no computador", estado)
            self.assertEqual(engine.seconds_remaining(), 30)
            engine._defer("usuario ativo no computador", estado)
            self.assertEqual(len(sistema), 1)
            self.assertIn("Nova tentativa em 30s", sistema[0])

            curto, curto_estado, _, _, _ = make_engine(Settings(interval=20, only_when_idle=True))
            curto._defer("motivo", curto_estado)
            self.assertEqual(curto.seconds_remaining(), 20)


class CursorTests(unittest.TestCase):
    def test_cursor_returns_when_user_is_away(self):
        engine, estado, eventos, _, _ = make_engine(
            Settings(only_when_idle=True, idle_seconds=60)
        )
        backend = FakeBackend(posicao=(50, 50))
        with mock.patch.object(presence.activity, "idle_seconds", return_value=120), mock.patch.object(
            presence.PresenceEngine, "_glide"
        ) as glide:
            engine._restore_cursor(backend, estado, (10, 10), (50, 50))
        glide.assert_called_once()
        self.assertIn("Cursor devolvido a posicao original.", eventos)

    def test_cursor_is_not_pulled_when_user_moved_it(self):
        engine, estado, eventos, _, _ = make_engine(
            Settings(only_when_idle=True, idle_seconds=60)
        )
        backend = FakeBackend(posicao=(100, 100))
        with mock.patch.object(presence.activity, "idle_seconds", return_value=120), mock.patch.object(
            presence.PresenceEngine, "_glide"
        ) as glide:
            engine._restore_cursor(backend, estado, (10, 10), (50, 50))
        glide.assert_not_called()
        self.assertNotIn("Cursor devolvido a posicao original.", eventos)

    def test_cursor_is_not_restored_while_configured_off_or_user_active(self):
        engine, estado, eventos, _, _ = make_engine(Settings(only_when_idle=False))
        backend = FakeBackend(posicao=(50, 50))
        with mock.patch.object(presence.PresenceEngine, "_glide") as glide:
            engine._restore_cursor(backend, estado, (10, 10), (50, 50))
        glide.assert_not_called()

        ativo, ativo_estado, _, _, _ = make_engine(Settings(only_when_idle=True, idle_seconds=60))
        with mock.patch.object(presence.activity, "idle_seconds", return_value=10), mock.patch.object(
            presence.PresenceEngine, "_glide"
        ) as glide2:
            ativo._restore_cursor(backend, ativo_estado, (10, 10), (50, 50))
        glide2.assert_not_called()


class PathTests(unittest.TestCase):
    def test_sample_path_has_36_steps_and_lands_on_target(self):
        pontos = PresenceEngine._sample_path(0, 0, 100, 50)
        self.assertEqual(len(pontos), 36)
        self.assertEqual(pontos[-1], (100, 50))
        x_anterior = 0
        for x, _y in pontos:
            self.assertGreaterEqual(x, x_anterior)
            x_anterior = x

    def test_glide_stops_when_requested(self):
        engine, _, _, _, _ = make_engine()
        backend = FakeBackend()
        engine._stop.set()
        engine._glide(backend, [(1, 1), (2, 2)], 0.1)
        self.assertEqual(backend.movimentos, [])

    def test_glide_moves_through_all_points(self):
        engine, _, _, _, _ = make_engine()
        backend = FakeBackend()
        with mock.patch.object(presence.time, "sleep"):
            engine._glide(backend, [(1, 1), (2, 2)], 0.1)
        self.assertEqual(backend.movimentos, [(1, 1), (2, 2)])


class LifecycleTests(unittest.TestCase):
    def test_backend_import_failure_is_reported_once(self):
        engine, _, _, sistema, _ = make_engine()
        with mock.patch.dict(sys.modules, {"pyautogui": None}):
            self.assertIsNone(engine._load_backend())
            self.assertIsNone(engine._load_backend())
        self.assertEqual(len(sistema), 1)
        self.assertIn("Automacao de mouse/teclado indisponivel", sistema[0])

    def test_start_and_stop(self):
        engine, _, eventos, _, _ = make_engine(
            Settings(interval=10, only_when_idle=False, simulate_mouse=False, press_key="none")
        )
        self.assertFalse(engine.is_running)
        self.assertIsNone(engine.seconds_remaining())
        engine.start()
        try:
            self.assertTrue(engine.is_running)
            self.assertIn(engine.seconds_remaining(), (9, 10))
            engine.start()
        finally:
            engine.stop()
        self.assertFalse(engine.is_running)
        self.assertTrue(any("Simulacao ativada" in linha for linha in eventos))
        self.assertIn("Simulacao desativada.", eventos)
        self.assertEqual(sum("Simulacao ativada" in linha for linha in eventos), 1)

    def test_start_warns_when_idle_detection_is_unavailable(self):
        engine, _, _, sistema, _ = make_engine(
            Settings(interval=60, only_when_idle=True, simulate_mouse=False, press_key="none")
        )
        with mock.patch.object(presence.activity, "idle_seconds", return_value=None):
            engine.start()
            try:
                self.assertTrue(engine.is_running)
            finally:
                engine.stop()
        self.assertTrue(any("Deteccao de inatividade indisponivel" in linha for linha in sistema))


if __name__ == "__main__":
    unittest.main()
