"""Preferencias e segredos da ponte de SMS."""

from __future__ import annotations

import base64
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field, fields
from pathlib import Path

from ..paths import data_dir
from . import e2e
from .protocol import COMMAND_PORT

CONFIG_FILENAME = "sms_config.json"
DEFAULT_HTTP_PORT = 8766
SETUP_TTL_SECONDS = 15 * 60
MIN_HTTP_PORT = 1024
MAX_HTTP_PORT = 65535
MIN_PER_MINUTE = 1
MAX_PER_MINUTE = 120
MIN_PER_DAY = 1
MAX_PER_DAY = 5000
MIN_PER_NUMBER_HOUR = 1
MAX_PER_NUMBER_HOUR = 10
MIN_PER_NUMBER_DAY = 1
MAX_PER_NUMBER_DAY = 50
MIN_DUPLICATE_WINDOW = 0
MAX_DUPLICATE_WINDOW = 1440
MIN_CLOCK_SKEW = 30
MAX_CLOCK_SKEW = 300
MIN_NONCE_TTL = 60
MAX_NONCE_TTL = 3600
MIN_AUDIT_RETENTION_DAYS = 1
MAX_AUDIT_RETENTION_DAYS = 3650
_SAVE_LOCK = threading.Lock()


@dataclass
class SmsConfig:
    enabled: bool = True
    http_port: int = DEFAULT_HTTP_PORT
    api_token: str = ""
    shared_secret_b64: str = ""
    setup_token: str = ""
    setup_token_created: float = 0.0
    phone_host: str = ""
    phone_port: int = COMMAND_PORT
    license_token: str = ""
    max_per_minute: int = 20
    max_per_day: int = 300
    per_number_per_hour: int = 1
    per_number_per_day: int = 3
    duplicate_window_minutes: int = 30
    require_signed_requests: bool = True
    only_templates: bool = True
    request_clock_skew_seconds: int = 60
    nonce_ttl_seconds: int = 600
    command_sequence: int = 0
    e2e_required: bool = True
    phone_public_key_b64: str = ""
    phone_key_updated_at: float = 0.0
    audit_key_b64: str = ""
    audit_retention_days: int = 90
    last_diagnostic_at: float = 0.0
    last_diagnostic_sms_ok: bool = False
    last_diagnostic_battery_ok: bool = False
    last_diagnostic_message: str = ""
    path: str = field(default="", repr=False, compare=False)

    def ensure_secrets(self) -> None:
        if not self.shared_secret_b64:
            self.shared_secret_b64 = base64.b64encode(os.urandom(32)).decode("ascii")
        if not self.api_token:
            self.api_token = secrets.token_urlsafe(24)
        if not self.audit_key_b64:
            self.audit_key_b64 = base64.b64encode(os.urandom(32)).decode("ascii")

    def audit_key(self) -> bytes:
        try:
            raw = base64.b64decode(self.audit_key_b64 or "", validate=True)
        except Exception:
            raw = b""
        if len(raw) < 16:
            self.audit_key_b64 = base64.b64encode(os.urandom(32)).decode("ascii")
            raw = base64.b64decode(self.audit_key_b64)
        return raw

    def phone_public_key(self) -> str:
        return str(self.phone_public_key_b64 or "").strip()

    def has_phone_key(self) -> bool:
        return e2e.is_valid_public_key_b64(self.phone_public_key())

    def set_phone_public_key(self, value: object, allow_replace: bool = False) -> bool:
        """Guarda a chave publica do celular.

        Trocar uma chave ja registrada so vale com o token de pareamento; assim
        ninguem que descubra o segredo da rede troca o celular por outro.
        """
        if not e2e.is_valid_public_key_b64(value):
            return False
        normalized = str(value).strip()
        current = self.phone_public_key()
        if current == normalized:
            return True
        if current and not allow_replace:
            return False
        self.phone_public_key_b64 = normalized
        self.phone_key_updated_at = time.time()
        return True

    def phone_key_fingerprint(self) -> str:
        return e2e.fingerprint_b64(self.phone_public_key())

    def rotate_api_token(self) -> str:
        self.api_token = secrets.token_urlsafe(24)
        return self.api_token

    def next_command_sequence(self) -> int:
        """Contador que so avanca; o celular recusa sequencia repetida."""
        self.command_sequence = max(0, int(self.command_sequence)) + 1
        self.save()
        return self.command_sequence

    def new_setup_token(self) -> str:
        self.setup_token = secrets.token_hex(8)
        self.setup_token_created = time.time()
        return self.setup_token

    def setup_token_valid(self, token: object) -> bool:
        if not token or not self.setup_token:
            return False
        if not secrets.compare_digest(str(token).strip(), self.setup_token):
            return False
        return (time.time() - self.setup_token_created) <= SETUP_TTL_SECONDS

    def setup_payload(self, ip: str) -> str:
        """QR lido pelo app: CARACORE-SETUP|ip|porta|chave|token|licenca."""
        self.ensure_secrets()
        if not self.setup_token_valid(self.setup_token):
            self.new_setup_token()
        address = (ip or "").strip()
        if not address:
            raise ValueError("endereco de rede indisponivel")
        return "|".join(
            (
                "CARACORE-SETUP",
                address,
                str(self.http_port),
                self.shared_secret_b64,
                self.setup_token,
                self.license_token or "",
            )
        )

    def save(self, path: Path | None = None) -> Path:
        target = Path(path or self.path or (data_dir() / CONFIG_FILENAME))
        self.path = str(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {item.name: getattr(self, item.name) for item in fields(self) if item.name != "path"}
        tmp = target.with_suffix(target.suffix + ".tmp")
        with _SAVE_LOCK:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target


def _coerce(config: SmsConfig, raw: dict) -> None:
    for item in fields(SmsConfig):
        if item.name == "path" or item.name not in raw:
            continue
        value = raw[item.name]
        current = getattr(config, item.name)
        if isinstance(current, bool):
            setattr(config, item.name, bool(value))
        elif isinstance(current, int):
            try:
                setattr(config, item.name, int(value))
            except (TypeError, ValueError):
                pass
        elif isinstance(current, float):
            try:
                setattr(config, item.name, float(value))
            except (TypeError, ValueError):
                pass
        elif isinstance(value, str):
            setattr(config, item.name, value)


def _clamp(config: SmsConfig) -> None:
    config.http_port = max(MIN_HTTP_PORT, min(MAX_HTTP_PORT, config.http_port or DEFAULT_HTTP_PORT))
    config.phone_port = max(1, min(65535, config.phone_port or COMMAND_PORT))
    config.max_per_minute = max(MIN_PER_MINUTE, min(MAX_PER_MINUTE, config.max_per_minute or 20))
    config.max_per_day = max(MIN_PER_DAY, min(MAX_PER_DAY, config.max_per_day or 300))
    config.per_number_per_hour = max(
        MIN_PER_NUMBER_HOUR, min(MAX_PER_NUMBER_HOUR, config.per_number_per_hour or 1)
    )
    config.per_number_per_day = max(
        config.per_number_per_hour,
        max(MIN_PER_NUMBER_DAY, min(MAX_PER_NUMBER_DAY, config.per_number_per_day or 3)),
    )
    config.duplicate_window_minutes = max(
        MIN_DUPLICATE_WINDOW, min(MAX_DUPLICATE_WINDOW, config.duplicate_window_minutes or 0)
    )
    config.request_clock_skew_seconds = max(
        MIN_CLOCK_SKEW, min(MAX_CLOCK_SKEW, config.request_clock_skew_seconds or 60)
    )
    config.nonce_ttl_seconds = max(
        MIN_NONCE_TTL, min(MAX_NONCE_TTL, config.nonce_ttl_seconds or 600)
    )
    config.command_sequence = max(0, config.command_sequence or 0)
    config.audit_retention_days = max(
        MIN_AUDIT_RETENTION_DAYS,
        min(MAX_AUDIT_RETENTION_DAYS, config.audit_retention_days or 90),
    )
    if not e2e.is_valid_public_key_b64(config.phone_public_key_b64):
        config.phone_public_key_b64 = ""
        config.phone_key_updated_at = 0.0


def load_config(path: Path | None = None) -> SmsConfig:
    target = Path(path or (data_dir() / CONFIG_FILENAME))
    config = SmsConfig(path=str(target))
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if isinstance(raw, dict):
        _coerce(config, raw)
    _clamp(config)
    config.ensure_secrets()
    config.save(target)
    return config
