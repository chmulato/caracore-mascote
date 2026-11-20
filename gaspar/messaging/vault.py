"""Chave e cifra do que a fila guarda de sensivel.

Nada de cliente fica em texto claro no banco: numero do destinatario e texto do
SMS usam AES-GCM com IV aleatorio. A busca por ``id_externo`` e o casamento de
uma resposta precisam de valor deterministico, entao usam AES-SIV, que so revela
que duas linhas tem o mesmo valor - e nada alem disso.

A chave fica num arquivo ao lado da fila, criado na primeira execucao. Quem tem
acesso ao arquivo tem acesso a fila inteira; e por isso que a pasta fica na
configuracao do proprio usuario (``GASPAR_HOME``).
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from gaspar.sms.crypto import decrypt as _aesgcm_decrypt
from gaspar.sms.crypto import encrypt as _aesgcm_encrypt

from .errors import StorageError

KEY_BYTES = 64
KEY_FILENAME = "messaging-vault.key"

_AEAD_DOMAIN = b"gaspar-messaging-aead-v1"
_TAG_DOMAIN = b"gaspar-messaging-tag-v1"
_TAG_LENGTH = 12


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text or "") + padding)


class Vault:
    """Cifra e rotula os campos sensiveis da fila."""

    def __init__(self, key: bytes):
        if len(key) != KEY_BYTES:
            raise ValueError(f"a chave da fila precisa ter {KEY_BYTES} bytes")
        self._siv = AESSIV(key)
        self._aead_key = hashlib.sha256(_AEAD_DOMAIN + key).digest()

    @classmethod
    def load_or_create(cls, path: Path) -> "Vault":
        target = Path(path)
        if target.exists():
            try:
                raw = _b64decode(target.read_text(encoding="ascii").strip())
            except (OSError, ValueError) as exc:
                raise StorageError("nao foi possivel ler a chave da fila") from exc
            if len(raw) != KEY_BYTES:
                raise StorageError("a chave da fila esta corrompida")
            return cls(raw)
        key = os.urandom(KEY_BYTES)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(_b64encode(key), encoding="ascii")
            os.replace(tmp, target)
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
        except OSError as exc:
            raise StorageError("nao foi possivel guardar a chave da fila") from exc
        return cls(key)

    def seal(self, value: str) -> str:
        """Cifra com IV aleatorio: duas linhas iguais ficam diferentes no banco."""
        return _b64encode(_aesgcm_encrypt(self._aead_key, str(value or "").encode("utf-8")))

    def open(self, blob: str) -> str:
        try:
            return _aesgcm_decrypt(self._aead_key, _b64decode(blob)).decode("utf-8")
        except (InvalidTag, ValueError, TypeError) as exc:
            raise StorageError("conteudo da fila nao confere com a chave") from exc

    def deterministic(self, value: str, domain: str) -> str:
        """Cifra deterministica, para linha que precisa ser encontrada depois."""
        plaintext = str(value or "").encode("utf-8")
        return _b64encode(self._siv.encrypt(plaintext, [domain.encode("ascii")]))

    def reveal(self, blob: str, domain: str) -> str:
        try:
            return self._siv.decrypt(_b64decode(blob), [domain.encode("ascii")]).decode("utf-8")
        except (InvalidTag, ValueError, TypeError) as exc:
            raise StorageError("identificador guardado nao confere com a chave") from exc

    def tag(self, value: str, domain: str) -> str:
        """Rotulo estavel: compara sem guardar o dado."""
        digest = hashlib.sha256(
            _TAG_DOMAIN + domain.encode("ascii") + b"\n" + str(value or "").encode("utf-8") + b"\n"
            + self._aead_key
        ).digest()
        return base64.urlsafe_b64encode(digest[:_TAG_LENGTH]).decode("ascii").rstrip("=")
