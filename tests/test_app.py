"""Painel do Gaspar: constroi a janela de verdade, escondida, com dados temporarios.

Os testes de tela pulam quando nao ha display (a esteira Linux roda sob xvfb).
Nada aqui abre porta fixa, toca no hosts real ou inicia a bandeja de verdade.
"""

from __future__ import annotations

import gc
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
from gaspar.messaging.config import MessagingConfig
from gaspar.messaging.transport import Health
from gaspar.messaging.transports.android_lan import NOME_MOTORISTA as MEIO_CELULAR
from gaspar.messaging.transports.factory import construir
from gaspar.messaging.transports.smtp_email import EmailBridgeDriver
from gaspar.messaging.vault import KEY_FILENAME as MESSAGING_KEY_FILENAME, Vault
from gaspar.paths import data_dir

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
        self.enviados: list[tuple[str, str, bool]] = []
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
        self.enviados.append((number, message, manual))
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

        def __init__(
            self,
            bridge,
            config,
            on_diagnostic=None,
            on_log=None,
            on_receipt=None,
            send_blocker=None,
        ):
            self.port = 8788
            self.stopped = 0
            self.iniciado = 0
            self.on_diagnostic = on_diagnostic
            self.on_log = on_log
            self.on_receipt = on_receipt
            self.send_blocker = send_blocker
            Servidor.instancias.append(self)
            if erro is not None:
                raise erro

        def start(self):
            self.iniciado += 1

        def stop(self):
            self.stopped += 1

    return Servidor


class ServicoMensagensFalso:
    """Imita ``MessagingService`` sem fila e sem porta: so conta os passos.

    O cofre e o registro entram de mentira mas funcionando, porque a tela do lojista
    (Onda B6-6) pergunta a saude por origem, sela senha com o cofre e reusa o
    motorista vivo na hora de conferir o acesso.
    """

    criados: list["ServicoMensagensFalso"] = []

    def __init__(self, config=None):
        self.config = config if config is not None else MessagingConfig(enabled=True)
        self.iniciado = 0
        self.fechado = 0
        self.abriu_porta = None
        self.port = 8767
        self.comprovantes: list[str] = []
        self.registry = RegistroFalso()
        self.vault = Vault.load_or_create(data_dir() / MESSAGING_KEY_FILENAME)

    @classmethod
    def from_config(cls, path=None, **kwargs):
        objeto = cls()
        cls.criados.append(objeto)
        return objeto

    def start(self, *, open_port=None, start_round=True):
        self.abriu_porta = open_port
        self.iniciado += 1
        return bool(self.config.enabled)

    def registrar_comprovante(self, corpo: object) -> bool:
        """A porta da 1.7 chama com o recibo cifrado; quem decide e a fila 2.0."""
        self.comprovantes.append(str(corpo))
        return bool(corpo)

    def close(self):
        self.fechado += 1


class RegistroFalso:
    """O que a tela sabe perguntar ao motor: quem esta vivo e como cada origem esta."""

    def __init__(self, motoristas=(), saude=None):
        self._motoristas = list(motoristas)
        self._saude = dict(saude or {})

    def drivers(self):
        return list(self._motoristas)

    def health_for(self, origem: str) -> Health:
        return self._saude.get(origem, Health(False, "o canal escolhido ainda nao respondeu"))


class MotoristaSonda:
    """Motorista que so sabe fazer a prova de acesso, sem rede nenhuma por traz."""

    def __init__(self, nome: str, saude: Health | None = None, erro: Exception | None = None):
        self.name = nome
        self.saude = saude if saude is not None else Health(True, "", "sonda")
        self.erro = erro
        self.chamadas = 0

    def testar_acesso(self) -> Health:
        self.chamadas += 1
        if self.erro is not None:
            raise self.erro
        return self.saude


