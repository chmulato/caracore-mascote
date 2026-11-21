"""Configuracao da barra de mensagens do Gaspar 2.0.

Tudo comeca desligado. Enquanto ``enabled`` for falso, nenhuma porta abre,
nenhum meio se mexe e o mascote continua exatamente como na versao 1.7. Assim o
codigo novo pode entrar no produto sem mudar o comportamento de quem ja usa.

A porta e sempre local (127.0.0.1): o contrato e entre programas do mesmo
computador de balcao, nunca pela internet.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path

from gaspar.paths import data_dir

from .model import ORIGENS, validar_origem

CONFIG_FILENAME = "messaging.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8767
MAX_BODY_BYTES = 64 * 1024


def is_loopback_host(host: object) -> bool:
    """Aceita so endereco do proprio computador; o resto fica de fora por desenho."""
    text = str(host or "").strip()
    if not text:
        return False
    if text.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_loopback


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "sim", "on"):
            return True
        if text in ("0", "false", "nao", "off", ""):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _as_int(value: object, default: int, *, low: int, high: int) -> int:
    try:
        number = int(float(str(value)))
    except (TypeError, ValueError):
        number = int(default)
    return min(max(number, low), high)


def _as_float(value: object, default: float, *, low: float, high: float) -> float:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        number = float(default)
    return min(max(number, low), high)


@dataclass
class MessagingConfig:
    """Opacoes da barra de mensagens, lidas de ``messaging.json``."""

    enabled: bool = False
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    require_signed_requests: bool = True
    request_clock_skew_seconds: int = 60
    nonce_ttl_seconds: int = 600
    max_pending: int = 2000
    daily_limit_per_origin: int = 300
    #: teto de pedidos de uma origem em cada janela de 60 segundos (D3)
    per_minute_limit_per_origin: int = 20
    max_attempts: int = 2
    poll_interval_seconds: float = 2.0
    #: motorista escolhido por origem: {"PDV": "loopback", "HUB": ""}
    transports: dict[str, str] = field(default_factory=dict)
    #: ajustes de cada motorista, pelo nome: {"smtp_email": {...}, "android_lan": {...}}
    transport_settings: dict[str, dict] = field(default_factory=dict)
    #: de onde este objeto veio; nao vai para o arquivo
    source: str = ""

    def __post_init__(self) -> None:
        self.enabled = _as_bool(self.enabled, False)
        host = str(self.host or DEFAULT_HOST).strip()
        if not is_loopback_host(host):
            host = DEFAULT_HOST
        self.host = host
        self.port = _as_int(self.port, DEFAULT_PORT, low=0, high=65535)
        self.require_signed_requests = _as_bool(self.require_signed_requests, True)
        self.request_clock_skew_seconds = _as_int(
            self.request_clock_skew_seconds, 60, low=5, high=600
        )
        self.nonce_ttl_seconds = _as_int(self.nonce_ttl_seconds, 600, low=10, high=3600)
        self.max_pending = _as_int(self.max_pending, 2000, low=1, high=200_000)
        self.daily_limit_per_origin = _as_int(self.daily_limit_per_origin, 300, low=1, high=100_000)
        self.per_minute_limit_per_origin = _as_int(
            self.per_minute_limit_per_origin, 20, low=1, high=self.daily_limit_per_origin
        )
        self.max_attempts = _as_int(self.max_attempts, 2, low=1, high=5)
        self.poll_interval_seconds = _as_float(self.poll_interval_seconds, 2.0, low=0.2, high=600.0)
        self.transports = self._clean_transports(self.transports)
        self.transport_settings = self._clean_settings(self.transport_settings)

    @staticmethod
    def _clean_transports(value: object) -> dict[str, str]:
        result: dict[str, str] = {}
        items = value if isinstance(value, dict) else {}
        for key, item in items.items():
            try:
                origin = validar_origem(key)
            except ValueError:
                continue
            result[origin] = str(item or "").strip()
        return result

    @staticmethod
    def _clean_settings(value: object) -> dict[str, dict]:
        """Guarda so blocos com nome de motorista e corpo de objeto.

        Um bloco torto (lista, texto, numero) nao derruba a leitura do arquivo: ele
        e descartado e o motorista correspondente sobe com os proprios padroes.
        """
        result: dict[str, dict] = {}
        items = value if isinstance(value, dict) else {}
        for chave, corpo in items.items():
            nome = str(chave or "").strip()
            if nome and isinstance(corpo, dict):
                result[nome] = dict(corpo)
        return result

    # ------------------------------------------------------------------ meios

    def transport_for(self, origem: str) -> str:
        try:
            return self.transports.get(validar_origem(origem), "")
        except ValueError:
            return ""

    def set_transport(self, origem: str, transport: str) -> None:
        origin = validar_origem(origem)
        name = str(transport or "").strip()
        if name:
            self.transports[origin] = name
        else:
            self.transports.pop(origin, None)

    @property
    def origins_with_transport(self) -> tuple[str, ...]:
        return tuple(origem for origem in ORIGENS if self.transports.get(origem))

    @property
    def meios_citados(self) -> tuple[str, ...]:
        """Motoristas que alguem escolheu, sem repeticao e em ordem de nome.

        E a lista que a fabrica percorre: ninguem monta uma caixa postal ou um
        celular que nenhuma origem foi usar.
        """
        citados = {nome for nome in self.transports.values() if nome}
        return tuple(sorted(citados))

    def settings_for(self, nome: str) -> dict:
        """Os ajustes gravados para um motorista. Ausente = objeto vazio."""
        bloco = self.transport_settings.get(str(nome or "").strip())
        return dict(bloco) if isinstance(bloco, dict) else {}

    def set_settings(self, nome: str, ajustes: object) -> None:
        key = str(nome or "").strip()
        if not key:
            return
        if isinstance(ajustes, dict) and ajustes:
            self.transport_settings[key] = dict(ajustes)
        else:
            self.transport_settings.pop(key, None)

    # -------------------------------------------------------------- arquivo

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "require_signed_requests": self.require_signed_requests,
            "request_clock_skew_seconds": self.request_clock_skew_seconds,
            "nonce_ttl_seconds": self.nonce_ttl_seconds,
            "max_pending": self.max_pending,
            "daily_limit_per_origin": self.daily_limit_per_origin,
            "per_minute_limit_per_origin": self.per_minute_limit_per_origin,
            "max_attempts": self.max_attempts,
            "poll_interval_seconds": self.poll_interval_seconds,
            "transports": {origem: self.transports[origem] for origem in ORIGENS if origem in self.transports},
            "transport_settings": {
                nome: dict(self.transport_settings[nome])
                for nome in sorted(self.transport_settings)
                if isinstance(self.transport_settings.get(nome), dict)
            },
        }

    def save(self, path: Path | None = None) -> Path:
        target = Path(path) if path is not None else Path(self.source or default_config_path())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.source = str(target)
        return target


def default_config_path() -> Path:
    return data_dir() / CONFIG_FILENAME


def load_config(path: Path | None = None) -> MessagingConfig:
    """Le o arquivo; o que falta ou estiver torto volta ao padrao desligado."""
    target = Path(path) if path is not None else default_config_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MessagingConfig(source=str(target))
    data = raw if isinstance(raw, dict) else {}
    known = {key: data[key] for key in data if key in MessagingConfig.__dataclass_fields__}
    known.pop("source", None)
    return MessagingConfig(**known, source=str(target))
