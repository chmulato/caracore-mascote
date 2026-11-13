"""Testes do nucleo do Gaspar que nao depende de tela (config, paths, hosts e SO)."""

from __future__ import annotations

import contextlib
import ctypes
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from gaspar import activity, autostart, blackbox, eventlog, paths, telemetry_hosts
from gaspar.config import (
    MAX_IDLE,
    MAX_INTERVAL,
    MIN_IDLE,
    MIN_INTERVAL,
    Settings,
    load_settings,
    save_settings,
)
from gaspar.overlay import GasparOverlay


class ConfigTests(unittest.TestCase):
    def test_defaults_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = load_settings(Path(tmp) / "config.json")
            self.assertEqual(settings, Settings())

    def test_corrupt_or_non_object_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text("{isto nao e json", encoding="utf-8")
            self.assertEqual(load_settings(target), Settings())
            target.write_text("[]", encoding="utf-8")
            self.assertEqual(load_settings(target), Settings())

    def test_unknown_keys_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(json.dumps({"interval": 60, "campo_novo": 1}), encoding="utf-8")
            settings = load_settings(target)
            self.assertEqual(settings.interval, 60)
            self.assertFalse(hasattr(settings, "campo_novo"))

    def test_interval_idle_and_opacity_are_clamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(
                json.dumps({"interval": 1, "idle_seconds": 1, "opacity": 10}),
                encoding="utf-8",
            )
            settings = load_settings(target)
            self.assertEqual(settings.interval, MIN_INTERVAL)
            self.assertEqual(settings.idle_seconds, MIN_IDLE)
            self.assertEqual(settings.opacity, 50)

            target.write_text(
                json.dumps({"interval": 99999, "idle_seconds": 99999, "opacity": 999}),
                encoding="utf-8",
            )
            settings = load_settings(target)
            self.assertEqual(settings.interval, MAX_INTERVAL)
            self.assertEqual(settings.idle_seconds, MAX_IDLE)
            self.assertEqual(settings.opacity, 100)

    def test_invalid_types_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(
                json.dumps({"interval": "abc", "idle_seconds": None, "opacity": "x"}),
                encoding="utf-8",
            )
            settings = load_settings(target)
            self.assertEqual(settings.interval, 300)
            self.assertEqual(settings.idle_seconds, 60)
            self.assertEqual(settings.opacity, 82)

    def test_key_and_booleans_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(
                json.dumps({"press_key": "tecla-invalida", "sound": 1, "overlay": 0}),
                encoding="utf-8",
            )
            settings = load_settings(target)
            self.assertEqual(settings.press_key, "f15")
            self.assertTrue(settings.sound)
            self.assertFalse(settings.overlay)

    def test_save_is_atomic_and_clamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "config.json"
            save_settings(Settings(interval=1, opacity=999), target)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["interval"], MIN_INTERVAL)
            self.assertEqual(payload["opacity"], 100)
            self.assertFalse(target.with_suffix(".json.tmp").exists())

    def test_default_path_uses_gaspar_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"GASPAR_HOME": tmp}):
                save_settings(Settings(interval=55))
                self.assertTrue((Path(tmp) / "config.json").exists())
                self.assertEqual(load_settings().interval, 55)


class PathsTests(unittest.TestCase):
    def test_gaspar_home_overrides_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "dados"
            with mock.patch.dict(os.environ, {"GASPAR_HOME": str(alvo)}):
                self.assertEqual(paths.data_dir(), alvo)
                self.assertTrue(alvo.is_dir())
                self.assertEqual(paths.log_path(), alvo / "cycle_log.txt")
                self.assertEqual(paths.config_path(), alvo / "config.json")

    def test_linux_and_windows_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sys, "platform", "linux"):
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp, "GASPAR_HOME": ""}):
                self.assertEqual(paths.data_dir(), Path(tmp) / "caracore" / "gaspar")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sys, "platform", "win32"):
            with mock.patch.dict(os.environ, {"APPDATA": tmp, "GASPAR_HOME": ""}):
                self.assertEqual(paths.data_dir(), Path(tmp) / "CaraCore" / "Gaspar")

    def test_frozen_paths_use_meipass(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
                sys, "_MEIPASS", tmp, create=True
            ):
                self.assertEqual(paths.project_root(), Path(tmp))

    def test_asset_path_falls_back_to_expected_location(self):
        existente = paths.asset_path("gaspar.png")
        self.assertTrue(existente.exists())
        ausente = paths.asset_path("nao-existe.bin")
        self.assertEqual(ausente, paths.project_root() / "assets" / "nao-existe.bin")


