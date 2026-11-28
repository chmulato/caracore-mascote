"""Chave e cifra do que a fila guarda de sensivel.

Nada de cliente fica em texto claro no banco: numero do destinatario e texto do
SMS usam AES-GCM com IV aleatorio. A busca por ``id_externo`` e o casamento de
uma resposta precisam de valor deterministico, entao usam AES-SIV, que so revela
que duas linhas tem o mesmo valor - e nada alem disso.

A chave fica num arquivo ao lado da fila, criado na primeira execucao. Quem tem
acesso ao arquivo tem acesso a fila inteira; e por isso que a pasta fica na
configuracao do proprio usuario (``GASPAR_HOME``) e que no Windows a lista de
permissoes do arquivo e fechada para o dono da conta antes de ele existir no
lugar definitivo. Se o Windows recusar o fechamento, a chave nao nasce. Uma
chave que ja estava la e nao conseguiu ser fechada continua valendo - e aparece
no estado do servico, para a recusa nao sumir dentro de um ``chmod`` que o
sistema ignora.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import os
import subprocess
from io import StringIO
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from gaspar.sms.crypto import decrypt as _aesgcm_decrypt
from gaspar.sms.crypto import encrypt as _aesgcm_encrypt

from .errors import StorageError

KEY_BYTES = 64
KEY_FILENAME = "messaging-vault.key"

_AEAD_DOMAIN = b"gaspar-messaging-aead-v1"
_KDF_DOMAIN = b"gaspar-messaging-kdf-v1"
_TAG_DOMAIN = b"gaspar-messaging-tag-v2"
_TAG_LENGTH = 12
_ACL_TIMEOUT_SECONDS = 15


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text or "") + padding)


def _derive(master: bytes, label: bytes) -> bytes:
    """Uma subchave por oficio: a chave da fila nunca sai direto como chave de cifra ou de rotulo."""
    return hmac.new(master, _KDF_DOMAIN + b"\n" + label, hashlib.sha256).digest()


# ------------------------------------------------------------------- permissoes


def parse_owner_sid(csv_text: str) -> str:
    """Extrai o SID da saida de ``whoami /user /fo csv /nh`` (``DOM\\usuario,S-1-5-21-...``)."""
    try:
        linha = next(csv.reader(StringIO(str(csv_text or ""))))
    except StopIteration:
        return ""
    for celula in linha:
        texto = str(celula).strip().strip('"')
        if texto.startswith("S-1-"):
            return texto
    return ""


def icacls_arguments(path: Path | str, sid: str) -> list[str]:
    """Comando puro: tira a heranca e da acesso total so ao dono da conta.

    O ``*`` antes do SID e obrigatorio: sem ele o icacls procura um nome de conta,
    devolve ``Nao foi feito mapeamento entre os nomes de conta`` e sai com codigo
    1332. Sem shell, o caminho vai como argumento - pasta com espaco ou ponto e
    virgula nao vira instrucao de comando.
    """
    return ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:F"]


def _executar(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_ACL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def owner_sid() -> str:
    """Identificador da conta que esta rodando o Gaspar. Vazio quando nao da para saber."""
    resposta = _executar(["whoami", "/user", "/fo", "csv", "/nh"])
    if resposta is None or resposta.returncode != 0:
        return ""
    return parse_owner_sid(resposta.stdout)


def restrict_to_owner_windows(path: Path | str) -> bool:
    """Devolve True so quando o icacls confirmou que fechou a heranca do arquivo."""
    sid = owner_sid()
    if not sid:
        return False
    resposta = _executar(icacls_arguments(path, sid))
    return resposta is not None and resposta.returncode == 0


def restrict_to_owner(path: Path | str, *, fail_closed: bool = True) -> bool:
    """Fecha o arquivo para o dono. No Windows o ``chmod`` nao faz nada de util.

    O modo 0600 continua no Linux e no macOS. No Windows manda a lista de
    permissoes, e a pasta do usuario herda acesso do sistema, entao o arquivo
    nasce mais aberto do que parece.
    """
    if os.name == "nt":
        ok = restrict_to_owner_windows(path)
        if not ok and fail_closed:
            raise StorageError(
                "o Windows recusou fechar as permissoes do arquivo da chave da fila; "
                "a chave nao foi criada"
            )
        return ok
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        if fail_closed:
            raise StorageError("nao foi possivel fechar as permissoes do arquivo da chave") from exc
        return False
    return True


class Vault:
    """Cifra e rotula os campos sensiveis da fila."""

    def __init__(self, key: bytes):
        if len(key) != KEY_BYTES:
            raise ValueError(f"a chave da fila precisa ter {KEY_BYTES} bytes")
        self._siv = AESSIV(key)
        # A formula desta chave nao muda com o rotulo: o que ja foi cifrado na maquina precisa abrir.
        self._aead_key = hashlib.sha256(_AEAD_DOMAIN + key).digest()
        self._tag_key = _derive(key, b"tag")
        #: None = ninguem olhou a permissao (chave montada direto), False = o sistema recusou
        self.permissoes_fechadas: bool | None = None

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
            # Fecha o que ja existe, mas sem desligar a barra: uma chave que esta
            # na maquina desde antes deste fechamento nao pode virar motivo de pane.
            vault = cls(raw)
            vault.permissoes_fechadas = restrict_to_owner(target, fail_closed=False)
            return vault
        key = os.urandom(KEY_BYTES)
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(_b64encode(key), encoding="ascii")
                restrict_to_owner(tmp)
                os.replace(tmp, target)
            except OSError as exc:
                raise StorageError("nao foi possivel guardar a chave da fila") from exc
        except StorageError:
            # Nada de chave solta por ai: ou ela nasce fechada no lugar definitivo, ou nao nasce.
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        vault = cls(key)
        # Nascer fechada era condicao para existir: acima, a recusa ja teria impedido.
        vault.permissoes_fechadas = True
        return vault

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
        """Rotulo estavel: compara sem guardar o dado.

        E um HMAC com subchave propria, nao um resumo com a chave concatenada na
        ponta. Assim, quem escreve no banco nao consegue testar numero candidato
        sem ter a chave da fila - e o rotulo de um dominio nao reaproveita o do outro.
        """
        digest = hmac.new(
            self._tag_key,
            _TAG_DOMAIN
            + b"\n"
            + domain.encode("ascii")
            + b"\n"
            + str(value or "").encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest[:_TAG_LENGTH]).decode("ascii").rstrip("=")