class ExecucaoDireta:
    """Thread de mentira: roda o trabalho na hora, para o teste nao esperar agulha."""

    def __init__(self, target=None, args=(), **_kw):
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)

    def join(self, timeout=None) -> None:
        return None


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
        # As janelas proprias do painel (Celular/SMS, QR, ajustes, registro) morrem
        # com o Tk vivo, e o coletor de lixo passa aqui antes do root.destroy():
        # variaveis e imagens huercas acordam depois da destruicao e derrubam o
        # interpretador Tcl no meio da suite (medido em Windows).
        try:
            for filha in self.root.winfo_children():
                filha.destroy()
            # larga o app antes de recolher: as variaveis e imagens que ele segura
            # tem de morrer com o Tk vivo, nao depois do root.destroy()
            self.app = None
            gc.collect()
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
        self.assertEqual(self.app.key_var.get(), "Nenhuma")
        self.assertFalse(self.app.var_mouse.get())
        self.assertFalse(self.app.var_keep.get())
        self.assertFalse(self.app.var_auto.get())
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
        self.app.settings.press_key = "f15"

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

    def test_pedido_de_teste_nao_enfileira_com_o_celular_cedido(self):
        """O botão da 1.7 obedece à reserva: enfileirar no motorista parado diria "enviado" à toa.

        Amarra três pontas ao mesmo tempo: o pedido de teste não chega ao bridge, o
        aviso diz o motivo e onde desligar a barra, e o log registra a recusa.
        """
        _, bridge = self.usar_fakes()
        self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.assertTrue(self.app._motivo_celular_reservado(), "a reserva tem de estar de pé no teste")
        with mock.patch.object(app_module.messagebox, "showwarning") as aviso:
            self.app._on_test_send()
        self.assertEqual([], bridge.enviados)
        self.assertFalse(any("enfileirado" in l for l in self.app._events_backlog))
        texto = aviso.call_args[0][1]
        self.assertIn("barra 2.0", texto)
        self.assertIn("Mensagens pelo computador", texto, "o aviso aponta o quadro onde desligar")
        self.assertTrue(
            any("Teste de SMS" in linha and "nao enviado" in linha for linha in self.app._events_backlog)
        )

    def test_pedido_de_teste_livre_quando_o_celular_nesta_fora_do_meio(self):
        """A reserva só morde com o celular pelo Wi-Fi: escolhendo o e-mail, a 1.7 segue de pé.

        A outra metade da regra, medida no mesmo fake que registra o enqueue: sem
        reserva o teste passa por aqui exatamente como passava antes da barra 2.0.
        """
        _, bridge = self.usar_fakes()
        self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        self.assertEqual("", self.app._motivo_celular_reservado())
        self.app.sms_number_var.set("11999999999")
        with mock.patch.object(app_module.messagebox, "showwarning") as aviso:
            self.app._on_test_send()
        aviso.assert_not_called()
        self.assertEqual([("11999999999", self.app.sms_message_var.get(), True)], bridge.enviados)
        self.assertTrue(any("Teste de SMS enfileirado" in l for l in self.app._events_backlog))

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


