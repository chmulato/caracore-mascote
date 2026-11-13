"""Painel do Gaspar: constroi a janela de verdade, escondida, com dados temporarios.

Os testes de tela pulam quando nao ha display (a esteira Linux roda sob xvfb).
Nada aqui abre porta fixa, toca no hosts real ou inicia a bandeja de verdade.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gaspar import app as app_module
from gaspar import updates

TEM_TELA = bool(os.environ.get("DISPLAY")) or sys.platform in ("win32", "darwin")


class FakeOverlay:
    instances: list["FakeOverlay"] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.visible = False
        self.panel_visible = None
        self.opacity = None
        self.pause_fullscreen = None
        self.destroyed = False
        FakeOverlay.instances.append(self)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def set_panel_visible(self, visible):
        self.panel_visible = visible

    def set_opacity(self, value):
        self.opacity = value

    def set_pause_fullscreen(self, value):
        self.pause_fullscreen = value

    def destroy(self):
        self.destroyed = True

    @property
    def is_visible(self):
        return self.visible


class FakeEngine:
    def __init__(self, running=False):
        self.is_running = running
        self.cycles = 0
        self.remaining = None
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1
        self.is_running = True

    def stop(self):
        self.stopped += 1
        self.is_running = False

    def seconds_remaining(self):
        return self.remaining


class FakeTray:
    def __init__(self):
        self.notifications = []
        self.menu_updates = 0
        self.stopped = 0

    def notify(self, message, title):
        self.notifications.append((message, title))

    def update_menu(self):
        self.menu_updates += 1

    def stop(self):
        self.stopped += 1


class FakeSmsConfig:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.api_token = "token-fake"
        self.http_port = 8788
        self.audit_retention_days = 90
        self.last_diagnostic_at = 0.0
        self.last_diagnostic_sms_ok = False
        self.last_diagnostic_battery_ok = False
        self.saved = 0
        self.rotated = 0

    def save(self):
        self.saved += 1

    def rotate_api_token(self):
        self.rotated += 1
        self.api_token = "token-rotacionado"

    def setup_payload(self, host):
        return f"gaspar://{host}"


class FakeStore:
    def __init__(self):
        self.jobs = []

    def recent(self, limit=10):
        return self.jobs[:limit]


class FakeBridge:
    def __init__(self):
        self.base_url = ""
        self.started = 0
        self.stopped = 0
        self.erased = 0
        self.phone_result = {"found": True, "host": "192.168.0.9"}
        self.enqueue_error = None
        self.phone_online = False
        self.phone_host = ""
        self.counts = {"fila": 1, "enviado": 2, "entregue": 3, "falhou": 0}
        self.e2e = {"required": False}
        self.store = FakeStore()

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1

    def refresh_phone(self):
        return self.phone_result

    def enqueue(self, number, message, manual=False):
        if self.enqueue_error is not None:
            raise self.enqueue_error
        return SimpleNamespace(id="abcdef1234567890")

    def erase_history(self):
        self.erased += 1

    def stats(self):
        return {
            "phone": {"online": self.phone_online, "host": self.phone_host},
            "counts": self.counts,
            "e2e": self.e2e,
        }


def servidor_falso(erro: Exception | None = None):
    class Servidor:
        instancias: list["Servidor"] = []

        def __init__(self, bridge, config, on_diagnostic=None, on_log=None):
            self.port = 8788
            self.stopped = 0
            self.on_diagnostic = on_diagnostic
            self.on_log = on_log
            Servidor.instancias.append(self)
            if erro is not None:
                raise erro

        def start(self):
            pass

        def stop(self):
            self.stopped += 1

    return Servidor


@unittest.skipUnless(TEM_TELA, "Tk precisa de tela (no Linux a esteira usa xvfb)")
class PainelBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._destruir)

        ambiente = mock.patch.dict(
            os.environ, {"GASPAR_HOME": str(Path(self.tmp.name) / "dados")}
        )
        ambiente.start()
        self.addCleanup(ambiente.stop)

        autostart = mock.patch.object(app_module.autostart, "is_enabled", return_value=False)
        autostart.start()
        self.addCleanup(autostart.stop)

        FakeOverlay.instances.clear()
        self.overlay_patch = mock.patch.object(app_module, "GasparOverlay", FakeOverlay)
        self.overlay_patch.start()
        self.addCleanup(self.overlay_patch.stop)

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = app_module.GasparApp(self.root)
        self._cancelar_timers()

    def _destruir(self):
        try:
            self.app.closing = True
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _cancelar_timers(self):
        for job in self.root.tk.call("after", "info"):
            try:
                self.root.after_cancel(job)
            except Exception:
                pass

    def reconstruir(self, overlay_cls=FakeOverlay, start_minimized=False):
        self.app.closing = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        if overlay_cls is not FakeOverlay:
            self.overlay_patch.stop()
            self.overlay_patch = mock.patch.object(app_module, "GasparOverlay", overlay_cls)
            self.overlay_patch.start()
            self.addCleanup(self.overlay_patch.stop)
        else:
            FakeOverlay.instances.clear()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = app_module.GasparApp(self.root, start_minimized=start_minimized)
        self._cancelar_timers()
        return self.app

    def pump(self):
        self.root.update()

    def arquivo_config(self) -> dict:
        alvo = Path(os.environ["GASPAR_HOME"]) / "config.json"
        return json.loads(alvo.read_text(encoding="utf-8"))

    def abrir_painel_sms(self):
        self.app.open_sms_panel()
        self.pump()
        self.app._sms_window.withdraw()
        return self.app._sms_window


class ConstrucaoTests(PainelBase):
    def test_painel_monta_com_os_valores_salvos(self):
        self.assertIn("Gaspar", self.root.title())
        self.assertEqual(self.app.interval_var.get(), "300")
        self.assertEqual(self.app.key_var.get(), "F15")
        self.assertTrue(self.app.var_mouse.get())
        self.assertTrue(self.app.var_idle.get())
        self.assertTrue(self.app.var_fullscreen.get())
        self.assertFalse(self.app.var_startup.get())
        self.assertIsNotNone(self.app._logo)

    def test_sobreposicao_nasce_ligada_e_botao_avisa(self):
        self.assertEqual(len(FakeOverlay.instances), 1)
        sobreposicao = FakeOverlay.instances[0]
        self.assertEqual(sobreposicao.kwargs["opacity"], 0.82)
        self.assertTrue(sobreposicao.kwargs["pause_fullscreen"])
        self.assertTrue(sobreposicao.visible)
        self.assertTrue(sobreposicao.panel_visible)
        self.assertEqual(self.app.overlay_button.cget("text"), "Tirar o Gaspar da tela")
        self.assertEqual(self.app.action_button.cget("text"), "Ativar")

    def test_aviso_de_atualizacao_comeca_escondido(self):
        self.assertEqual(self.app.update_frame.winfo_manager(), "")
        self.assertEqual(self.app.update_text_var.get(), "")

    def test_log_inicial_fica_na_reserva_antes_da_janela_de_logs(self):
        self.assertTrue(any("Aplicacao iniciada." in linha for linha in self.app._events_backlog))

    def test_falha_ao_criar_sobreposicao_desliga_o_recurso(self):
        class SobreposicaoQuebrada(FakeOverlay):
            def __init__(self, *args, **kwargs):
                raise RuntimeError("sem janela")

        app = self.reconstruir(overlay_cls=SobreposicaoQuebrada)
        self.assertFalse(app.settings.overlay)
        self.assertFalse(app.var_overlay.get())
        self.assertEqual(app.overlay_button.cget("text"), "Trazer o Gaspar de volta")
        self.assertTrue(any("Nao foi possivel criar o Gaspar flutuante" in l for l in app._system_backlog))


class IntervaloTests(PainelBase):
    def test_intervalo_valido_e_salvo(self):
        self.app.interval_var.set("90")
        self.assertTrue(self.app._commit_interval(focus=True))
        self.assertEqual(self.app.settings.interval, 90)
        self.assertEqual(self.arquivo_config()["interval"], 90)

    def test_intervalo_fora_da_faixa_e_ajustado(self):
        self.app.interval_var.set("5")
        self.assertTrue(self.app._commit_interval())
        self.assertEqual(self.app.interval_var.get(), "10")
        self.app.interval_var.set("99999")
        self.assertTrue(self.app._commit_interval())
        self.assertEqual(self.app.interval_var.get(), "3600")

    def test_intervalo_invalido_avisa_e_restaura(self):
        self.app.interval_var.set("abc")
        with mock.patch.object(app_module.messagebox, "showwarning") as aviso:
            self.assertFalse(self.app._commit_interval())
        aviso.assert_called_once()
        self.assertEqual(self.app.interval_var.get(), "300")

    def test_falha_ao_salvar_fica_no_log(self):
        with mock.patch.object(app_module, "save_settings", side_effect=OSError("disco cheio")):
            self.app._persist()
        self.assertTrue(any("Nao foi possivel salvar as preferencias" in l for l in self.app._system_backlog))


class OpcoesTests(PainelBase):
    def test_chaves_ligam_e_desligam_e_persistem(self):
        self.app.var_mouse.set(False)
        self.app._on_mouse_toggle()
        self.assertFalse(self.app.settings.simulate_mouse)
        self.assertFalse(self.arquivo_config()["simulate_mouse"])

        self.app.var_sound.set(True)
        self.app._on_sound_toggle()
        self.assertTrue(self.arquivo_config()["sound"])

        self.app.var_keep.set(False)
        self.app._on_keep_toggle()
        self.assertFalse(self.arquivo_config()["keep_teams"])

        self.app.var_idle.set(False)
        self.app._on_idle_toggle()
        self.assertFalse(self.arquivo_config()["only_when_idle"])

    def test_telemetria_e_inicio_automatico(self):
        self.app.var_system.set(True)
        self.app._on_system_toggle()
        self.assertTrue(self.arquivo_config()["system_telemetry"])
        self.app.var_auto.set(False)
        self.app._on_auto_toggle()
        self.assertFalse(self.arquivo_config()["auto_start"])

    def test_pausa_em_tela_cheia_avisa_a_sobreposicao(self):
        self.app.var_fullscreen.set(False)
        self.app._on_fullscreen_toggle()
        self.assertFalse(self.app.settings.pause_fullscreen)
        self.assertFalse(FakeOverlay.instances[0].pause_fullscreen)

    def test_tecla_de_atividade(self):
        self.app.key_var.set("Espaço")
        self.app._on_key_change()
        self.assertEqual(self.app.settings.press_key, "space")
        self.assertEqual(self.arquivo_config()["press_key"], "space")
        self.app.key_var.set("desconhecida")
        self.app._on_key_change()
        self.assertEqual(self.app.settings.press_key, "shift")

    def test_iniciar_com_o_sistema_liga_e_desliga(self):
        with mock.patch.object(app_module.autostart, "enable", return_value="") as ligar:
            self.app.var_startup.set(True)
            self.app._on_startup_toggle()
        ligar.assert_called_once()
        with mock.patch.object(app_module.autostart, "disable", return_value="") as desligar:
            self.app.var_startup.set(False)
            self.app._on_startup_toggle()
        desligar.assert_called_once()

    def test_iniciar_com_o_sistema_com_erro_desfaz_a_marca(self):
        self.app.var_startup.set(True)
        with mock.patch.object(app_module.autostart, "enable", return_value="sem permissao"):
            with mock.patch.object(app_module.messagebox, "showerror") as erro:
                self.app._on_startup_toggle()
        erro.assert_called_once()
        self.assertFalse(self.app.var_startup.get())

    def test_opacidade_ajusta_a_sobreposicao(self):
        self.app._on_opacity_change("60")
        self.assertEqual(self.app.opacity_label.cget("text"), "60%")
        self.assertAlmostEqual(FakeOverlay.instances[0].opacity, 0.60)
        self.app._on_opacity_change("20")
        self.assertEqual(self.app.opacity_label.cget("text"), "50%")
        self.app._persist_opacity()
        self.assertIsNone(self.app._opacity_job)
        self.assertEqual(self.arquivo_config()["opacity"], 50)

    def test_opacidade_invalida_nao_muda_nada(self):
        antes = self.app.settings.opacity
        self.app._on_opacity_change("texto")
        self.assertEqual(self.app.settings.opacity, antes)


class SobreposicaoTests(PainelBase):
    def test_tirar_e_trazer_a_sobreposicao(self):
        sobreposicao = FakeOverlay.instances[0]
        self.app.set_overlay(False)
        self.assertFalse(self.app.settings.overlay)
        self.assertFalse(sobreposicao.visible)
        self.assertEqual(self.app.overlay_button.cget("text"), "Trazer o Gaspar de volta")
        self.app.toggle_overlay()
        self.assertTrue(self.app.settings.overlay)
        self.assertTrue(sobreposicao.visible)
        self.assertTrue(self.app.overlay_visible)

    def test_pedir_o_mesmo_estado_nao_faz_nada(self):
        antes = len(self.app._events_backlog)
        self.app.set_overlay(True)
        self.assertEqual(len(self.app._events_backlog), antes)


class SimulacaoTests(PainelBase):
    def setUp(self):
        super().setUp()
        self.engine = FakeEngine()
        self.app.engine = self.engine

    def test_ativar_e_desativar(self):
        self.engine.remaining = 42
        self.app.toggle_simulation()
        self.assertEqual(self.engine.started, 1)
        self.assertEqual(self.app.sim_var.get(), "Ativa")
        self.assertEqual(self.app.next_var.get(), "42s")
        self.assertEqual(self.app.action_button.cget("text"), "Desativar")
        self.engine.remaining = None
        self.app.toggle_simulation()
        self.assertEqual(self.engine.stopped, 1)
        self.assertEqual(self.app.sim_var.get(), "Parada")
        self.assertEqual(self.app.next_var.get(), "-")

    def test_intervalo_invalido_nao_inicia(self):
        self.app.interval_var.set("abc")
        with mock.patch.object(app_module.messagebox, "showwarning"):
            self.app.toggle_simulation()
        self.assertEqual(self.engine.started, 0)

    def test_sem_acao_escolhida_avisa(self):
        self.app.settings.simulate_mouse = False
        self.app.settings.press_key = "none"
        self.app.settings.keep_teams = False
        self.app.var_mouse.set(False)
        self.app.var_keep.set(False)
        with mock.patch.object(app_module.messagebox, "showwarning") as aviso:
            self.app.toggle_simulation()
        aviso.assert_called_once()
        self.assertEqual(self.engine.started, 0)

    def test_inicio_automatico_so_com_a_opcao_ligada(self):
        self.app.settings.auto_start = False
        self.app._maybe_auto_start()
        self.assertEqual(self.engine.started, 0)
        self.app.settings.auto_start = True
        self.app._maybe_auto_start()
        self.assertEqual(self.engine.started, 1)
        self.app.closing = True
        self.app._maybe_auto_start()
        self.assertEqual(self.engine.started, 1)

    def test_relogio_esconde_o_painel_da_sobreposicao(self):
        self.app._panel_visible = True
        self.app._tick()
        self.assertFalse(FakeOverlay.instances[0].panel_visible)
        self._cancelar_timers()


class CelularSmsTests(PainelBase):
    def setUp(self):
        super().setUp()
        self.janela = self.abrir_painel_sms()

    def usar_fakes(self, enabled=True):
        self.app.sms_config = FakeSmsConfig(enabled=enabled)
        self.app.sms_bridge = FakeBridge()
        return self.app.sms_config, self.app.sms_bridge

    def test_janela_abre_e_reaproveita(self):
        primeira = self.app._sms_window
        self.assertTrue(primeira.winfo_exists())
        self.app.open_sms_panel()
        self.pump()
        self.assertIs(self.app._sms_window, primeira)
        self.app._close_sms_window()
        self.assertIsNone(self.app._sms_window)
        self.app._close_sms_window()

    def test_sem_configuracao_mostra_ponte_desligada(self):
        self.app._refresh_sms_ui()
        self.app._update_sms_api()
        self.assertEqual(self.app.sms_api_var.get(), "Ponte desligada")
        self.assertEqual(self.app._sms_api_url(), "http://127.0.0.1:0")

    def test_texto_vazio_avisa_que_nao_ha_envios(self):
        self.app.sms_text.configure(state=tk.NORMAL)
        self.app._set_sms_text([])
        self.assertIn("Nenhum envio registrado.", self.app.sms_text.get("1.0", "end"))

    def test_servidor_e_ponte_sobem_e_descem(self):
        config, bridge = self.usar_fakes()
        Servidor = servidor_falso()
        with mock.patch.object(app_module, "SmsHttpServer", Servidor), mock.patch.object(
            app_module, "lan_ip", return_value="192.168.0.5"
        ):
            self.app._start_sms_services()
        self.assertIsNotNone(self.app.sms_server)
        self.assertEqual(bridge.started, 1)
        self.assertEqual(bridge.base_url, "http://192.168.0.5:8788")
        self.assertEqual(self.app.sms_token_var.get(), "token-fake")
        self.assertIn("/api/sms", self.app.sms_api_var.get())
        self.assertTrue(any("Servidor local de SMS ativo na porta 8788" in l for l in self.app._events_backlog))

        self.app._stop_sms_services()
        self.assertIsNone(self.app.sms_server)
        self.assertEqual(bridge.stopped, 1)
        self.assertEqual(bridge.base_url, "")
        self.assertEqual(self.app.sms_api_var.get(), "Servidor local desligado")

    def test_porta_ocupada_avisa_sem_derrubar_o_painel(self):
        config, bridge = self.usar_fakes()
        Servidor = servidor_falso(erro=OSError("porta ocupada"))
        with mock.patch.object(app_module, "SmsHttpServer", Servidor):
            self.app._start_sms_services()
        self.assertIsNone(self.app.sms_server)
        self.assertTrue(any("Nao foi possivel abrir a porta 8788" in l for l in self.app._system_backlog))

    def test_liga_e_desliga_a_ponte(self):
        config, bridge = self.usar_fakes(enabled=False)
        self.app.sms_enabled_var.set(True)
        Servidor = servidor_falso()
        with mock.patch.object(app_module, "SmsHttpServer", Servidor), mock.patch.object(
            app_module, "lan_ip", return_value="127.0.0.1"
        ):
            self.app._on_sms_enabled()
        self.assertTrue(config.enabled)
        self.assertEqual(config.saved, 1)
        self.assertEqual(bridge.started, 1)
        self.assertTrue(any("Ponte de SMS ligada." in l for l in self.app._events_backlog))

        self.app.sms_enabled_var.set(False)
        self.app._on_sms_enabled()
        self.assertFalse(config.enabled)
        self.assertEqual(bridge.stopped, 1)
        self.assertTrue(any("Ponte de SMS desligada." in l for l in self.app._events_backlog))

    def test_procurar_celular_encontra_e_nao_encontra(self):
        _, bridge = self.usar_fakes()
        with mock.patch.object(self.app, "_refresh_sms_ui"):
            self.app._find_phone_worker()
            self.pump()
            self.assertIn("192.168.0.9", self.app.sms_status_var.get())

            bridge.phone_result = {"found": False}
            self.app._find_phone_worker()
            self.pump()
            self.assertIn("nao encontrado", self.app.sms_status_var.get())

            with mock.patch.object(bridge, "refresh_phone", side_effect=RuntimeError("rede")):
                self.app._find_phone_worker()
            self.pump()
            self.assertIn("nao encontrado", self.app.sms_status_var.get())

    def test_procurar_sem_ponte_avisa(self):
        with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
            self.app._on_find_phone()
        aviso.assert_called_once()
        self.usar_fakes(enabled=False)
        with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
            self.app._on_find_phone()
        aviso.assert_called_once()

    def test_pareamento_exige_servidor(self):
        with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
            self.app._on_show_qr()
        aviso.assert_called_once()

    def test_qr_pareia_e_fecha(self):
        self.usar_fakes()
        self.app.sms_server = SimpleNamespace(port=8788)
        self.app._on_show_qr()
        self.pump()
        self.app._sms_qr_window.withdraw()
        self.assertIsNotNone(self.app._sms_qr_window)
        self.assertIsNotNone(self.app._sms_qr_photo)
        self.assertTrue(any("QR de pareamento exibido." in l for l in self.app._events_backlog))
        primeira = self.app._sms_qr_window
        self.app._on_show_qr()
        self.pump()
        self.assertIs(self.app._sms_qr_window, primeira)
        self.app._close_qr_window()
        self.assertIsNone(self.app._sms_qr_window)

    def test_qr_com_erro_mostra_texto_no_lugar_da_imagem(self):
        self.usar_fakes()
        self.app.sms_server = SimpleNamespace(port=8788)
        with mock.patch.object(app_module, "make_qr", side_effect=RuntimeError("sem qrcode")):
            self.app._on_show_qr()
            self.pump()
        self.assertIn("Nao foi possivel gerar o QR", self.app._sms_qr_image_label.cget("text"))

    def test_envio_de_teste(self):
        config, bridge = self.usar_fakes()
        self.app.sms_number_var.set("11999999999")
        with mock.patch.object(bridge, "enqueue", return_value=SimpleNamespace(id="abcdef1234567890")) as enfileirar:
            self.app._on_test_send()
        enfileirar.assert_called_once_with("11999999999", self.app.sms_message_var.get(), manual=True)
        self.assertTrue(any("Teste de SMS enfileirado (abcdef12)" in l for l in self.app._events_backlog))

        bridge.enqueue_error = app_module.InvalidMessage("numero invalido")
        with mock.patch.object(app_module.messagebox, "showwarning") as aviso:
            self.app._on_test_send()
        aviso.assert_called_once()

        bridge.enqueue_error = RuntimeError("inesperado")
        with mock.patch.object(app_module.messagebox, "showerror") as erro:
            self.app._on_test_send()
        erro.assert_called_once()

    def test_envio_sem_ponte_ou_desligada_avisa(self):
        with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
            self.app._on_test_send()
        aviso.assert_called_once()
        self.usar_fakes(enabled=False)
        with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
            self.app._on_test_send()
        aviso.assert_called_once()

    def test_apagar_historico_pede_confirmacao(self):
        _, bridge = self.usar_fakes()
        with mock.patch.object(app_module.messagebox, "askyesno", return_value=False):
            self.app._on_sms_erase()
        self.assertEqual(bridge.erased, 0)
        with mock.patch.object(app_module.messagebox, "askyesno", return_value=True):
            self.app._on_sms_erase()
        self.assertEqual(bridge.erased, 1)
        self.assertEqual(self.app._sms_signature, ())

    def test_copiar_e_rotacionar_token(self):
        config, _ = self.usar_fakes()
        self.app._on_copy_token()
        self.assertEqual(self.root.clipboard_get(), "token-fake")
        self.app._on_rotate_token()
        self.assertEqual(config.rotated, 1)
        self.assertEqual(self.app.sms_token_var.get(), "token-rotacionado")
        self.assertTrue(any("Novo token da API gerado" in l for l in self.app._events_backlog))

    def test_copiar_token_com_falha_avisa(self):
        self.usar_fakes()
        with mock.patch.object(self.root, "clipboard_clear", side_effect=tk.TclError("sem area")):
            with mock.patch.object(app_module.messagebox, "showerror") as erro:
                self.app._on_copy_token()
        erro.assert_called_once()

    def test_status_da_ponte_por_estado(self):
        config, bridge = self.usar_fakes()
        self.app._refresh_sms_ui()
        self.assertEqual(self.app.sms_status_var.get(), "Celular ainda nao pareado")
        self.assertIn("fila 1", self.app.sms_detail_var.get())

        config.enabled = False
        self.app._refresh_sms_ui()
        self.assertEqual(self.app.sms_status_var.get(), "Ponte de SMS desligada")

        config.enabled = True
        bridge.phone_online = True
        bridge.phone_host = "192.168.0.9"
        self.app._refresh_sms_ui()
        self.assertIn("Celular conectado", self.app.sms_status_var.get())

        bridge.phone_online = False
        self.app._refresh_sms_ui()
        self.assertIn("sem resposta recente", self.app.sms_status_var.get())

    def test_detalhe_mostra_diagnostico_e_cifra(self):
        config, bridge = self.usar_fakes()
        config.last_diagnostic_at = 1_700_000_000
        config.last_diagnostic_sms_ok = True
        config.last_diagnostic_battery_ok = False
        bridge.e2e = {"required": True, "phone_key": "chave", "fingerprint": "1234567890"}
        self.app._refresh_sms_ui()
        detalhe = self.app.sms_detail_var.get()
        self.assertIn("pareado", detalhe)
        self.assertIn("SMS ok", detalhe)
        self.assertIn("bateria otimizada", detalhe)
        self.assertIn("cifrado ponta a ponta (12345678)", detalhe)
        bridge.e2e = {"required": True, "phone_key": ""}
        self.app._refresh_sms_ui()
        self.assertIn("sem chave do celular", self.app.sms_detail_var.get())

    def test_lista_de_envios_so_reescreve_quando_muda(self):
        _, bridge = self.usar_fakes()
        bridge.store.jobs = [
            SimpleNamespace(id="1", status="entregue", updated_at=1_700_000_000, confirmed=True, recipient_tag="abc12345", template="venda", actor=""),
            SimpleNamespace(id="2", status="falhou", updated_at=1_700_000_100, confirmed=False, recipient_tag="", template="", actor="manual"),
            SimpleNamespace(id="3", status="enviado", updated_at=1_700_000_200, confirmed=True, recipient_tag="def", template="", actor=""),
        ]
        with mock.patch.object(self.app, "_set_sms_text") as escrever:
            self.app._refresh_sms_ui()
            self.app._refresh_sms_ui()
        escrever.assert_called_once()
        linhas = escrever.call_args.args[0]
        self.assertEqual(len(linhas), 3)
        self.assertIn("ok", linhas[0])
        self.assertIn("abc12345", linhas[0])
        self.assertIn("!", linhas[1])
        self.assertIn("+", linhas[2])

    def test_diagnostico_do_celular_pareado(self):
        self.usar_fakes()
        self.app._on_sms_diagnostic({"sms_ok": True, "battery_ok": True})
        self.pump()
        self.assertTrue(any("Celular pareado: SMS ok; bateria ok." in l for l in self.app._events_backlog))
        self.app._on_sms_log("fila andou")
        self.assertTrue(any("SMS: fila andou" in l for l in self.app._events_backlog))

    def test_relogio_do_sms_para_ao_fechar(self):
        self.app.closing = True
        self.app._sms_tick()
        self.assertIsNone(self.app._sms_poll_job)
        self.app.closing = False
        with mock.patch.object(self.app, "_refresh_sms_ui") as atualizar:
            self.app._sms_tick()
        atualizar.assert_called_once()
        self.assertIsNotNone(self.app._sms_poll_job)
        self._cancelar_timers()

    def test_construcao_inicial_com_ponte_desligada(self):
        config = FakeSmsConfig(enabled=False)
        with mock.patch.object(app_module, "load_sms_config", return_value=config):
            self.app._init_sms()
        self.assertIsNotNone(self.app.sms_config)
        self.assertIsNotNone(self.app.sms_bridge)
        self.assertIsNone(self.app.sms_server)
        self.assertIsNotNone(self.app._sms_poll_job)
        self._cancelar_timers()

    def test_construcao_inicial_com_erro_avisa(self):
        with mock.patch.object(app_module, "load_sms_config", side_effect=RuntimeError("config quebrada")):
            self.app._init_sms()
        self.assertTrue(any("Ponte de SMS indisponivel: config quebrada" in l for l in self.app._system_backlog))

    def test_janela_avisa_quando_a_ponte_nao_esta_disponivel(self):
        with mock.patch.object(app_module, "SMS_AVAILABLE", False), mock.patch.object(
            app_module, "SMS_IMPORT_ERROR", "sem modulo"
        ):
            self.app._build_sms_window(tk.Toplevel(self.root))
        self.assertIn("indisponivel", self.app.sms_status_var.get())
        self.assertIn("sem modulo", self.app.sms_detail_var.get())


class AtualizacaoTests(PainelBase):
    def info(self, **campos):
        base = dict(
            versao="1.8.0",
            mandatory=False,
            url="https://exemplo/Gaspar-1.8.0.exe",
            sha256="a" * 64,
            tamanho=100,
            notas="Correcoes.",
            notes_url="https://exemplo/notas",
            publicado_em="2026-11-12T10:00:00Z",
        )
        base.update(campos)
        return updates.Disponivel(**base)

    def estado(self) -> dict:
        return updates.carregar_estado()

    def test_mostrar_opcional_abre_o_aviso(self):
        self.app.mostrar_atualizacao(self.info())
        self.assertIsNotNone(self.app.update_info)
        self.assertEqual(self.app.update_frame.winfo_manager(), "pack")
        self.assertIn("1.8.0 disponivel", self.app.update_text_var.get())
        self.assertEqual(str(self.app.update_skip_button.cget("state")), str(tk.NORMAL))
        self.assertTrue(any("Atualizacao 1.8.0 disponivel (opcional)" in l for l in self.app._events_backlog))

    def test_mostrar_obrigatoria_bloqueia_o_pular(self):
        self.app.mostrar_atualizacao(self.info(mandatory=True))
        self.assertIn("necessaria", self.app.update_text_var.get())
        self.assertEqual(str(self.app.update_skip_button.cget("state")), str(tk.DISABLED))
        self.assertTrue(any("(obrigatoria)" in l for l in self.app._events_backlog))

    def test_versao_pulada_nao_volta(self):
        updates.salvar_estado(skipped_version="1.8.0")
        self.app.mostrar_atualizacao(self.info())
        self.assertIsNone(self.app.update_info)
        self.assertEqual(self.app.update_frame.winfo_manager(), "")

    def test_versao_adiada_fica_guardada_sem_aviso(self):
        updates.salvar_estado(deferred_version="1.8.0")
        self.app.mostrar_atualizacao(self.info())
        self.assertIsNotNone(self.app.update_info)
        self.assertEqual(self.app.update_frame.winfo_manager(), "")

    def test_bandeja_avisa_uma_vez_so(self):
        bandeja = FakeTray()
        self.app.tray_icon = bandeja
        info = self.info()
        self.app._notificar_atualizacao(info)
        self.app._notificar_atualizacao(info)
        self.assertEqual(len(bandeja.notifications), 1)
        self.assertEqual(self.estado()["notified_version"], "1.8.0")
        self.assertGreaterEqual(bandeja.menu_updates, 1)

    def test_sem_bandeja_nao_grava_aviso(self):
        self.app._notificar_atualizacao(self.info())
        self.assertNotIn("notified_version", self.estado())

    def test_botao_da_bandeja_abre_o_painel(self):
        self.app.mostrar_atualizacao(self.info())
        self.app.show_update()
        self.assertEqual(self.app.update_frame.winfo_manager(), "pack")

    def test_ver_novidades(self):
        self.app.mostrar_atualizacao(self.info())
        with mock.patch.object(app_module.updates, "abrir_pagina", return_value=True) as abrir:
            self.app._on_update_notes()
        abrir.assert_called_once_with("https://exemplo/notas")
        self.assertTrue(any("Pagina de novidades da versao 1.8.0 aberta" in l for l in self.app._events_backlog))

    def test_depois_guarda_a_versao_e_esconde_o_aviso(self):
        self.app.mostrar_atualizacao(self.info())
        self.app._on_update_later()
        self.assertEqual(self.estado()["deferred_version"], "1.8.0")
        self.assertEqual(self.app.update_frame.winfo_manager(), "")

    def test_pular_versao(self):
        self.app.mostrar_atualizacao(self.info())
        self.app._on_update_skip()
        self.assertEqual(self.estado()["skipped_version"], "1.8.0")
        self.assertIsNone(self.app.update_info)
        self.assertTrue(any("Atualizacao 1.8.0 pulada" in l for l in self.app._events_backlog))

    def test_obrigatoria_nao_pode_ser_pulada(self):
        self.app.mostrar_atualizacao(self.info(mandatory=True))
        self.app._on_update_skip()
        self.assertEqual(self.app.update_info.versao, "1.8.0")
        self.assertNotIn("skipped_version", self.estado())

    def test_fora_do_windows_o_botao_abre_o_download(self):
        with mock.patch("sys.platform", "linux"), mock.patch.object(
            app_module.updates, "abrir_pagina", return_value=True
        ) as abrir:
            self.app.mostrar_atualizacao(self.info())
            self.app._on_update_now()
        abrir.assert_called_once_with("https://exemplo/notas")
        self.assertEqual(self.app.update_now_button.cget("text"), "Abrir download")

    def test_fora_do_windows_com_pagina_indisponivel_mostra_o_endereco(self):
        self.app.mostrar_atualizacao(self.info(notes_url=""))
        with mock.patch("sys.platform", "linux"), mock.patch.object(
            app_module.updates, "abrir_pagina", return_value=False
        ):
            self.app._on_update_now()
        self.assertIn("https://exemplo/Gaspar-1.8.0.exe", self.app.update_status_var.get())

    def test_no_windows_baixa_em_segundo_plano(self):
        self.app.mostrar_atualizacao(self.info())
        with mock.patch("sys.platform", "win32"), mock.patch.object(
            self.app, "_baixar_atualizacao"
        ) as baixar:
            self.app._on_update_now()
            self.app._update_worker.join(timeout=2)
        baixar.assert_called_once()
        self.assertIn("Baixando", self.app.update_status_var.get())

    def test_nao_dispara_dois_downloads(self):
        self.app.mostrar_atualizacao(self.info())
        self.app._update_worker = mock.Mock(is_alive=lambda: True)
        with mock.patch.object(self.app, "_baixar_atualizacao") as baixar:
            self.app._on_update_now()
        baixar.assert_not_called()

    def test_download_concluido_entrega_ao_instalador(self):
        info = self.info()
        self.app.mostrar_atualizacao(info)
        instalador = Path(self.tmp.name) / "Gaspar-1.8.0.exe"
        with mock.patch.object(app_module.updates, "baixar_instalador", return_value=instalador), mock.patch.object(
            app_module.updates, "aplicar_windows"
        ) as aplicar:
            self.app._baixar_atualizacao(info)
            self.pump()
        aplicar.assert_called_once()
        self.assertEqual(self.estado()["pending_version"], "1.8.0")
        self.assertTrue(self.app.closing)
        self.assertTrue(any("Instalacao da versao 1.8.0 iniciada" in l for l in self.app._events_backlog))

    def test_download_com_falha_avisa_e_libera_os_botoes(self):
        info = self.info()
        self.app.mostrar_atualizacao(info)
        with mock.patch.object(
            app_module.updates, "baixar_instalador", side_effect=updates.FalhaAtualizacao("SHA-256 do pacote nao confere")
        ):
            self.app._baixar_atualizacao(info)
            self.pump()
        self.assertIn("SHA-256 do pacote nao confere", self.app.update_status_var.get())
        self.assertEqual(str(self.app.update_now_button.cget("state")), str(tk.NORMAL))

    def test_erro_inesperado_no_download(self):
        info = self.info()
        self.app.mostrar_atualizacao(info)
        with mock.patch.object(app_module.updates, "baixar_instalador", side_effect=RuntimeError("disco")):
            self.app._baixar_atualizacao(info)
            self.pump()
        self.assertIn("erro inesperado (RuntimeError)", self.app.update_status_var.get())

    def test_instalar_recusa_versao_diferente(self):
        self.app.mostrar_atualizacao(self.info())
        with mock.patch.object(app_module.updates, "aplicar_windows") as aplicar:
            self.app._aplicar_atualizacao(Path("x.exe"), self.info(versao="1.9.0"))
        aplicar.assert_not_called()
        self.assertNotIn("pending_version", self.estado())

    def test_instalador_que_nao_inicia_avisa(self):
        info = self.info()
        self.app.mostrar_atualizacao(info)
        with mock.patch.object(app_module.updates, "aplicar_windows", side_effect=OSError("sem permissao")):
            self.app._aplicar_atualizacao(Path("x.exe"), info)
        self.assertIn("nao foi possivel iniciar o instalador", self.app.update_status_var.get())

    def test_botoes_ocupados_respeitam_a_obrigatoriedade(self):
        self.app.mostrar_atualizacao(self.info(mandatory=True))
        self.app._update_busy(True)
        self.assertEqual(str(self.app.update_skip_button.cget("state")), str(tk.DISABLED))
        self.app.mostrar_atualizacao(self.info())
        self.app._update_busy(False)
        self.assertEqual(str(self.app.update_skip_button.cget("state")), str(tk.NORMAL))

    def test_resultado_da_instalacao_aparece_ao_abrir(self):
        updates.salvar_estado(pending_version="1.8.0")
        alvo = updates.estado_path().with_name("update-result.txt")
        alvo.write_text("version=1.8.0\ncode=0\n", encoding="ascii")
        with mock.patch.object(app_module.updates, "chave_publica", return_value=None):
            self.app._init_updates()
        self.assertTrue(any("Atualizacao para 1.8.0 concluida." in l for l in self.app._events_backlog))
        self.assertEqual(self.estado().get("pending_version"), "")

    def test_instalacao_com_codigo_de_erro_fica_no_log(self):
        alvo = updates.estado_path().with_name("update-result.txt")
        alvo.write_text("version=1.8.0\ncode=5\n", encoding="ascii")
        with mock.patch.object(app_module.updates, "chave_publica", return_value=None):
            self.app._init_updates()
        self.assertTrue(any("nao concluiu (codigo 5)" in l for l in self.app._system_backlog))

    def test_canal_desativado_sem_chave(self):
        with mock.patch.object(app_module.updates, "chave_publica", return_value=None):
            self.app._init_updates()
        self.assertTrue(any("chave publica ausente" in l for l in self.app._system_backlog))

    def test_vigia_comeca_quando_ha_chave(self):
        vigia = mock.Mock()
        with mock.patch.object(app_module.updates, "chave_publica", return_value=object()), mock.patch.object(
            app_module.updates, "Vigia", return_value=vigia
        ):
            self.app._init_updates()
        vigia.iniciar.assert_called_once()
        self.assertIs(self.app._update_vigia, vigia)


class JanelasTests(PainelBase):
    def test_logs_abrem_com_a_reserva_e_recebem_novas_linhas(self):
        self.app.log_event("linha antiga")
        self.app.open_logs()
        self.pump()
        self.app._logs_window.withdraw()
        self.assertIn("linha antiga", self.app.events_text.get("1.0", "end"))
        self.app.log_event("linha nova")
        self.pump()
        self.assertIn("linha nova", self.app.events_text.get("1.0", "end"))
        janela = self.app._logs_window
        self.app.open_logs()
        self.pump()
        self.assertIs(self.app._logs_window, janela)
        self.app._close_logs_window()
        self.assertIsNone(self.app._logs_window)
        self.assertIsNone(self.app.events_text)

    def test_reserva_de_log_e_limitada(self):
        reserva = []
        for indice in range(501):
            self.app._remember(reserva, f"l{indice}")
        self.assertEqual(len(reserva), 401)
        self.assertEqual(reserva[0], "l100")


class JanelasLogLongoTests(PainelBase):
    def test_log_longo_apaga_o_comeco(self):
        self.app.open_logs()
        self.app._logs_window.withdraw()
        texto = self.app.events_text
        texto.configure(state=tk.NORMAL)
        texto.insert("1.0", "\n".join(f"l{i}" for i in range(2000)) + "\n")
        texto.configure(state=tk.DISABLED)
        self.app._append(texto, "ultima")
        linhas = int(texto.index("end-1c").split(".")[0])
        self.assertLess(linhas, 2001)
        self.assertIn("ultima", texto.get("1.0", "end"))

    def test_ocultar_e_mostrar_o_painel(self):
        self.app.hide_window()
        self.assertFalse(self.app._panel_visible)
        self.assertFalse(FakeOverlay.instances[0].panel_visible)
        self.assertTrue(any("Painel minimizado." in l for l in self.app._events_backlog))
        self.app.show_panel()
        self.assertTrue(self.app._panel_visible)
        self.assertTrue(FakeOverlay.instances[0].panel_visible)

    def test_ocultar_na_bandeja(self):
        self.app.tray_icon = FakeTray()
        self.app.hide_window()
        self.assertTrue(any("Painel oculto na bandeja" in l for l in self.app._events_backlog))

    def test_abrir_pasta_de_dados(self):
        with mock.patch("sys.platform", "linux"), mock.patch.object(app_module.subprocess, "Popen") as popen:
            self.app._open_data_folder()
        self.assertEqual(popen.call_args.args[0][0], "xdg-open")

    def test_pasta_de_dados_com_erro_avisa(self):
        with mock.patch("sys.platform", "linux"), mock.patch.object(
            app_module.subprocess, "Popen", side_effect=OSError("sem gerenciador")
        ):
            with mock.patch.object(app_module.messagebox, "showerror") as erro:
                self.app._open_data_folder()
        erro.assert_called_once()

    def test_blackbox_em_desenvolvimento(self):
        with mock.patch.object(app_module.subprocess, "Popen") as popen:
            self.app.open_blackbox()
        self.assertEqual(popen.call_args.args[0], [sys.executable, "-m", "gaspar.blackbox"])

    def test_blackbox_empacotado_sem_executavel_avisa(self):
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
            sys, "executable", str(Path(self.tmp.name) / "Gaspar.exe")
        ):
            with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
                self.app.open_blackbox()
        aviso.assert_called_once()

    def test_blackbox_empacotado_abre_o_executavel_vizinho(self):
        base = Path(self.tmp.name) / "instalado"
        base.mkdir()
        alvo = base / "gaspar_blackbox.exe"
        alvo.write_bytes(b"x")
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
            sys, "executable", str(base / "Gaspar.exe")
        ), mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            app_module.subprocess, "Popen"
        ) as popen:
            self.app.open_blackbox()
        self.assertEqual(popen.call_args.args[0], [str(alvo)])
        self.assertEqual(popen.call_args.kwargs["cwd"], str(base))

    def test_bandeja_indisponivel_fica_no_log(self):
        with mock.patch.object(app_module, "create_tray", return_value=(None, "sem pystray")):
            self.app._init_tray()
        self.assertTrue(any("Bandeja do sistema indisponivel: sem pystray" in l for l in self.app._system_backlog))

    def test_abrir_minimizado_com_bandeja_esconde(self):
        self.app.start_minimized = True
        with mock.patch.object(app_module, "create_tray", return_value=(FakeTray(), None)):
            self.app._init_tray()
        self.assertEqual(self.root.state(), "withdrawn")

    def test_abrir_minimizado_sem_bandeja_mostra(self):
        self.app.start_minimized = True
        with mock.patch.object(app_module, "create_tray", return_value=(None, "sem pystray")):
            self.app._init_tray()
        self.assertIn(self.root.state(), ("normal", "zoomed"))
        self.app.hide_window()

    def test_ui_respeita_o_fechamento(self):
        chamada = mock.Mock()
        self.app.ui(chamada, 1, 2)
        self.pump()
        chamada.assert_called_once_with(1, 2)
        self.app.closing = True
        self.app.ui(chamada, 3)
        self.pump()
        chamada.assert_called_once_with(1, 2)

    def test_sinal_sonoro_nao_quebra(self):
        self.app._bell()
        self.pump()

    def test_sair_encerra_tudo_e_salva(self):
        self.app.engine = FakeEngine(running=True)
        sobreposicao = FakeOverlay.instances[0]
        bandeja = FakeTray()
        self.app.tray_icon = bandeja
        self.app._update_vigia = mock.Mock()
        self.app.sms_bridge = FakeBridge()
        self.app.sms_server = SimpleNamespace(stop=mock.Mock())
        self.app.quit()
        self.assertTrue(self.app.closing)
        self.assertEqual(self.app.engine.stopped, 1)
        self.assertTrue(sobreposicao.destroyed)
        self.assertEqual(bandeja.stopped, 1)
        self.app._update_vigia.parar.assert_called_once()
        self.assertEqual(self.app.sms_bridge.stopped, 1)
        self.assertTrue(self.arquivo_config())
        self.app.quit()


if __name__ == "__main__":
    unittest.main()