class EventLogTests(unittest.TestCase):
    def test_creates_header_and_appends_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = eventlog.EventLog(Path(tmp) / "log.txt")
            line = log.write("motor", "ciclo 1")
            self.assertIn("motor: ciclo 1", line)
            texto = (Path(tmp) / "log.txt").read_text(encoding="utf-8")
            self.assertIn("Log de ciclos iniciado", texto)
            self.assertIn("motor: ciclo 1", texto)

    def test_disabled_returns_line_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = eventlog.EventLog(Path(tmp) / "log.txt")
            log.set_enabled(False)
            line = log.write("motor", "ignorado")
            self.assertIn("ignorado", line)
            self.assertNotIn("ignorado", (Path(tmp) / "log.txt").read_text(encoding="utf-8"))

    def test_rotation_moves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "log.txt"
            log = eventlog.EventLog(target)
            with mock.patch.object(eventlog, "MAX_BYTES", 1):
                log.write("motor", "x" * 50)
            backup = target.with_suffix(".txt.1")
            self.assertTrue(backup.exists())
            self.assertIn("Log de ciclos iniciado", backup.read_text(encoding="utf-8"))
            self.assertIn("x" * 50, target.read_text(encoding="utf-8"))

    def test_write_failure_is_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "log.txt"
            log = eventlog.EventLog(target)
            target.unlink()
            target.mkdir()
            self.assertIsInstance(log.write("motor", "sem escrita"), str)


