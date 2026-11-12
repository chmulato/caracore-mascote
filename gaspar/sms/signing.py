"""Assinatura dos pedidos do PDV: HMAC-SHA256, relogio e nonce de uso unico.

A chave da assinatura e o proprio token da API, em UTF-8. O cabecalho
X-Api-Token continua identificando a instalacao; a assinatura prova que quem
pediu conhece o segredo e impede que um pedido capturado seja repetido.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time

TIMESTAMP_HEADER = "X-Gaspar-Timestamp"
NONCE_HEADER = "X-Gaspar-Nonce"
SIGNATURE_HEADER = "X-Gaspar-Signature"
MAX_CLOCK_SKEW = 60
NONCE_TTL = 600
MIN_NONCE_LENGTH = 8
MAX_NONCE_LENGTH = 128


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def canonical_request(method: str, path: str, timestamp: int, nonce: str, body: bytes) -> bytes:
    parts = (
        method.upper(),
        path,
        str(int(timestamp)),
        nonce,
        body_digest(body),
    )
    return "\n".join(parts).encode("utf-8")


def sign_request(
    key: bytes,
    method: str,
    path: str,
    body: bytes,
    timestamp: int,
    nonce: str,
) -> str:
    return hmac.new(
        key,
        canonical_request(method, path, timestamp, nonce, body),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    key: bytes,
    method: str,
    path: str,
    body: bytes,
    timestamp: int,
    nonce: str,
    signature: str,
) -> bool:
    expected = sign_request(key, method, path, body, timestamp, nonce)
    received = str(signature or "").strip().lower()
    return bool(received) and hmac.compare_digest(expected, received)


class NonceCache:
    """Guarda nonces aceitos pelo tempo da janela de repeticao."""

    def __init__(self, ttl: int = NONCE_TTL):
        self.ttl = max(1, int(ttl))
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def accept(self, nonce: str, now: float | None = None) -> bool:
        moment = time.time() if now is None else float(now)
        text = str(nonce or "")
        if not text:
            return False
        with self._lock:
            self._prune(moment)
            if text in self._seen:
                return False
            self._seen[text] = moment
            return True

    def _prune(self, now: float) -> None:
        limit = now - self.ttl
        expired = [nonce for nonce, seen in self._seen.items() if seen < limit]
        for nonce in expired:
            del self._seen[nonce]