class BarraMensagens20Tests(PainelBase):
    """O painel so liga a barra 2.0 quando o arquivo manda - e ai o celular e dela.

    A regra de convivencia (Onda B6-A, decisao do dono em 21/11/2026): com
    ``messaging.enabled`` verdadeiro e alguma origem escolhendo ``android_lan``, a
    ponte de SMS da 1.7 cede a porta 49998. Com o motor desligado - o padrao - a 1.7
    faz exatamente o que sempre fez.
    """

    def setUp(self):
        super().setUp()
        ServicoMensagensFalso.criados = []
        self.abrir_painel_sms()

    def usar_ponte(self, enabled=True):
        self.app.sms_config = FakeSmsConfig(enabled=enabled)
        self.app.sms_bridge = FakeBridge()
        return self.app.sms_config, self.app.sms_bridge

    def ligar_o_motor(self, config):
        """Rel o arquivo e liga, com o servico falso contando os passos."""
        with mock.patch.object(app_module, "load_messaging_config", return_value=config), mock.patch.object(
            app_module, "MessagingService", ServicoMensagensFalso
        ):
            self.app._init_messaging()
        return self.app.messaging_service

    def subir_a_1_7(self):
        Servidor = servidor_falso()
        with mock.patch.object(app_module, "SmsHttpServer", Servidor), mock.patch.object(
            app_module, "lan_ip", return_value="192.168.0.5"
        ):
            self.app._start_sms_services()

    def test_sem_arquivo_da_barra_o_gaspar_continua_a_17(self):
        self.app._init_messaging()
        self.assertIsNotNone(self.app.messaging_config)
        self.assertFalse(self.app.messaging_config.enabled)
        self.assertIsNone(self.app.messaging_service)
        self.assertEqual("", self.app._motivo_celular_reservado())

    def test_motor_desligado_no_arquivo_nem_constroi_o_servico(self):
        servico = self.ligar_o_motor(MessagingConfig(enabled=False, transports={"PDV": MEIO_CELULAR}))
        self.assertIsNone(servico)
        self.assertEqual([], ServicoMensagensFalso.criados)

    def test_motor_ligado_no_arquivo_sobe_a_barra(self):
        servico = self.ligar_o_motor(MessagingConfig(enabled=True))
        self.assertIsNotNone(servico)
        self.assertEqual(1, servico.iniciado)
        self.assertIs(servico, self.app.messaging_service)

    def test_arquivo_quebrado_avisa_sem_derrubar_o_painel(self):
        with mock.patch.object(app_module, "load_messaging_config", side_effect=RuntimeError("config quebrada")):
            self.app._init_messaging()
        self.assertIsNone(self.app.messaging_service)
        self.assertTrue(
            any("Barra de mensagens indisponivel: config quebrada" in l for l in self.app._system_backlog)
        )

    def test_dependencia_ausente_do_motor_avisa_e_nao_tenta_nada(self):
        with mock.patch.object(app_module, "MESSAGING_AVAILABLE", False), mock.patch.object(
            app_module, "MESSAGING_IMPORT_ERROR", "sem modulo"
        ):
            self.app._init_messaging()
            self.assertEqual("", self.app._motivo_celular_reservado())
        self.assertTrue(
            any("Barra de mensagens indisponivel: sem modulo" in l for l in self.app._system_backlog)
        )

    def test_motor_desligado_deixa_a_ponte_1_7_usar_o_celular(self):
        _, ponte = self.usar_ponte()
        self.app.messaging_config = MessagingConfig(enabled=False, transports={"PDV": MEIO_CELULAR})
        self.subir_a_1_7()
        self.assertEqual(1, ponte.started)
        self.assertIsNotNone(self.app.sms_server)
        self.assertIn("/api/sms", self.app.sms_api_var.get())

    def test_meio_de_email_nao_tira_o_celular_da_ponte_1_7(self):
        _, ponte = self.usar_ponte()
        self.app.messaging_config = MessagingConfig(
            enabled=True, transports={"PDV": EmailBridgeDriver.name, "HUB": EmailBridgeDriver.name}
        )
        self.subir_a_1_7()
        self.assertEqual(1, ponte.started)
        self.assertIsNotNone(self.app.sms_server)

    def test_motor_no_celular_segura_a_49998_e_a_1_7_cede(self):
        _, ponte = self.usar_ponte()
        self.app.messaging_config = MessagingConfig(enabled=True, transports={"HUB": MEIO_CELULAR})
        self.subir_a_1_7()
        self.assertEqual(0, ponte.started)
        self.assertTrue(any("cede a porta 49998" in l for l in self.app._events_backlog))
        self.assertIn("cede a porta 49998", self.app.sms_api_var.get())
        self.assertIn("HUB", self.app.sms_api_var.get())

    def test_a_porta_do_comprovante_fica_de_pe_com_o_celular_cedido(self):
        """Ceder o celular nao e fechar a porta: e pela 8766 que o recibo volta para casa."""
        _, ponte = self.usar_ponte()
        self.app.messaging_config = MessagingConfig(enabled=True, transports={"HUB": MEIO_CELULAR})
        self.subir_a_1_7()
        self.assertEqual(0, ponte.started)
        self.assertIsNotNone(self.app.sms_server)
        self.assertEqual(1, self.app.sms_server.iniciado)
        self.assertIsNotNone(self.app.sms_server.send_blocker)
        self.assertIsNone(
            self.app.sms_server.on_receipt, "sem barra 2.0 subida, ainda nao ha para quem entregar"
        )

    def test_a_volta_do_celular_entregue_pelo_painel_chega_na_barra_2_0(self):
        _, ponte = self.usar_ponte()
        self.subir_a_1_7()
        with mock.patch.object(app_module, "MessagingService", ServicoMensagensFalso):
            self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": MEIO_CELULAR})
            self.app._start_messaging()
        self.app.sms_server.on_receipt("RECIBO-CIFRADO")
        self.assertEqual(["RECIBO-CIFRADO"], self.app.messaging_service.comprovantes)

    def test_a_reserva_aponta_o_produto_para_o_contrato_local(self):
        self.usar_ponte()
        self.subir_a_1_7()
        self.assertEqual("", self.app._motivo_de_envio_cedido())
        with mock.patch.object(app_module, "MessagingService", ServicoMensagensFalso):
            self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": MEIO_CELULAR})
            self.app._start_messaging()
        motivo = self.app._motivo_de_envio_cedido()
        self.assertIn("barra de mensagens 2.0", motivo)
        self.assertIn("http://127.0.0.1:8767/v2/messages", motivo)

    def test_o_token_do_pdv_continua_visivel_quando_a_1_7_cede_o_celular(self):
        self.usar_ponte()
        self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.subir_a_1_7()
        self.assertEqual("token-fake", self.app.sms_token_var.get())

    def test_motor_que_sobe_depois_pede_o_celular_de_volta(self):
        _, ponte = self.usar_ponte()
        self.subir_a_1_7()
        self.assertEqual(1, ponte.started)
        self.assertIsNotNone(self.app.sms_server)
        with mock.patch.object(app_module, "MessagingService", ServicoMensagensFalso):
            self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": MEIO_CELULAR})
            self.app._start_messaging()
        self.assertEqual(1, ponte.stopped)
        # a porta nao caiu: passou a encaminhar o recibo para a fila nova
        self.assertIsNotNone(self.app.sms_server)
        self.assertEqual(
            self.app.messaging_service.registrar_comprovante, self.app.sms_server.on_receipt
        )
        self.assertTrue(any("cede a porta 49998" in l for l in self.app._events_backlog))

    def test_ligar_a_ponte_no_painel_com_celular_reservado_avisa_o_lojista(self):
        config, ponte = self.usar_ponte(enabled=False)
        self.app.messaging_config = MessagingConfig(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.app.sms_enabled_var.set(True)
        Servidor = servidor_falso()
        with mock.patch.object(app_module, "SmsHttpServer", Servidor):
            self.app._on_sms_enabled()
        self.assertTrue(config.enabled)
        self.assertEqual(1, config.saved)
        self.assertEqual(0, ponte.started)
        self.assertEqual(1, len(Servidor.instancias))
        self.assertIsNotNone(self.app.sms_server)
        self.assertIsNotNone(self.app.sms_server.send_blocker)
        eventos = self.app._events_backlog
        self.assertTrue(any("Ponte de SMS ligada." in l for l in eventos))
        self.assertTrue(any("cede a porta 49998" in l for l in eventos))

    def test_fechar_a_barra_duas_vezes_nao_estoura(self):
        servico = self.ligar_o_motor(MessagingConfig(enabled=True))
        self.app._stop_messaging()
        self.app._stop_messaging()
        self.assertEqual(1, servico.fechado)
        self.assertIsNone(self.app.messaging_service)


class TelaDaBarraTests(PainelBase):
    """A tela do lojista na aba Celular / SMS (Onda B6-6): escolher, guardar, conferir.

    O que aqui se amarra: a tela repete o que o arquivo diz, troca um programa sem
    tocar no outro, nao finge que salvou quando o disco recusou, sela a senha antes
    de escrever e pergunta o acesso sem enviar nada a ninguem. Rede de verdade: zero.
    """

    def setUp(self):
        super().setUp()
        ServicoMensagensFalso.criados = []
        for patch in (
            mock.patch.object(app_module, "MessagingService", ServicoMensagensFalso),
            # o endereco da casa sai de um soquete de verdade: aqui e uma constante
            mock.patch.object(app_module, "lan_ip", return_value="192.168.0.5"),
            # nem a barra desligada deixa a 1.7 abrir porta dentro de um teste
            mock.patch.object(app_module, "SmsHttpServer", servidor_falso()),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.ponte = FakeBridge()
        self.app.sms_bridge = self.ponte
        self.app.sms_config = FakeSmsConfig(enabled=True)
        self.arquivo = data_dir() / "messaging.json"
        self.abrir_painel_sms()

    def gravar_e_ler(self, **corpo) -> MessagingConfig:
        """Escreve o arquivo da barra na pasta temporaria e faz o painel rele-lo."""
        dados = {"enabled": False, "transports": {}, "transport_settings": {}}
        dados.update(corpo)
        self.arquivo.write_text(json.dumps(dados), encoding="utf-8")
        self.app._init_messaging()
        return self.app.messaging_config

    def no_arquivo(self) -> dict:
        return json.loads(self.arquivo.read_text(encoding="utf-8"))

    def subir_a_1_7(self):
        self.app._start_sms_services()

    def abrir_ajustes(self) -> dict:
        self.app._open_meios_window()
        self.pump()
        return self.app._meio_campos

    def conferir_acesso(self) -> None:
        """Aperta o botao com a thread rodando na hora: o teste nao espera agulha."""
        with mock.patch.object(app_module, "threading", SimpleNamespace(Thread=ExecucaoDireta)):
            self.app._on_testar_acesso()
        self.pump()

    # ------------------------------------------------------------- o que a tela diz

    def test_a_tela_repete_o_que_o_arquivo_diz(self):
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.assertTrue(self.app.msg_enabled_var.get())
        self.assertEqual(app_module._rotulo_meio(MEIO_CELULAR), self.app.msg_meio_var["PDV"].get())
        self.assertEqual(app_module._rotulo_meio(""), self.app.msg_meio_var["HUB"].get())
        self.assertIn("CaraCore Hub nao envia mensagens", self.app.msg_status_var["HUB"].get())
        self.assertIn("ainda nao esta pronto", self.app.msg_status_var["PDV"].get())
        self.assertIn("a ponte antiga esta cedida", self.app.msg_status_var["PDV"].get())

    def test_a_barra_desligada_avisa_que_nada_sai(self):
        self.gravar_e_ler(enabled=False, transports={"PDV": MEIO_CELULAR})
        self.assertIn("a barra esta desligada, nada sai", self.app.msg_status_var["PDV"].get())
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        servico = self.app.messaging_service
        servico.registry = RegistroFalso(saude={"PDV": Health(True, "", "android-lan")})
        self.app._refresh_messaging_ui()
        self.assertIn("pronto para enviar - android-lan", self.app.msg_status_var["PDV"].get())

    def test_a_tela_nao_oferece_o_canal_que_nao_tem_codigo(self):
        self.assertEqual(
            ["", MEIO_CELULAR, "loopback", EmailBridgeDriver.name], app_module._canais_da_tela()
        )
        self.assertNotIn("usb_modem", app_module.MEIO_APELIDO)

    def test_o_canal_que_a_tela_nao_conhece_nao_e_reescrito(self):
        """Um nome tecnico no arquivo aparece sem maquiagem e sai intacto da troca."""
        self.gravar_e_ler(enabled=False, transports={"PDV": "usb_modem"})
        self.assertEqual("usb_modem", self.app.msg_meio_var["PDV"].get())
        self.app._on_meio_change("PDV")
        self.assertEqual({"PDV": "usb_modem"}, self.no_arquivo()["transports"])

    def test_escolher_o_canal_grava_e_nao_mexe_no_vizinho(self):
        config = self.gravar_e_ler(enabled=True, transports={"HUB": EmailBridgeDriver.name})
        self.app.msg_meio_var["PDV"].set(app_module._rotulo_meio(MEIO_CELULAR))
        self.app._on_meio_change("PDV")
        self.assertEqual(MEIO_CELULAR, config.transport_for("PDV"))
        self.assertEqual(EmailBridgeDriver.name, config.transport_for("HUB"))
        self.assertEqual(
            {"PDV": MEIO_CELULAR, "HUB": EmailBridgeDriver.name}, self.no_arquivo()["transports"]
        )
        eventos = self.app._events_backlog
        self.assertTrue(any("CaraCore PDV passa a enviar por Celular pela rede da loja" in l for l in eventos))

    def test_tirar_o_canal_de_um_programa_para_de_enviar_por_ele(self):
        config = self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR, "HUB": MEIO_CELULAR})
        self.app.msg_meio_var["PDV"].set(app_module._rotulo_meio(""))
        self.app._on_meio_change("PDV")
        self.assertEqual("", config.transport_for("PDV"))
        self.assertEqual({"HUB": MEIO_CELULAR}, self.no_arquivo()["transports"])
        self.assertIn("CaraCore PDV nao envia mensagens", self.app.msg_status_var["PDV"].get())
        # o celular continua reservado: ainda ha um programa usando-o
        self.assertIn("a ponte antiga esta cedida", self.app.msg_status_var["HUB"].get())

    def test_ligar_a_barra_pelo_painel_sobe_o_motor_e_grava(self):
        config = self.gravar_e_ler(enabled=False)
        self.app.msg_enabled_var.set(True)
        self.app._on_messaging_enabled()
        self.assertTrue(config.enabled)
        self.assertTrue(self.no_arquivo()["enabled"])
        self.assertIsNotNone(self.app.messaging_service)
        self.assertTrue(any("Barra de mensagens 2.0 ligada." in l for l in self.app._events_backlog))

    def test_desligar_a_barra_devolve_o_celular_a_ponte_1_7(self):
        self.subir_a_1_7()
        self.assertEqual(1, self.ponte.started)
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.assertEqual("", self.ponte.base_url, "com a barra em cima do celular, a 1.7 nao envia")
        motor = self.app.messaging_service
        self.app.msg_enabled_var.set(False)
        self.app._on_messaging_enabled()
        self.assertEqual(1, motor.fechado)
        self.assertIsNone(self.app.messaging_service)
        self.assertEqual(2, self.ponte.started, "a barra saiu de cima: o aparelho volta para a 1.7")
        self.assertIn("http://192.168.0.5:", self.ponte.base_url)
        self.assertFalse(self.no_arquivo()["enabled"])
        self.assertIsNone(self.app.sms_server.on_receipt, "a volta do celular voltou a ser da 1.7")

    def test_um_cambio_que_nao_e_o_celular_nao_reinicia_a_ponte_1_7(self):
        self.subir_a_1_7()
        self.gravar_e_ler(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        self.assertEqual(1, self.ponte.started, "a 1.7 ja estava de pe com o celular: ninguem a tocou")
        self.app.msg_meio_var["HUB"].set(app_module._rotulo_meio("loopback"))
        self.app._on_meio_change("HUB")
        self.assertEqual(1, self.ponte.started)

    def test_arquivo_que_nao_deixa_escrever_nao_finge_que_mudou(self):
        config = self.gravar_e_ler(enabled=False, transports={"PDV": MEIO_CELULAR})
        with mock.patch.object(MessagingConfig, "save", side_effect=OSError("disco cheio")):
            self.app.msg_enabled_var.set(True)
            self.app._on_messaging_enabled()
        self.assertFalse(config.enabled, "o que nao foi para o disco nao pode ficar na memoria")
        self.assertFalse(self.app.msg_enabled_var.get())
        self.assertIsNone(self.app.messaging_service)
        self.assertTrue(
            any("Nao foi possivel salvar a barra de mensagens" in l for l in self.app._system_backlog)
        )

    def test_troca_que_nao_consegue_salvar_volta_atras(self):
        config = self.gravar_e_ler(enabled=False, transports={"PDV": EmailBridgeDriver.name})
        self.app.msg_meio_var["PDV"].set(app_module._rotulo_meio(MEIO_CELULAR))
        with mock.patch.object(MessagingConfig, "save", side_effect=OSError("protegido")):
            self.app._on_meio_change("PDV")
        self.assertEqual(EmailBridgeDriver.name, config.transport_for("PDV"))
        self.assertEqual(
            app_module._rotulo_meio(EmailBridgeDriver.name), self.app.msg_meio_var["PDV"].get()
        )

    def test_a_janela_de_ajustes_que_nao_consegue_salvar_volta_atras(self):
        """O que o disco recusou não pode continuar na memória: a tela releria um canal salvo.

        A janela de ajustes tinha o rollback só na palavra. Aqui se amarra o bloco em
        memória, o que o log conta e o que fica na tela para o lojista tentar de novo.
        """
        config = self.gravar_e_ler(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        campos = self.abrir_ajustes()[EmailBridgeDriver.name]
        campos["smtp_host"].set("smtp.usado-agora.test.invalid")
        with mock.patch.object(MessagingConfig, "save", side_effect=OSError("disco cheio")):
            self.app._salvar_meios()
        self.assertEqual({}, config.settings_for(EmailBridgeDriver.name), "a memória voltou ao antes")
        self.assertNotIn(EmailBridgeDriver.name, config.transport_settings)
        self.assertIsNotNone(self.app._meios_window, "a janela fica aberta para tentar de novo")
        self.assertEqual("smtp.usado-agora.test.invalid", campos["smtp_host"].get())
        self.assertFalse(any("Ajustes dos canais salvos" in l for l in self.app._events_backlog))
        self.assertTrue(
            any("Nao foi possivel salvar a barra" in l for l in self.app._system_backlog),
            "a recusa do disco tem de aparecer no registro",
        )

    def test_a_janela_devolve_o_mapa_inteiro_sem_inventar_canal(self):
        """Depois de um disco que recusa, a memória é o mapa de antes, chave por chave.

        O rollback não pode deixar para trás o bloco de um canal que ninguém escolheu:
        a fábrica percorre os citados, e um bloco órfão na memória monta caixa postal
        que o arquivo nunca aprovou.
        """
        selo = self.app._cofre_da_barra().seal("senha-de-antes")
        antes = {
            EmailBridgeDriver.name: {"user": "loja@loja.test.invalid", "password_sealed": selo},
            MEIO_CELULAR: {"segredo_sealed": "abc", "descobrir": True},
        }
        config = self.gravar_e_ler(
            enabled=True,
            transports={"PDV": EmailBridgeDriver.name},
            transport_settings={nome: dict(bloco) for nome, bloco in antes.items()},
        )
        mapa_de_antes = {nome: dict(bloco) for nome, bloco in config.transport_settings.items()}
        campos = self.abrir_ajustes()[EmailBridgeDriver.name]
        campos["smtp_host"].set("smtp.usado-agora.test.invalid")
        with mock.patch.object(MessagingConfig, "save", side_effect=OSError("disco cheio")):
            self.app._salvar_meios()
        self.assertEqual(mapa_de_antes, config.transport_settings)
        self.assertEqual(antes[MEIO_CELULAR], config.settings_for(MEIO_CELULAR))

    # ------------------------------------------------------- ajustes e segredo selado

    def test_a_senha_digitada_vai_selada_para_o_arquivo(self):
        config = self.gravar_e_ler(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        campos = self.abrir_ajustes()[EmailBridgeDriver.name]
        self.assertEqual("", campos["password"].get(), "a senha nunca volta para a tela")
        campos["user"].set("loja@loja.test.invalid")
        campos["smtp_host"].set("smtp.test.invalid")
        campos["password"].set("senha-de-app-de-verdade")
        self.app._salvar_meios()
        bruto = self.arquivo.read_text(encoding="utf-8")
        self.assertNotIn("senha-de-app-de-verdade", bruto)
        bloco = json.loads(bruto)["transport_settings"][EmailBridgeDriver.name]
        cofre = self.app.messaging_service.vault
        self.assertEqual("senha-de-app-de-verdade", cofre.open(bloco["password_sealed"]))
        self.assertEqual("smtp.test.invalid", config.settings_for(EmailBridgeDriver.name)["smtp_host"])
        self.assertIsNone(self.app._meios_window, "salvar fecha a janela dos ajustes")

    def test_campo_em_branco_mantem_o_selo_e_o_arquivo_nao_perde_ajuste_fino(self):
        selo = self.app._cofre_da_barra().seal("senha-de-antes")
        guardado = {
            "enabled": True,
            "user": "loja@loja.test.invalid",
            "password_sealed": selo,
            "mailbox": "COMPRAS",
            "max_poll_messages": 7,
        }
        self.gravar_e_ler(
            enabled=True,
            transports={"PDV": EmailBridgeDriver.name},
            transport_settings={EmailBridgeDriver.name: dict(guardado)},
        )
        campos = self.abrir_ajustes()[EmailBridgeDriver.name]
        self.assertEqual("loja@loja.test.invalid", campos["user"].get())
        self.app._salvar_meios()
        bloco = self.no_arquivo()["transport_settings"][EmailBridgeDriver.name]
        self.assertEqual(selo, bloco["password_sealed"])
        self.assertEqual("COMPRAS", bloco["mailbox"], "o que a tela nao mostra nao e apagado")
        self.assertEqual(7, bloco["max_poll_messages"])

    def test_a_janela_nao_escreve_um_selo_vazio_para_o_campo_que_nunca_teve_senha(self):
        self.gravar_e_ler(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        self.abrir_ajustes()
        self.app._salvar_meios()
        bloco = self.no_arquivo()["transport_settings"][EmailBridgeDriver.name]
        self.assertNotIn("password_sealed", bloco)
        self.assertNotIn("bridge_key_sealed", bloco)

    def test_a_porta_em_branco_monta_o_canal_na_porta_do_motorista(self):
        """A janela escreve texto; o motorista converte. Porta em branco nao e porta quebrada."""
        self.gravar_e_ler(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        campos = self.abrir_ajustes()[EmailBridgeDriver.name]
        campos["user"].set("loja@loja.test.invalid")
        campos["smtp_host"].set("smtp.test.invalid")
        self.app._salvar_meios()
        bloco = self.no_arquivo()["transport_settings"][EmailBridgeDriver.name]
        self.assertEqual("", bloco["smtp_port"], "em branco vai para o arquivo como em branco")
        cofre = Vault.load_or_create(data_dir() / MESSAGING_KEY_FILENAME)
        motorista = construir(EmailBridgeDriver.name, bloco, vault=cofre, home=data_dir())
        self.assertEqual(465, motorista.settings.smtp_port)

    def test_a_janela_preserva_o_que_so_o_motorista_sabe_ler(self):
        """Os padroes gravados pela janela sao os do proprio canal, nao os de uma caixa."""
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.abrir_ajustes()
        self.app._salvar_meios()
        bloco = self.no_arquivo()["transport_settings"][MEIO_CELULAR]
        self.assertIs(True, bloco["descobrir"], "procurar o celular nasce ligado")
        self.assertIs(True, bloco["exigir_e2e"], "a exigencia de cifra nao se desliga sozinha")
        self.assertIs(False, bloco["ligada"])

    def test_a_janela_ajustes_reaproveita_a_que_ja_esta_aberta(self):
        self.gravar_e_ler(enabled=True)
        self.abrir_ajustes()
        primeira = self.app._meios_window
        self.abrir_ajustes()
        self.assertIs(primeira, self.app._meios_window)
        self.app._close_meios_window()
        self.assertIsNone(self.app._meios_window)
        self.assertEqual({}, self.app._meio_campos)

    def test_sem_cofre_nao_se_gruda_a_senha_e_nada_muda(self):
        config = self.gravar_e_ler(enabled=True, transports={"PDV": EmailBridgeDriver.name})
        campos = self.abrir_ajustes()[EmailBridgeDriver.name]
        campos["password"].set("senha-que-nao-tem-onde-guardar")
        self.app.messaging_service.vault = None
        with mock.patch.object(app_module.messagebox, "showerror") as erro:
            self.app._salvar_meios()
        self.assertIn("Nada foi alterado", erro.call_args[0][1])
        self.assertEqual({}, config.settings_for(EmailBridgeDriver.name))
        self.assertIsNotNone(self.app._meios_window, "a janela fica aberta para o lojista tentar de novo")

    # ------------------------------------------------------------- testar o acesso

    def test_a_tela_conferre_o_acesso_pelo_motorista_vivo(self):
        celular = MotoristaSonda(MEIO_CELULAR, Health(True, "", "192.168.0.9:49998"))
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR, "HUB": MEIO_CELULAR})
        self.app.messaging_service.registry = RegistroFalso([celular])
        self.conferir_acesso()
        self.assertEqual(2, celular.chamadas, "as duas origens compartilham o mesmo celular")
        self.assertIn("Ultimo teste de acesso", self.app.msg_verificado_var.get())
        self.assertIn("acesso conferido (192.168.0.9:49998)", self.app.msg_verificado_var.get())
        eventos = self.app._events_backlog
        self.assertTrue(any("Teste de acesso PDV (Celular pela rede da loja)" in l for l in eventos))
        self.assertTrue(any("Teste de acesso HUB" in l for l in eventos))

    def test_a_tela_diz_quem_nao_atendeu(self):
        celular = MotoristaSonda(MEIO_CELULAR, Health(False, "o celular nao atendeu em 192.168.0.50:49998"))
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.app.messaging_service.registry = RegistroFalso([celular])
        self.conferir_acesso()
        self.assertIn("sem acesso: o celular nao atendeu", self.app.msg_verificado_var.get())

    def test_a_sonda_que_estoura_nao_derruba_a_tela(self):
        celular = MotoristaSonda(MEIO_CELULAR, erro=RuntimeError("o motorista esqueceu um passo"))
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.app.messaging_service.registry = RegistroFalso([celular])
        self.conferir_acesso()
        self.assertIn("a verificacao nao terminou: o motorista esqueceu um passo", self.app.msg_verificado_var.get())

    def test_a_sonda_monta_o_canal_do_arquivo_sem_ligar_o_motor(self):
        self.gravar_e_ler(enabled=False, transports={"PDV": "loopback"})
        self.conferir_acesso()
        self.assertIn("Ensaio neste computador", self.app.msg_verificado_var.get())
        self.assertIn("acesso conferido", self.app.msg_verificado_var.get())
        self.assertIsNone(self.app.messaging_service, "conferir o acesso nao liga a barra")

    def test_o_canal_que_nao_monta_diz_o_motivo_em_vez_de_sumir(self):
        self.gravar_e_ler(enabled=False, transports={"PDV": "usb_modem"})
        self.conferir_acesso()
        self.assertIn("nao deu para preparar o canal com os ajustes salvos", self.app.msg_verificado_var.get())
        self.assertTrue(
            any("nao montou para o teste" in l for l in self.app._system_backlog),
            "o motivo tecnico fica no registro, nao na tela do lojista",
        )

    def test_sem_canal_escolhido_a_tela_pede_escolha_primeiro(self):
        self.gravar_e_ler(enabled=True)
        with mock.patch.object(app_module.messagebox, "showinfo") as aviso:
            self.conferir_acesso()
        self.assertIn("Escolha primeiro", aviso.call_args[0][1])
        self.assertEqual({}, self.app._msg_sondas, "nada foi perguntado a ninguem")

    def test_o_primeiro_acesso_conferido_nao_aparece_antes_de_existir(self):
        self.gravar_e_ler(enabled=True, transports={"PDV": MEIO_CELULAR})
        self.assertIn("Nenhum teste de acesso ainda", self.app.msg_verificado_var.get())


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
        barra = ServicoMensagensFalso(MessagingConfig(enabled=True))
        self.app.messaging_service = barra
        self.app.quit()
        self.assertTrue(self.app.closing)
        self.assertEqual(self.app.engine.stopped, 1)
        self.assertTrue(sobreposicao.destroyed)
        self.assertEqual(bandeja.stopped, 1)
        self.app._update_vigia.parar.assert_called_once()
        self.assertEqual(self.app.sms_bridge.stopped, 1)
        self.assertEqual(1, barra.fechado)
        self.assertIsNone(self.app.messaging_service)
        self.assertTrue(self.arquivo_config())
        self.app.quit()


if __name__ == "__main__":
    unittest.main()