class HostsTests(unittest.TestCase):
    def make_hosts(self, tmp: str, content: str = "# hosts\n127.0.0.1 localhost\n") -> Path:
        path = Path(tmp) / "hosts"
        path.write_text(content, encoding="utf-8", newline="")
        return path

    def test_read_error_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            content, error = telemetry_hosts.read_hosts(Path(tmp) / "nao-existe")
            self.assertEqual(content, "")
            self.assertTrue(error)
            self.assertFalse(telemetry_hosts.has_block(content))

    def test_apply_is_idempotent_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_hosts(tmp)
            self.assertIsNone(telemetry_hosts.apply_block(path))
            texto = path.read_text(encoding="utf-8")
            self.assertTrue(telemetry_hosts.has_block(texto))
            self.assertIn("127.0.0.1 localhost", texto)
            self.assertEqual(texto.count(telemetry_hosts.MARKER_START), 1)
            self.assertEqual(texto.count("0.0.0.0 "), len(telemetry_hosts.DOMAINS))
            self.assertIsNone(telemetry_hosts.apply_block(path))
            self.assertEqual(path.read_text(encoding="utf-8").count(telemetry_hosts.MARKER_START), 1)

    def test_crlf_is_normalized_when_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_hosts(tmp, "# hosts\r\n127.0.0.1 localhost\r\n")
            self.assertIsNone(telemetry_hosts.apply_block(path))
            texto = path.read_text(encoding="utf-8")
            self.assertTrue(telemetry_hosts.has_block(texto))
            self.assertIn("127.0.0.1 localhost", texto)

    def test_remove_block_and_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_hosts(tmp)
            self.assertIsNone(telemetry_hosts.remove_block(path))
            self.assertIsNone(telemetry_hosts.apply_block(path))
            self.assertIsNone(telemetry_hosts.remove_block(path))
            texto = path.read_text(encoding="utf-8")
            self.assertNotIn(telemetry_hosts.MARKER_START, texto)
            self.assertIn("127.0.0.1 localhost", texto)

    def test_flush_dns_reports_missing_commands(self):
        with mock.patch.object(telemetry_hosts.shutil, "which", return_value=None):
            erro = telemetry_hosts.flush_dns()
            self.assertIn("nenhum comando disponivel", erro)

    def test_flush_dns_accepts_a_successful_command(self):
        ok = types.SimpleNamespace(returncode=0, stderr="")
        with mock.patch.object(telemetry_hosts.shutil, "which", return_value="x"), mock.patch.object(
            telemetry_hosts.subprocess, "run", return_value=ok
        ):
            self.assertIsNone(telemetry_hosts.flush_dns())

    def test_flush_dns_reports_failures(self):
        falha = types.SimpleNamespace(returncode=1, stderr="boom")
        with mock.patch.object(telemetry_hosts.shutil, "which", return_value="x"), mock.patch.object(
            telemetry_hosts.subprocess, "run", return_value=falha
        ):
            self.assertIn("boom", telemetry_hosts.flush_dns())
        with mock.patch.object(telemetry_hosts.shutil, "which", return_value="x"), mock.patch.object(
            telemetry_hosts.subprocess, "run", side_effect=RuntimeError("recusado")
        ):
            self.assertIn("recusado", telemetry_hosts.flush_dns())

    def run_main(self, *args: str):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            code = telemetry_hosts.main(list(args))
        return code, saida.getvalue(), erro.getvalue()

    def test_main_status_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_hosts(tmp)
            code, saida, _ = self.run_main("--hosts", str(path), "--status")
            self.assertEqual(code, 0)
            self.assertIn("inativo", saida)
            code, saida, _ = self.run_main("--hosts", str(path), "--dry-run")
            self.assertEqual(code, 0)
            self.assertIn("gravaria", saida)
            self.assertNotIn(telemetry_hosts.MARKER_START, path.read_text(encoding="utf-8"))
            code, saida, _ = self.run_main("--hosts", str(path), "--dry-run", "--remove")
            self.assertEqual(code, 0)
            self.assertIn("nao encontrou", saida)

    def test_main_applies_and_removes_when_admin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_hosts(tmp)
            with mock.patch.object(telemetry_hosts, "is_admin", return_value=True):
                code, saida, _ = self.run_main("--hosts", str(path))
                self.assertEqual(code, 0)
                self.assertIn(f"{len(telemetry_hosts.DOMAINS)} dominios", saida)
                self.assertTrue(telemetry_hosts.has_block(path.read_text(encoding="utf-8")))
                code, saida, _ = self.run_main("--hosts", str(path), "--remove")
                self.assertEqual(code, 0)
                self.assertFalse(telemetry_hosts.has_block(path.read_text(encoding="utf-8")))

    def test_main_requires_admin_and_reports_read_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_hosts(tmp)
            with mock.patch.object(telemetry_hosts, "is_admin", return_value=False):
                code, _, erro = self.run_main("--hosts", str(path))
                self.assertEqual(code, 1)
                self.assertIn("Administrador" if sys.platform == "win32" else "root", erro)
            code, _, erro = self.run_main("--hosts", str(Path(tmp) / "ausente"), "--status")
            self.assertEqual(code, 1)
            self.assertIn("ERRO", erro)


class FakeWinregKey:
    def __init__(self, data: dict):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values: dict[str, dict] = {}

    def OpenKey(self, _root, name, *_args):
        if name not in self.values:
            raise FileNotFoundError(name)
        return FakeWinregKey(self.values[name])

    def CreateKey(self, _root, name):
        return FakeWinregKey(self.values.setdefault(name, {}))

    def QueryValueEx(self, key, name):
        if name not in key.data:
            raise FileNotFoundError(name)
        return key.data[name], self.REG_SZ

    def SetValueEx(self, key, name, _reserved, _tipo, value):
        key.data[name] = value

    def DeleteValue(self, key, name):
        if name not in key.data:
            raise FileNotFoundError(name)
        del key.data[name]


