"""Cliente TCP que entrega o comando cifrado ao celular."""

from __future__ import annotations

import json
import socket
import struct
from dataclasses import dataclass

from .crypto import decrypt, encrypt
from .protocol import MAX_FRAME, build_command, frame


class SmsPhoneError(Exception):
    """Falha generica ao falar com o celular."""


class PhoneOffline(SmsPhoneError):
    """Celular inacessivel na rede."""


@dataclass
class SendResult:
    acknowledged: bool
    ack: dict | None = None


class PhoneClient:
    def __init__(
        self,
        host: str,
        port: int,
        key: bytes,
        timeout: float = 5.0,
        ack_timeout: float = 0.8,
    ):
        self.host = host
        self.port = int(port)
        self.key = key
        self.timeout = timeout
        self.ack_timeout = ack_timeout

    def send(self, number: str, message: str, msg_id: str = "", timestamp: float | None = None) -> SendResult:
        payload = build_command(number, message, msg_id, timestamp)
        blob = encrypt(self.key, payload)
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                sock.sendall(frame(blob))
                try:
                    sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                ack = self._read_ack(sock)
        except (OSError, TimeoutError) as exc:
            raise PhoneOffline(str(exc) or "celular sem resposta") from exc
        return SendResult(acknowledged=ack is not None, ack=ack)

    def _read_ack(self, sock: socket.socket) -> dict | None:
        sock.settimeout(self.ack_timeout)
        try:
            header = self._read_exact(sock, 4)
        except (socket.timeout, TimeoutError):
            return None
        if len(header) != 4:
            return None
        length = struct.unpack(">I", header)[0]
        if length <= 0 or length > MAX_FRAME:
            return None
        body = self._read_exact(sock, length)
        if len(body) != length:
            return None
        try:
            return json.loads(decrypt(self.key, body).decode("utf-8"))
        except Exception:
            return None

    @staticmethod
    def _read_exact(sock: socket.socket, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            part = sock.recv(size - len(chunks))
            if not part:
                break
            chunks.extend(part)
        return bytes(chunks)
