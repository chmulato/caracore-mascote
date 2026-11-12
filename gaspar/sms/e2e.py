"""Criptografia de ponta a ponta entre o computador do PDV e o celular.

O celular guarda um par de chaves EC P-256 e envia a chave publica ao Gaspar no
pareamento. Cada pedido sai com uma chave efemera (ECDH + HKDF-SHA256) e o
conteudo vai em AES-256-GCM. O Gaspar nao guarda chave privada do celular, logo
nao consegue abrir o envelope que ele mesmo repassa.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CURVE = ec.SECP256R1()
PUBLIC_KEY_LEN = 65
IV_LEN = 12
TAG_LEN = 16
KEY_LEN = 32
HKDF_SALT = b"gaspar-sms-e2e-v1"
HKDF_INFO = b"pdv-phone"
TAG_DOMAIN = b"gaspar-sms-audit-v1"


class E2EError(Exception):
    """Envelope ou chave fora do formato esperado."""


def _public_bytes(public_key) -> bytes:
    return public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


def parse_public_key(raw: bytes):
    if len(raw) != PUBLIC_KEY_LEN or raw[0] != 0x04:
        raise E2EError("chave publica do celular invalida")
    try:
        return ec.EllipticCurvePublicKey.from_encoded_point(CURVE, raw)
    except ValueError as exc:
        raise E2EError("chave publica do celular invalida") from exc


def parse_public_key_b64(text: object) -> bytes:
    value = str(text or "").strip()
    if not value:
        raise E2EError("chave publica ausente")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise E2EError("chave publica do celular invalida") from exc
    parse_public_key(raw)
    return raw


def is_valid_public_key_b64(text: object) -> bool:
    try:
        parse_public_key_b64(text)
    except E2EError:
        return False
    return True


def fingerprint(public_raw: bytes) -> str:
    return hashlib.sha256(public_raw).hexdigest()[:16]


def fingerprint_b64(text: object) -> str:
    try:
        return fingerprint(parse_public_key_b64(text))
    except E2EError:
        return ""


def generate_keypair() -> tuple[bytes, bytes]:
    """Par de chaves no formato que o aplicativo Android usa (PKCS8 + ponto)."""
    private_key = ec.generate_private_key(CURVE)
    private_der = private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return private_der, _public_bytes(private_key.public_key())


def _derive_key(shared_secret: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=HKDF_SALT,
        info=HKDF_INFO,
    ).derive(shared_secret)


def seal(peer_public_b64: object, plaintext: bytes, aad: bytes) -> str:
    """Devolve base64(chave efemera publica || IV || texto cifrado)."""
    peer = parse_public_key(parse_public_key_b64(peer_public_b64))
    ephemeral = ec.generate_private_key(CURVE)
    key = _derive_key(ephemeral.exchange(ec.ECDH(), peer))
    iv = os.urandom(IV_LEN)
    body = AESGCM(key).encrypt(iv, plaintext, aad)
    return base64.b64encode(_public_bytes(ephemeral.public_key()) + iv + body).decode("ascii")


def open_sealed(private_der: bytes, envelope_b64: object, aad: bytes) -> bytes:
    value = str(envelope_b64 or "").strip()
    if not value:
        raise E2EError("envelope ausente")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise E2EError("envelope invalido") from exc
    if len(raw) < PUBLIC_KEY_LEN + IV_LEN + TAG_LEN:
        raise E2EError("envelope invalido")
    peer = parse_public_key(raw[:PUBLIC_KEY_LEN])
    iv = raw[PUBLIC_KEY_LEN : PUBLIC_KEY_LEN + IV_LEN]
    body = raw[PUBLIC_KEY_LEN + IV_LEN :]
    try:
        private_key = serialization.load_der_private_key(private_der, None)
    except ValueError as exc:
        raise E2EError("chave privada invalida") from exc
    key = _derive_key(private_key.exchange(ec.ECDH(), peer))
    try:
        return AESGCM(key).decrypt(iv, body, aad)
    except Exception as exc:
        raise E2EError("envelope invalido") from exc


def tag(key: bytes, value: str) -> str:
    """Rotulo estavel para a auditoria: identifica sem guardar o dado."""
    mac = hmac.new(key, TAG_DOMAIN + value.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac[:TAG_LEN]).decode("ascii").rstrip("=")