class AutostartTests(unittest.TestCase):
    def test_command_line_variants(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(
            os.environ, {"APPIMAGE": ""}
        ), mock.patch.object(sys, "frozen", False, create=True):
            linha = autostart.command_line()
            self.assertTrue(linha.endswith('run.py" --minimized'))
            self.assertIn("run.py", linha)
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(
            os.environ, {"APPIMAGE": "/opt/Gaspar.AppImage"}
        ):
            self.assertEqual(autostart.command_line(), '"/opt/Gaspar.AppImage" --minimized')
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(
            os.environ, {"APPIMAGE": ""}
        ), mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual(
                autostart.command_line(), f'"{sys.executable}" --minimized'
            )
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            sys, "frozen", True, create=True
        ):
            self.assertEqual(
                autostart.command_line(), f'"{sys.executable}" --minimized'
            )

    def test_linux_enable_disable_cycle(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            sys, "platform", "linux"
        ), mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}):
            self.assertFalse(autostart.is_enabled())
            self.assertIsNone(autostart.enable())
            target = Path(tmp) / "autostart" / "gaspar.desktop"
            texto = target.read_text(encoding="utf-8")
            self.assertIn("X-GNOME-Autostart-enabled=true", texto)
            self.assertIn("--minimized", texto)
            self.assertTrue(autostart.is_enabled())
            self.assertIsNone(autostart.disable())
            self.assertFalse(autostart.is_enabled())
            self.assertIsNone(autostart.disable())

    def test_linux_enable_reports_write_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bloqueio = Path(tmp) / "arquivo"
            bloqueio.write_text("x", encoding="utf-8")
            with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(
                os.environ, {"XDG_CONFIG_HOME": str(bloqueio)}
            ):
                erro = autostart.enable()
            self.assertIn("autostart", erro)

    def test_windows_registry_cycle(self):
        fake = FakeWinreg()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            sys, "platform", "win32"
        ), mock.patch.dict(sys.modules, {"winreg": fake}), mock.patch.dict(
            os.environ, {"XDG_CONFIG_HOME": tmp}
        ):
            self.assertFalse(autostart.is_enabled())
            self.assertIsNone(autostart.enable())
            self.assertTrue(autostart.is_enabled())
            self.assertIn(autostart.VALUE_NAME, fake.values[autostart.RUN_KEY])
            self.assertIsNone(autostart.disable())
            self.assertFalse(autostart.is_enabled())
            self.assertIsNone(autostart.disable())


class FakeWindll:
    def __init__(self, shell_result: int = 42, erro: Exception | None = None):
        self.shell32 = types.SimpleNamespace(ShellExecuteW=self.shell_execute)
        self._result = shell_result
        self._erro = erro

    def shell_execute(self, *_args):
        if self._erro:
            raise self._erro
        return self._result


class ActivityTests(unittest.TestCase):
    def test_unsupported_platform_has_no_detection(self):
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertIsNone(activity.idle_seconds())
            self.assertFalse(activity.fullscreen_app_active())

    def test_linux_without_display_is_safe(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(
            os.environ, {"DISPLAY": ""}
        ):
            self.assertIsNone(activity.idle_seconds())
            self.assertFalse(activity.fullscreen_app_active())

    def test_windows_dispatch(self):
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            activity, "_windows_idle", return_value=7.5
        ), mock.patch.object(activity, "_windows_fullscreen", return_value=True):
            self.assertEqual(activity.idle_seconds(), 7.5)
            self.assertTrue(activity.fullscreen_app_active())

    def test_windows_api_failure_is_silent(self):
        with mock.patch.object(activity.ctypes, "windll", FakeWindll(erro=RuntimeError("x")), create=True):
            self.assertIsNone(activity._windows_idle())
            self.assertFalse(activity._windows_fullscreen())


class BlackBoxElevationTests(unittest.TestCase):
    def test_linux_without_pkexec_refuses(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(
            sys, "frozen", False, create=True
        ), mock.patch.dict(os.environ, {"APPIMAGE": ""}), mock.patch.object(
            blackbox.shutil, "which", return_value=None
        ):
            self.assertFalse(blackbox._relaunch_elevated())

    def test_linux_uses_pkexec_with_module(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(
            sys, "frozen", False, create=True
        ), mock.patch.dict(os.environ, {"APPIMAGE": ""}), mock.patch.object(
            blackbox.shutil, "which", return_value="/usr/bin/pkexec"
        ), mock.patch.object(blackbox.subprocess, "Popen") as popen:
            self.assertTrue(blackbox._relaunch_elevated())
            comando = popen.call_args.args[0]
            self.assertEqual(comando[0], "pkexec")
            self.assertIn("-m", comando)
            self.assertIn("gaspar.blackbox", comando)

    def test_linux_appimage_runs_itself(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(
            os.environ, {"APPIMAGE": "/opt/Gaspar.AppImage"}
        ), mock.patch.object(blackbox.shutil, "which", return_value="/usr/bin/pkexec"), mock.patch.object(
            blackbox.subprocess, "Popen"
        ) as popen:
            self.assertTrue(blackbox._relaunch_elevated())
            self.assertEqual(popen.call_args.args[0], ["pkexec", "/opt/Gaspar.AppImage"])

    def test_windows_shell_execute_paths(self):
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            sys, "frozen", True, create=True
        ), mock.patch.object(ctypes, "windll", FakeWindll(42), create=True):
            self.assertTrue(blackbox._relaunch_elevated())
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            sys, "frozen", True, create=True
        ), mock.patch.object(ctypes, "windll", FakeWindll(0), create=True):
            self.assertFalse(blackbox._relaunch_elevated())
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            sys, "frozen", True, create=True
        ), mock.patch.object(
            ctypes, "windll", FakeWindll(erro=RuntimeError("negado")), create=True
        ):
            self.assertFalse(blackbox._relaunch_elevated())


