"""Fachada da barra de mensagens: cifra, fila, credenciais, meios e contrato local.

Quem liga o produto so precisa de ``MessagingService.from_config()`` e
``start()``. Com ``enabled`` falso - que e o padrao - nada de porta abre, nada de
ronda roda e o mascote segue igual a versao 1.7.
"""

from __future__ import annotations

import threading
from pathlib import Path

from gaspar.paths import data_dir
from gaspar.sms.audit import AuditLog

from .comprovantes import aplicar_comprovante
from .config import MessagingConfig, load_config
from .credentials import Credential, CredentialVault
from .dispatcher import Dispatcher
from .local_api import MessagingApi
from .model import ORIGENS
from .store import MessageStore
from .transports import TransportRegistry, UnknownTransport
from .transports.factory import montar_registry
from .vault import KEY_FILENAME, Vault

DB_FILENAME = "messaging.db"
AUDIT_FILENAME = "messaging_audit.jsonl"


class MessagingService:
    """Dono do ciclo de vida da barra de mensagens dentro do Gaspar."""

    def __init__(
        self,
        config: MessagingConfig | None = None,
        *,
        home: Path | str | None = None,
        registry: TransportRegistry | None = None,
        audit: AuditLog | None = None,
        on_log=None,
    ):
        self.config = config if config is not None else MessagingConfig()
        self.home = Path(home) if home is not None else data_dir()
        self.on_log = on_log
        self.vault = Vault.load_or_create(self.home / KEY_FILENAME)
        self.store = MessageStore(
            self.home / DB_FILENAME, self.vault, max_pending=self.config.max_pending
        )
        self.credentials = CredentialVault(self.store, self.vault)
        self._registry_injetado = registry is not None
        self.registry = registry if registry is not None else TransportRegistry()
        self.audit = audit if audit is not None else AuditLog(self.home / AUDIT_FILENAME)
        self.montar_meios()
        self.dispatcher = Dispatcher(
            self.store,
            self.registry,
            max_attempts=self.config.max_attempts,
            audit=self.audit,
            on_log=self._log,
        )
        self.api: MessagingApi | None = None
        self.uncertain_after_restart = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    # ------------------------------------------------------------- construcao

    @classmethod
    def from_config(cls, path: Path | str | None = None, **kwargs) -> "MessagingService":
        return cls(load_config(Path(path) if path is not None else None), **kwargs)

    # ------------------------------------------------------------ ciclo de vida

    def start(self, *, open_port: bool | None = None, start_round: bool = True) -> bool:
        """Liga a barra. Devolve False enquanto a configuracao mantiver tudo desligado.

        ``open_port`` decide se o contrato local abre ou nao.
        ``start_round`` desliga a ronda automatica, para quem prefere bombear os
        pedidos no proprio passo.
        """
        if self._running:
            return True
        if not self.config.enabled:
            self._log("barra de mensagens desligada na configuracao")
            return False
        self.uncertain_after_restart = self.store.reconcile_after_restart()
        if self.uncertain_after_restart:
            self._log(
                f"{self.uncertain_after_restart} envio(s) pararam no meio do caminho: "
                "ficam em duvida, nada foi reenviado"
            )
        self.montar_meios()
        self.bind_transports()
        if open_port is not False:
            self.api = MessagingApi(self)
            self.api.start()
            self._log(f"contrato local de mensagens ouvindo em {self.config.host}:{self.api.port}")
        if start_round:
            self._stop.clear()
            self._thread = threading.Thread(
                target=self.dispatcher.run_forever,
                args=(self._stop,),
                kwargs={"interval": self.config.poll_interval_seconds},
                name="gaspar-messaging-round",
                daemon=True,
            )
            self._thread.start()
        self._running = True
        return True

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        if self.api is not None:
            self.api.stop()
            self.api = None
        self._running = False

    def close(self) -> None:
        self.stop()
        self.registry.shutdown()
        self.store.close()

    # ---------------------------------------------------------------- apoio

    def montar_meios(self) -> list[str]:
        """Constroi os motoristas que a configuracao cita. Devolve os nomes montados.

        Com o motor desligado - o padrao de fabrica - nada se monta: nenhuma caixa
        postal e lida, nenhum celular e procurado e nenhuma porta abre. Nao se confunda
        com a pasta vazia: a chave do cofre e o arquivo da fila ja foram criados no
        construtor, ligada ou nao a barra. Quem injeta um registro pronto (os testes e
        qualquer integrador) manda no que esta ligado.
        """
        if self._registry_injetado or not self.config.enabled:
            return []
        return montar_registry(
            self.registry,
            self.config,
            vault=self.vault,
            home=self.home,
            log=self._log,
        )

    def bind_transports(self) -> dict[str, str]:
        """Aplica a escolha de meio por origem. Meio inexistente deixa a origem desligada."""
        resultado: dict[str, str] = {}
        for origem in ORIGENS:
            nome = self.config.transport_for(origem)
            if not nome:
                self.registry.unbind(origem)
                resultado[origem] = ""
                continue
            try:
                self.registry.bind(origem, nome)
                resultado[origem] = nome
            except UnknownTransport as exc:
                self.registry.unbind(origem)
                resultado[origem] = ""
                self._log(f"meio '{nome}' indisponivel para {origem}: {str(exc)[:120]}")
        return resultado

    def issue_credential(self, origem: str) -> Credential:
        """Emite (ou gira) a credencial de uma origem. O par so aparece nesta resposta."""
        return self.credentials.issue(origem)

    def registrar_comprovante(self, corpo: object) -> bool:
        """Fecha a volta do SMS: o recibo cifrado do celular vira estado na fila.

        A porta nao e desta barra - e a mesma que o aplicativo do celular ja usa desde
        a 1.7. Quem esta de fora entrega o corpo cifrado aqui, e o motorista registrado
        abre com o segredo do pareamento. Devolve False quando o recibo nao e da fila
        2.0, e quem recebeu pode seguir com o proprio caminho.
        """
        return aplicar_comprovante(self.store, self.registry, corpo, log=self._log)

    def status(self) -> dict:
        meios = {}
        for origem, health in self.registry.health().items():
            driver = self.registry.driver_for(origem)
            meios[origem] = {
                "meio": driver.name if driver else "",
                "disponivel": health.available,
                "motivo": health.reason,
            }
        return {
            "ativo": bool(self.config.enabled),
            "rodando": self._running,
            "porta": self.port,
            "meios": meios,
            "credenciais": self.credentials.describe(),
            "fila": self.store.stats(),
            "duvidas_na_volta": self.uncertain_after_restart,
            "assinatura_obrigatoria": bool(self.config.require_signed_requests),
            "chave_restrita_ao_dono": self.vault.permissoes_fechadas,
        }

    @property
    def running(self) -> bool:
        return self._running

    @property
    def port(self) -> int:
        return int(self.api.port) if self.api is not None else int(self.config.port)

    def _log(self, message: str) -> None:
        if self.on_log is None:
            return
        try:
            self.on_log(message)
        except Exception:
            pass

