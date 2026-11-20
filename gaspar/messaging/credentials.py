"""Credenciais separadas por origem.

Cada produto (PDV e Hub) recebe um par proprio:

- ``token``: apresenta quem esta pedindo. O banco guarda apenas digesto com sal,
  entao quem le o arquivo da fila nao consegue reimprimir a credencial;
- ``secret``: assina o pedido (HMAC). Fica cifrado pela chave da fila porque o
  Gaspar precisa abrir a assinatura de cada requisicao.

A credencial e o que faz o isolamento: a origem de um pedido vem de quem
assinou, nunca do corpo da requisicao.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from .errors import CredentialError
from .model import ORIGENS, validar_origem
from .vault import Vault

TOKEN_BYTES = 32
SECRET_BYTES = 32
SALT_BYTES = 16
_DIGEST_DOMAIN = b"gaspar-messaging-credential-v1"
_SECRET_DOMAIN = "credencial_api"

_DDL = """
CREATE TABLE IF NOT EXISTS credentials (
    origem TEXT PRIMARY KEY,
    salt TEXT NOT NULL,
    verifier TEXT NOT NULL,
    secret_enc TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    rotated_at REAL NOT NULL DEFAULT 0
);
"""


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def new_secret() -> str:
    return secrets.token_urlsafe(SECRET_BYTES)


def _digest(token: str, salt: bytes) -> str:
    material = _DIGEST_DOMAIN + salt + str(token or "").encode("utf-8")
    return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class Credential:
    """O que o produto recebe uma unica vez, ao parear com o Gaspar."""

    origem: str
    token: str
    secret: str

    def to_dict(self) -> dict:
        return {"origem": self.origem, "token": self.token, "secret": self.secret}


class CredentialVault:
    """Emite, confere e gira as credenciais das origens dentro da propria fila."""

    def __init__(self, store, vault: Vault):
        self._store = store
        self._vault = vault
        with self._store.lock, self._store.handle:
            self._store.handle.executescript(_DDL)

    def issue(self, origem: str, *, replace: bool = True) -> Credential:
        """Cria a credencial da origem. O par so e devolvido nesta chamada."""
        origin = validar_origem(origem)
        token = new_token()
        secret = new_secret()
        salt = secrets.token_bytes(SALT_BYTES)
        now = time.time()
        with self._store.lock, self._store.handle:
            existing = self._store.handle.execute(
                "SELECT created_at FROM credentials WHERE origem = ?", (origin,)
            ).fetchone()
            if existing is not None and not replace:
                raise CredentialError(f"{origin} ja tem credencial; gire para trocar")
            if existing is None:
                self._store.handle.execute(
                    "INSERT INTO credentials (origem, salt, verifier, secret_enc, created_at, rotated_at)"
                    " VALUES (?, ?, ?, ?, ?, 0)",
                    (origin, salt.hex(), _digest(token, salt), self._vault.seal(secret), now),
                )
            else:
                self._store.handle.execute(
                    "UPDATE credentials SET salt = ?, verifier = ?, secret_enc = ?, rotated_at = ?"
                    " WHERE origem = ?",
                    (salt.hex(), _digest(token, salt), self._vault.seal(secret), now, origin),
                )
        return Credential(origin, token, secret)

    def ensure(self, origem: str) -> tuple[Credential | None, bool]:
        """Devolve (credencial, criada_agora). Quando ja existia, a credencial vem vazia."""
        origin = validar_origem(origem)
        if self.exists(origin):
            return None, False
        return self.issue(origin, replace=False), True

    def resolve(self, token: object) -> str | None:
        """Qual origem esta token representa? None quando nao serve para nenhuma."""
        text = str(token or "").strip()
        if not text:
            return None
        with self._store.lock:
            rows = self._store.handle.execute(
                "SELECT origem, salt, verifier FROM credentials"
            ).fetchall()
        for row in rows:
            try:
                salt = bytes.fromhex(row["salt"])
            except ValueError:  # pragma: no cover - linha escrita por outra versao
                continue
            if secrets.compare_digest(_digest(text, salt), str(row["verifier"])):
                return str(row["origem"])
        return None

    def secret_for(self, origem: str) -> str:
        """Segredo de assinatura da origem. Vazio quando ela nao tem credencial."""
        origin = validar_origem(origem)
        with self._store.lock:
            row = self._store.handle.execute(
                "SELECT secret_enc FROM credentials WHERE origem = ?", (origin,)
            ).fetchone()
        if row is None or not str(row["secret_enc"] or ""):
            return ""
        return self._vault.open(row["secret_enc"])

    def exists(self, origem: str) -> bool:
        origin = validar_origem(origem)
        with self._store.lock:
            return (
                self._store.handle.execute(
                    "SELECT 1 FROM credentials WHERE origem = ?", (origin,)
                ).fetchone()
                is not None
            )

    def revoke(self, origem: str) -> bool:
        origin = validar_origem(origem)
        with self._store.lock, self._store.handle:
            return (
                self._store.handle.execute(
                    "DELETE FROM credentials WHERE origem = ?", (origin,)
                ).rowcount
                == 1
            )

    def describe(self) -> dict[str, dict]:
        """Metadados de cada credencial. Token, digesto e segredo nunca saem daqui."""
        with self._store.lock:
            rows = self._store.handle.execute(
                "SELECT origem, created_at, rotated_at, secret_enc FROM credentials ORDER BY origem"
            ).fetchall()
        result = {
            str(row["origem"]): {
                "emitida_em": float(row["created_at"]),
                "girada_em": float(row["rotated_at"]),
                "assinatura": bool(str(row["secret_enc"] or "")),
            }
            for row in rows
        }
        for origin in ORIGENS:
            result.setdefault(origin, {"emitida_em": 0.0, "girada_em": 0.0, "assinatura": False})
        return result
