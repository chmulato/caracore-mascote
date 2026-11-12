"""Canal de atualizacao do Gaspar.

O canal publica um unico arquivo assinado (``latest.json``) com o manifesto da
versao mais recente. A assinatura Ed25519 e conferida aqui com a chave publica
que acompanha o aplicativo; nenhum campo do envelope e usado sem estar dentro
do payload assinado. A atualizacao nunca e aplicada sem o aceite do usuario e
nunca interrompe uma simulacao ou uma venda em andamento.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from . import __version__
from .paths import asset_path, data_dir

CANAL_URL = "https://gaspar.caracore.com.br/latest.json"
APP_ID = "gaspar"
CANAL = "stable"
CHAVE_PUBLICA_ASSET = "gaspar-update-public.pem"

LIMITE_MANIFESTO = 64 * 1024
LIMITE_INSTALADOR = 256 * 1024 * 1024
TIMEOUT = 8
INTERVALO_CONSULTA = 6 * 3600
INTERVALO_MINIMO = 30 * 60
ESPERA_INICIAL = (25, 60)


class FalhaAtualizacao(Exception):
    """Falha esperada do canal; a mensagem vai para o log, nunca para um popup."""


@dataclass(frozen=True)
class Manifesto:
    versao: str
    mandatory: bool
    min_supported: str
    notes_url: str
    notas: str
    publicado_em: str
    key_id: str
    assets: dict


@dataclass(frozen=True)
class Disponivel:
    versao: str
    mandatory: bool
    url: str
    sha256: str
    tamanho: int
    notas: str
    notes_url: str
    publicado_em: str


def chave_publica(caminho: Path | None = None):
    alvo = Path(caminho) if caminho is not None else asset_path(CHAVE_PUBLICA_ASSET)
    try:
        dados = alvo.read_bytes()
    except OSError:
        return None
    try:
        return load_pem_public_key(dados)
    except ValueError:
        return None


def _normalizar(versao: str) -> str:
    limpo = (versao or "").strip()
    if limpo[:1] in ("v", "V"):
        limpo = limpo[1:]
    return limpo


def _anterior(atual: str, referencia: str) -> bool:
    a = _normalizar(atual)
    b = _normalizar(referencia)
    if not a or not b:
        return False
    partes_a = a.split(".")
    partes_b = b.split(".")
    for i in range(max(len(partes_a), len(partes_b))):
        pa = partes_a[i] if i < len(partes_a) else ""
        pb = partes_b[i] if i < len(partes_b) else ""
        if pa == pb:
            continue
        if not pa:
            return pb.isdigit()
        if not pb:
            return not pa.isdigit()
        na, nb = pa.split("-")[0], pb.split("-")[0]
        if na.isdigit() and nb.isdigit():
            if int(na) != int(nb):
                return int(na) < int(nb)
            pre_a = pa[len(na):]
            pre_b = pb[len(nb):]
            if pre_a == pre_b:
                continue
            if not pre_a:
                return False
            if not pre_b:
                return True
            return pre_a < pre_b
        if na.isdigit() != nb.isdigit():
            return na.isdigit()
        if pa != pb:
            return pa.lower() < pb.lower()
    return False


def ha_versao_nova(remota: str, local: str) -> bool:
    return bool(_normalizar(remota)) and _anterior(local, remota) and _normalizar(remota) != _normalizar(local)


def _b64(valor: str, campo: str) -> bytes:
    try:
        return base64.b64decode(str(valor), validate=True)
    except (ValueError, TypeError) as exc:
        raise FalhaAtualizacao(f"campo {campo} invalido no manifesto") from exc


def verificar_envelope(corpo: bytes, chave) -> Manifesto:
    """Confere a assinatura e devolve somente o que esta dentro do payload."""
    if not corpo or len(corpo) > LIMITE_MANIFESTO:
        raise FalhaAtualizacao("manifesto vazio ou grande demais")
    try:
        envelope = json.loads(corpo)
    except ValueError as exc:
        raise FalhaAtualizacao("manifesto nao e JSON") from exc
    if not isinstance(envelope, dict):
        raise FalhaAtualizacao("manifesto fora do formato")
    payload_bytes = _b64(envelope.get("payload", ""), "payload")
    assinatura = _b64(envelope.get("signature", ""), "signature")
    if not payload_bytes or not assinatura:
        raise FalhaAtualizacao("manifesto sem payload ou assinatura")
    try:
        chave.verify(assinatura, payload_bytes)
    except InvalidSignature as exc:
        raise FalhaAtualizacao("assinatura do manifesto nao confere") from exc
    try:
        payload = json.loads(payload_bytes)
    except ValueError as exc:
        raise FalhaAtualizacao("payload do manifesto ilegivel") from exc
    if not isinstance(payload, dict):
        raise FalhaAtualizacao("payload do manifesto fora do formato")
    if payload.get("appId") != APP_ID:
        raise FalhaAtualizacao("manifesto de outro aplicativo")
    if payload.get("channel") != CANAL:
        raise FalhaAtualizacao("manifesto de outro canal")
    versao = str(payload.get("version") or "").strip()
    if not versao:
        raise FalhaAtualizacao("manifesto sem versao")
    assets = payload.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise FalhaAtualizacao("manifesto sem assets")
    return Manifesto(
        versao=versao,
        mandatory=bool(payload.get("mandatory", False)),
        min_supported=str(payload.get("min_supported") or "").strip(),
        notes_url=str(payload.get("notes_url") or "").strip(),
        notas=str(payload.get("releaseNotes") or "").strip(),
        publicado_em=str(payload.get("published_at") or "").strip(),
        key_id=str(envelope.get("key_id") or "").strip(),
        assets=assets,
    )


def _permitido(url: str) -> bool:
    partes = urllib.parse.urlsplit(url)
    if partes.scheme == "https":
        return True
    if partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost"):
        return True
    return False


def _abrir(url: str, timeout: int, limite: int) -> bytes:
    if not _permitido(url):
        raise FalhaAtualizacao("endereco do canal nao e HTTPS")
    pedido = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"Gaspar/{__version__}",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            if resposta.status != 200:
                raise FalhaAtualizacao(f"canal respondeu HTTP {resposta.status}")
            dados = resposta.read(limite + 1)
    except urllib.error.HTTPError as exc:
        raise FalhaAtualizacao(f"canal respondeu HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise FalhaAtualizacao(f"canal inacessivel ({exc.__class__.__name__})") from exc
    if len(dados) > limite:
        raise FalhaAtualizacao("resposta do canal grande demais")
    return dados


def buscar_manifesto(url: str = CANAL_URL, timeout: int = TIMEOUT) -> bytes:
    return _abrir(url, timeout, LIMITE_MANIFESTO)


def _asset(manifesto: Manifesto) -> dict | None:
    nome = "windows-setup" if sys.platform == "win32" else "linux-deb"
    dados = manifesto.assets.get(nome)
    if not isinstance(dados, dict):
        return None
    url = str(dados.get("url") or "")
    sha = str(dados.get("sha256") or "").lower()
    if not url or len(sha) != 64:
        return None
    try:
        tamanho = int(dados.get("size") or 0)
    except (TypeError, ValueError):
        tamanho = 0
    return {"url": url, "sha256": sha, "size": tamanho}


def avaliar(manifesto: Manifesto, local: str = __version__) -> Disponivel | None:
    if not ha_versao_nova(manifesto.versao, local):
        return None
    asset = _asset(manifesto)
    if asset is None:
        raise FalhaAtualizacao("manifesto sem pacote para esta plataforma")
    obrigatoria = manifesto.mandatory
    if manifesto.min_supported and _anterior(local, manifesto.min_supported):
        obrigatoria = True
    return Disponivel(
        versao=manifesto.versao,
        mandatory=obrigatoria,
        url=asset["url"],
        sha256=asset["sha256"],
        tamanho=asset["size"],
        notas=manifesto.notas,
        notes_url=manifesto.notes_url,
        publicado_em=manifesto.publicado_em,
    )


def consultar(url: str = CANAL_URL, chave=None, local: str = __version__) -> Disponivel | None:
    if chave is None:
        chave = chave_publica()
    if chave is None:
        raise FalhaAtualizacao("chave publica do canal ausente")
    manifesto = verificar_envelope(buscar_manifesto(url), chave)
    return avaliar(manifesto, local)


def baixar_instalador(url: str, sha256: str, destino: Path, timeout: int = 60) -> Path:
    """Baixa e confere o pacote; so devolve o caminho quando o SHA-256 bate."""
    if not _permitido(url):
        raise FalhaAtualizacao("endereco do pacote nao e HTTPS")
    nome = Path(urllib.parse.urlsplit(url).path).name
    if not nome:
        raise FalhaAtualizacao("endereco do pacote sem nome")
    if sys.platform == "win32" and not nome.lower().endswith(".exe"):
        raise FalhaAtualizacao("pacote do Windows nao e instalador .exe")
    destino.parent.mkdir(parents=True, exist_ok=True)
    alvo = destino / nome
    parcial = alvo.with_suffix(alvo.suffix + ".part")
    pedido = urllib.request.Request(
        url,
        headers={"User-Agent": f"Gaspar/{__version__}", "Accept": "application/octet-stream"},
    )
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta, parcial.open("wb") as arquivo:
            if resposta.status != 200:
                raise FalhaAtualizacao(f"download respondeu HTTP {resposta.status}")
            while True:
                bloco = resposta.read(256 * 1024)
                if not bloco:
                    break
                total += len(bloco)
                if total > LIMITE_INSTALADOR:
                    raise FalhaAtualizacao("pacote grande demais")
                digest.update(bloco)
                arquivo.write(bloco)
    except (urllib.error.URLError, OSError) as exc:
        parcial.unlink(missing_ok=True)
        raise FalhaAtualizacao(f"download do pacote falhou ({exc.__class__.__name__})") from exc
    if total == 0:
        parcial.unlink(missing_ok=True)
        raise FalhaAtualizacao("pacote vazio")
    if digest.hexdigest().lower() != sha256.lower():
        parcial.unlink(missing_ok=True)
        raise FalhaAtualizacao("SHA-256 do pacote nao confere")
    os.replace(parcial, alvo)
    return alvo


def estado_path() -> Path:
    return data_dir() / "update.json"


def carregar_estado() -> dict:
    try:
        return json.loads(estado_path().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def salvar_estado(**campos) -> dict:
    estado = carregar_estado()
    estado.update(campos)
    alvo = estado_path()
    temporario = alvo.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(estado, indent=2), encoding="utf-8")
    os.replace(temporario, alvo)
    return estado


def _ps_aspas(valor: str) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def _roteiro_windows(
    instalador: Path, app_exe: Path | None, versao: str, pid: int, resultado: Path
) -> str:
    if app_exe is not None:
        reabrir = (
            f'Start-Process -FilePath {_ps_aspas(str(app_exe))} '
            "-ArgumentList '--minimized'\n"
        )
    else:
        reabrir = ""
    return (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        f"Wait-Process -Id {pid} -Timeout 60\n"
        "Start-Sleep -Milliseconds 500\n"
        f"$codigo = 1\n"
        f"try {{ $p = Start-Process -FilePath {_ps_aspas(str(instalador))} "
        "-ArgumentList '/SILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru; "
        "$codigo = $p.ExitCode } catch { $codigo = -1 }\n"
        f'Set-Content -Path {_ps_aspas(str(resultado))} -Encoding ASCII '
        f'-Value ("version={versao}`ncode=$codigo")\n'
        f"{reabrir}"
    )


def aplicar_windows(instalador: Path, app_exe: Path | None, versao: str) -> None:
    """Sai do caminho e deixa um processo separado instalar, registrar e reabrir.

    O Gaspar precisa liberar os arquivos antes do instalador copiar; por isso o
    aplicativo encerra logo depois de disparar este processo, que espera o PID
    atual terminar.
    """
    resultado = estado_path().with_name("update-result.txt")
    roteiro = _roteiro_windows(instalador, app_exe, versao, os.getpid(), resultado)
    codificado = base64.b64encode(roteiro.encode("utf-16-le")).decode("ascii")
    criar = 0
    if sys.platform == "win32":
        criar = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", codificado],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=criar,
    )


def ler_resultado_instalacao() -> dict | None:
    """Le o desfecho da ultima instalacao e apaga o marcador."""
    marcador = estado_path().with_name("update-result.txt")
    try:
        linhas = marcador.read_text(encoding="ascii", errors="replace").splitlines()
    except OSError:
        return None
    dados = {}
    for linha in linhas:
        chave, _, valor = linha.partition("=")
        dados[chave.strip()] = valor.strip()
    try:
        marcador.unlink()
    except OSError:
        pass
    if not dados:
        return None
    try:
        dados["code"] = int(dados.get("code", "-1"))
    except ValueError:
        dados["code"] = -1
    return dados


def abrir_pagina(url: str) -> bool:
    if not url:
        return False
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


class Vigia:
    """Consulta o canal em segundo plano e avisa a interface pelo callback."""

    def __init__(self, app, chave, url: str = CANAL_URL, local: str = __version__):
        self.app = app
        self.chave = chave
        self.url = url
        self.local = local
        self.disponivel: Disponivel | None = None
        self.ultimo_erro = ""
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    def iniciar(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._laco, name="gaspar-updates", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    def verificar_agora(self) -> Disponivel | None:
        disponivel = consultar(self.url, self.chave, self.local)
        if disponivel is not None:
            self.disponivel = disponivel
            self.app.ui(self.app.mostrar_atualizacao, disponivel)
        return disponivel

    def _laco(self) -> None:
        if self._parar.wait(random.uniform(*ESPERA_INICIAL)):
            return
        estado = carregar_estado()
        ultima = float(estado.get("last_check") or 0)
        if time.time() - ultima >= INTERVALO_MINIMO:
            self._consultar()
        while not self._parar.wait(INTERVALO_CONSULTA + random.uniform(-900, 900)):
            self._consultar()

    def _consultar(self) -> None:
        try:
            disponivel = consultar(self.url, self.chave, self.local)
        except FalhaAtualizacao as exc:
            if str(exc) != self.ultimo_erro:
                self.ultimo_erro = str(exc)
                self.app.log_system(f"Canal de atualizacao: {exc}.")
            return
        except Exception as exc:  # nunca derruba o aplicativo por causa do canal
            if not self.ultimo_erro:
                self.ultimo_erro = exc.__class__.__name__
                self.app.log_system(
                    f"Canal de atualizacao indisponivel ({exc.__class__.__name__})."
                )
            return
        self.ultimo_erro = ""
        salvar_estado(last_check=int(time.time()))
        if disponivel is None:
            return
        pulada = str(carregar_estado().get("skipped_version") or "")
        if pulada and pulada == disponivel.versao and not disponivel.mandatory:
            return
        self.disponivel = disponivel
        self.app.ui(self.app.mostrar_atualizacao, disponivel)
