"""Criptografia AES-256-GCM compativel com o aplicativo Android."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

IV_LEN = 12
KEY_BYTES = 32


def key_from_base64(secret_b64: str) -> bytes:
    """Repete a regra do GatewayCrypto: base64, SHA-256 se curta, 32 bytes."""
    if not secret_b64 or not secret_b64.strip():
        raise ValueError("chave de pareamento ausente")
    try:
        raw = base64.b64decode(secret_b64.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("chave de pareamento invalida") from exc
    if len(raw) < KEY_BYTES:
        raw = hashlib.sha256(raw).digest()
    return raw[:KEY_BYTES]


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Devolve IV (12 bytes) + texto cifrado + etiqueta GCM."""
    iv = os.urandom(IV_LEN)
    return iv + AESGCM(key).encrypt(iv, plaintext, None)


def decrypt(key: bytes, blob: bytes) -> bytes:
    if len(blob) < IV_LEN:
        raise ValueError("mensagem cifrada invalida")
    iv, cipher = blob[:IV_LEN], blob[IV_LEN:]
    return AESGCM(key).decrypt(iv, cipher, None)
