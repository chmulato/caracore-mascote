"""Formato de conversa com o aplicativo Android (descoberta e comando)."""

from __future__ import annotations

import json
import os
import struct

DISCOVERY_PORT = 49999
COMMAND_PORT = 49998
DISCOVER_MAGIC = b"CARACORE-PDV-DISCOVER"
RESPONSE_PREFIX = "CARACORE-APK|"
MAX_FRAME = 65536


def frame(payload: bytes) -> bytes:
    """Prefixo de 4 bytes com o tamanho, igual ao lido pelo aplicativo."""
    if len(payload) > MAX_FRAME:
        raise ValueError("comando grande demais")
    return struct.pack(">I", len(payload)) + payload


def build_command(
    number: str,
    message: str,
    msg_id: str = "",
    timestamp: float | None = None,
    base_url: str = "",
) -> bytes:
    data = {"action": "send_sms", "number": number, "message": message}
    if msg_id:
        data["id"] = msg_id
    if timestamp is not None:
        data["ts"] = int(timestamp)
    if base_url:
        data["base"] = base_url
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def parse_discovery(data: bytes) -> tuple[str, int] | None:
    """Le 'CARACORE-APK|ip|porta' e devolve (ip, porta) ou None."""
    try:
        text = data.decode("utf-8", "ignore").strip()
    except Exception:
        return None
    if not text.startswith(RESPONSE_PREFIX):
        return None
    parts = text.split("|")
    if len(parts) < 3:
        return None
    host = parts[1].strip()
    if not host:
        return None
    try:
        port = int(parts[2].strip(), 10)
    except ValueError:
        return None
    if not 0 < port < 65536:
        return None
    return host, port


def new_message_id() -> str:
    return os.urandom(8).hex()