class AppEntryTests(unittest.TestCase):
    def test_version_flag_does_not_open_a_window(self):
        from gaspar import __version__, app

        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.assertEqual(app.main(["--version"]), 0)
        self.assertIn(__version__, saida.getvalue())

    def test_dpi_awareness_is_noop_outside_windows(self):
        from gaspar import app

        with mock.patch.object(sys, "platform", "linux"):
            self.assertIsNone(app.enable_dpi_awareness())


class OverlayHelpersTests(unittest.TestCase):
    def test_bitmap_bytes_matches_side_and_mask(self):
        opaca = Image.new("RGBA", (220, 220), (0, 0, 0, 255))
        dados = GasparOverlay._bitmap_bytes(opaca)
        self.assertEqual(len(dados), 220 * ((220 + 7) // 8))
        self.assertEqual(dados.count(0xFF), 220 * 27)
        self.assertTrue(set(dados) <= {0xFF, 0x0F})
        vazia = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
        self.assertEqual(set(GasparOverlay._bitmap_bytes(vazia)), {0})

    def test_corner_positions_stay_inside_the_screen(self):
        overlay = object.__new__(GasparOverlay)
        overlay._screen_width = 1920
        overlay._screen_height = 1080
        cantos = overlay._corner_positions()
        self.assertEqual(len(cantos), 4)
        self.assertEqual(cantos[0], (18, 18))
        for x, y in cantos:
            self.assertGreaterEqual(x, 18)
            self.assertGreaterEqual(y, 18)
            self.assertLessEqual(x, 1920 - 220 - 18)
            self.assertLessEqual(y, 1080 - 220 - 64)

    def test_alpha_is_clamped_and_effective(self):
        overlay = object.__new__(GasparOverlay)
        overlay._dimmed = False
        overlay.win = types.SimpleNamespace(attributes=lambda *args: None)
        with mock.patch.object(sys, "platform", "linux"):
            overlay._set_alpha(0.1)
            self.assertEqual(overlay._opacity, 0.40)
            overlay._set_alpha(2)
            self.assertEqual(overlay._opacity, 1.0)
        overlay._dimmed = True
        self.assertLess(overlay._effective_alpha(), 0.4)
        overlay._dimmed = False
        self.assertEqual(overlay._effective_alpha(), 1.0)

    def test_visibility_and_bob(self):
        overlay = object.__new__(GasparOverlay)
        overlay._visible = False
        self.assertFalse(overlay.is_visible)
        overlay._visible = True
        self.assertTrue(overlay.is_visible)
        self.assertEqual(GasparOverlay._bob(0.0), 0)
        for instante in range(0, 100):
            self.assertIn(GasparOverlay._bob(instante / 10), (-3, -2, -1, 0, 1, 2, 3))

    def test_begin_travel_only_moves_to_a_neighbour(self):
        overlay = object.__new__(GasparOverlay)
        overlay._positions = [(0, 0), (10, 0), (10, 10), (0, 10)]
        overlay._current_index = 0
        overlay._current = (0, 0)
        with mock.patch("gaspar.overlay.random.choice", return_value=1), mock.patch(
            "gaspar.overlay.random.uniform", return_value=9.0
        ):
            overlay._begin_travel(100.0)
        self.assertEqual(overlay._current_index, 1)
        self.assertEqual(overlay._travel_to, (10, 0))
        self.assertEqual(overlay._travel_start, 100.0)
        self.assertEqual(overlay._travel_duration, 9.0)


if __name__ == "__main__":
    unittest.main()
