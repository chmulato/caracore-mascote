"""Ferramenta local do canal de atualizacao do Gaspar.

Roda no computador do responsavel, com a chave privada Ed25519 no HD removivel
(ou no cofre). A chave nunca entra no repositorio, na nuvem ou no log: este
programa le a chave do ambiente ``GASPAR_RELEASE_SIGNING_KEY`` e grava apenas
o manifesto assinado. A publicacao no GitHub Pages e feita pela esteira
``channel.yml``, que so aceita um manifesto cuja assinatura confere com a
chave publica versionada.

Fluxo:

    python tools/gaspar_channel.py init-key --key E:/gaspar/gaspar-signing.pem
    export GASPAR_RELEASE_SIGNING_KEY="$(cat E:/gaspar/gaspar-signing.pem)"
    python tools/gaspar_channel.py sign --tag gaspar-v1.7.1
    python tools/gaspar_channel.py sign --tag gaspar-v1.7.1 --publish
    python tools/gaspar_channel.py check --expect 1.7.1
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gaspar import updates  # noqa: E402  (mesma verificacao do aplicativo)

CONFIG = ROOT / "release" / "channel.json"
CHAVE_PUBLICA = ROOT / "assets" / updates.CHAVE_PUBLICA_ASSET
SAIDA = ROOT / "dist" / "channel"
ENV_CHAVE = "GASPAR_RELEASE_SIGNING_KEY"
OBRIGATORIA = re.compile(r"(?im)^\s*mandatory\s*:\s*(true|sim|yes)\s*$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
VERSAO = re.compile(r"^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$")


class Falha(Exception):
    pass


def ler_config() -> dict:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Falha(f"configuracao ausente: {CONFIG}") from exc
    except ValueError as exc:
        raise Falha(f"configuracao invalida: {CONFIG}") from exc
    if config.get("channel") != "stable":
        raise Falha("canal assinado so aceita channel=stable")
    return config


def gh(argumentos: list[str], binario: bool = False):
    try:
        resultado = subprocess.run(
            ["gh", *argumentos],
            capture_output=True,
            check=False,
            text=not binario,
            encoding=None if binario else "utf-8",
        )
    except FileNotFoundError as exc:
        raise Falha("o gh (GitHub CLI) nao esta instalado") from exc
    if resultado.returncode != 0:
        erro = resultado.stderr
        mensagem = erro.decode("utf-8", "replace") if binario else erro
        raise Falha(f"gh {' '.join(argumentos[:3])} falhou: {(mensagem or '').strip()}")
    return resultado.stdout


def release(repo: str, tag: str) -> dict:
    saida = gh(
        [
            "release",
            "view",
            tag,
            "-R",
            repo,
            "--json",
            "tagName,name,body,publishedAt,isDraft,isPrerelease,assets",
        ]
    )
    return json.loads(saida)


def validar_release(dados: dict, config: dict) -> str:
    tag = str(dados.get("tagName") or "").strip()
    prefixo = config["tag_prefix"]
    if not tag.startswith(prefixo):
        raise Falha(f"etiqueta {tag} fora do padrao {prefixo}<versao>")
    if dados.get("isDraft"):
        raise Falha(f"{tag} ainda e rascunho: publique a release antes de assinar o canal")
    if dados.get("isPrerelease"):
        raise Falha(f"{tag} esta marcada como pre-release; o canal so aceita versao estavel")
    versao = tag[len(prefixo):].strip()
    if not VERSAO.match(versao):
        raise Falha(f"versao invalida na etiqueta: {versao}")
    return versao


def _digest(asset: dict) -> str | None:
    digest = str(asset.get("digest") or "")
    if digest.lower().startswith("sha256:"):
        valor = digest[7:].strip().lower()
        if SHA256.match(valor):
            return valor
    return None


def _baixar_asset(repo: str, asset: dict) -> bytes:
    identificador = asset.get("id")
    if not identificador:
        raise Falha(f"asset {asset.get('name')} sem id para leitura")
    return gh(
        [
            "api",
            "-H",
            "Accept: application/octet-stream",
            f"repos/{repo}/releases/assets/{identificador}",
        ],
        binario=True,
    )


def _somas_do_sidecar(repo: str, assets: list[dict]) -> dict:
    for asset in assets:
        if str(asset.get("name") or "").lower() != "sha256sums.txt":
            continue
        conteudo = _baixar_asset(repo, asset)
        somas = {}
        for linha in conteudo.decode("utf-8", "replace").splitlines():
            partes = linha.split()
            if len(partes) == 2 and SHA256.match(partes[0]):
                somas[partes[1].lstrip("*")] = partes[0].lower()
        return somas
    return {}


def _escolher(assets: list[dict], padrao: str) -> dict | None:
    filtro = re.compile(padrao)
    for asset in assets:
        if filtro.search(str(asset.get("name") or "")):
            return asset
    return None


def montar_payload(dados: dict, config: dict) -> tuple[str, dict]:
    versao = validar_release(dados, config)
    repo = config["repo"]
    tag = dados["tagName"]
    assets_gh = dados.get("assets") or []
    sidecar = _somas_do_sidecar(repo, assets_gh)
    assets = {}
    for chave, padrao in config["assets"].items():
        asset = _escolher(assets_gh, padrao)
        if asset is None:
            if chave == "windows-setup":
                raise Falha("release sem instalador do Windows (GasparSetup-*.exe)")
            continue
        nome = str(asset["name"])
        sha = _digest(asset)
        if sha is None:
            sha = sidecar.get(nome, "")
        if nome in sidecar and sha and sidecar[nome] != sha:
            raise Falha(f"sha256 de {nome} diverge entre o digest e o SHA256SUMS.txt")
        if not SHA256.match(sha or ""):
            raise Falha(f"asset {nome} sem sha256 verificavel")
        url = f"https://github.com/{repo}/releases/download/{tag}/{urllib.parse.quote(nome)}"
        assets[chave] = {"url": url, "sha256": sha.lower(), "size": int(asset.get("size") or 0)}

    corpo = str(dados.get("body") or "").strip()
    payload = {
        "appId": config["app_id"],
        "version": versao,
        "channel": "stable",
    }
    publicado = str(dados.get("publishedAt") or "").strip()
    if publicado:
        payload["published_at"] = publicado
    payload["mandatory"] = bool(OBRIGATORIA.search(corpo))
    if str(config.get("min_supported") or "").strip():
        payload["min_supported"] = str(config["min_supported"]).strip()
    if str(config.get("notes_url") or "").strip():
        payload["notes_url"] = str(config["notes_url"]).strip()
    payload["releaseNotes"] = corpo
    payload["assets"] = assets
    return versao, payload


def carregar_chave_privada():
    valor = os.environ.get(ENV_CHAVE, "").strip()
    if not valor:
        raise Falha(f"defina {ENV_CHAVE} com a chave privada (PEM ou PKCS#8 em base64)")
    if "BEGIN PRIVATE KEY" in valor:
        return serialization.load_pem_private_key(valor.encode("utf-8"), password=None)
    try:
        return serialization.load_der_private_key(base64.b64decode(valor), password=None)
    except (ValueError, TypeError) as exc:
        raise Falha(f"{ENV_CHAVE} nao contem uma chave Ed25519 PKCS#8 valida") from exc


def assinar(payload: dict, config: dict, chave) -> bytes:
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assinatura = chave.sign(payload_bytes)
    setup = payload["assets"].get("windows-setup") or {}
    envelope = {
        "payload": base64.b64encode(payload_bytes).decode("ascii"),
        "signature": base64.b64encode(assinatura).decode("ascii"),
        "key_id": config["key_id"],
        "appId": payload["appId"],
        "version": payload["version"],
        "downloadUrl": setup.get("url"),
        "sha256": setup.get("sha256"),
        "releaseNotes": payload["releaseNotes"],
        "mandatory": payload["mandatory"],
        "assets": payload["assets"],
    }
    if payload.get("min_supported"):
        envelope["min_supported"] = payload["min_supported"]
    if payload.get("notes_url"):
        envelope["notes_url"] = payload["notes_url"]
    if payload.get("published_at"):
        envelope["published_at"] = payload["published_at"]
    return json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")


def iniciar_chave(caminho: Path) -> None:
    destino = caminho.expanduser().resolve()
    if destino.is_relative_to(ROOT.resolve()):
        raise Falha("grave a chave privada FORA do repositorio (HD removivel ou cofre)")
    if destino.exists():
        raise Falha(f"{destino} ja existe; apague ou escolha outro caminho conscientemente")
    privada = Ed25519PrivateKey.generate()
    pem_privado = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(pem_privado)
    try:
        os.chmod(destino, 0o600)
    except OSError:
        pass
    publica = privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    CHAVE_PUBLICA.write_bytes(publica)
    print(f"Chave privada gravada em {destino} (fora do repositorio).")
    print(f"Chave publica gravada em {CHAVE_PUBLICA} (essa vai para o repositorio).")
    print("Para assinar, carregue a chave no ambiente a partir do arquivo:")
    print(f'  export {ENV_CHAVE}="$(cat {destino})"')


def gravar(corpo: bytes) -> Path:
    SAIDA.mkdir(parents=True, exist_ok=True)
    alvo = SAIDA / "latest.json"
    alvo.write_bytes(corpo)
    return alvo


def conferir_local(corpo: bytes) -> updates.Manifesto:
    chave = updates.chave_publica(CHAVE_PUBLICA)
    if chave is None:
        raise Falha(f"chave publica ausente em {CHAVE_PUBLICA}; rode init-key primeiro")
    return updates.verificar_envelope(corpo, chave)


def publicar(config: dict, tag: str, manifesto: Path, acompanhar: bool) -> None:
    repo = config["repo"]
    print(f"Enviando {manifesto.name} para a release {tag}...")
    gh(["release", "upload", tag, str(manifesto), "--clobber", "-R", repo])
    print("Disparando a esteira do canal (GitHub Pages)...")
    gh(["workflow", "run", "channel.yml", "-R", repo, "-f", f"tag={tag}"])
    if not acompanhar:
        print("Esteira disparada. Acompanhe com: gh run list --workflow channel.yml")
        return
    limite = time.time() + 360
    executado = None
    while time.time() < limite:
        time.sleep(10)
        saida = gh(
            [
                "run",
                "list",
                "--workflow",
                "channel.yml",
                "-R",
                repo,
                "--limit",
                "1",
                "--json",
                "databaseId,status,conclusion,url,createdAt",
            ]
        )
        lista = json.loads(saida or "[]")
        if not lista:
            continue
        atual = lista[0]
        if atual.get("createdAt") and int(time.time() - _epoch(atual["createdAt"])) > 600:
            continue
        if atual.get("status") == "completed":
            executado = atual
            break
    if executado is None:
        raise Falha("a esteira do canal nao terminou em 6 minutos; veja no GitHub Actions")
    if executado.get("conclusion") != "success":
        raise Falha(
            f"a esteira do canal terminou como {executado.get('conclusion')}: {executado.get('url')}"
        )
    print(f"Esteira concluida: {executado.get('url')}")


def _epoch(iso: str) -> float:
    import datetime

    try:
        return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


def imprimir_manifesto(origem: str, manifesto: updates.Manifesto, expect: str | None) -> None:
    setup = manifesto.assets.get("windows-setup") or {}
    print(f"origem: {origem}")
    print(f"versao: {manifesto.versao}")
    print(f"key_id: {manifesto.key_id}")
    print(f"publicado_em: {manifesto.publicado_em or '-'}")
    print(f"obrigatoria: {'sim' if manifesto.mandatory else 'nao'}")
    print(f"sha256 do instalador: {setup.get('sha256', '-')}")
    if expect and manifesto.versao != expect:
        raise Falha(f"o manifesto publica {manifesto.versao}, esperado {expect}")
    print("assinatura: OK (conferida com a chave publica do repositorio)")


def conferir_url(url: str, expect: str | None, tentativas: int = 1) -> None:
    chave = updates.chave_publica(CHAVE_PUBLICA)
    if chave is None:
        raise Falha(f"chave publica ausente em {CHAVE_PUBLICA}")
    for tentativa in range(1, tentativas + 1):
        try:
            corpo = updates.buscar_manifesto(url)
        except updates.FalhaAtualizacao as exc:
            transitorio = "HTTP 404" in str(exc) or "inacessivel" in str(exc)
            if tentativa < tentativas and transitorio:
                print(f"Aguardando o Pages publicar ({exc}); tentativa {tentativa}/{tentativas}.")
                time.sleep(10)
                continue
            raise Falha(str(exc)) from exc
        imprimir_manifesto(url, updates.verificar_envelope(corpo, chave), expect)
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Canal de atualizacao do Gaspar.")
    sub = parser.add_subparsers(dest="comando", required=True)

    init = sub.add_parser("init-key", help="gera o par de chaves (a privada fica fora do repositorio)")
    init.add_argument("--key", required=True, type=Path, help="caminho da chave privada (HD removivel)")

    assinar_cmd = sub.add_parser("sign", help="assina o manifesto de uma release publicada")
    assinar_cmd.add_argument("--tag", required=True, help="etiqueta gaspar-vX.Y.Z ja publicada")
    assinar_cmd.add_argument("--publish", action="store_true", help="envia a release e publica no Pages")
    assinar_cmd.add_argument("--no-wait", action="store_true", help="nao acompanha a esteira")

    check = sub.add_parser("check", help="confere o manifesto publicado no canal")
    check.add_argument("--url", help="endereco do canal (padrao: o da configuracao)")
    check.add_argument("--expect", help="versao esperada")

    verificar = sub.add_parser("verify", help="confere um manifesto assinado salvo em arquivo")
    verificar.add_argument("--file", required=True, type=Path)
    verificar.add_argument("--expect", help="versao esperada")

    try:
        args = parser.parse_args(argv)
        config = ler_config()
        if args.comando == "init-key":
            iniciar_chave(args.key)
            return 0
        if args.comando == "check":
            conferir_url(args.url or config["channel_url"], args.expect)
            return 0
        if args.comando == "verify":
            try:
                corpo = args.file.read_bytes()
            except OSError as exc:
                raise Falha(f"manifesto nao encontrado: {args.file}") from exc
            manifesto = conferir_local(corpo)
            imprimir_manifesto(str(args.file), manifesto, args.expect)
            return 0
        dados = release(config["repo"], args.tag)
        versao, payload = montar_payload(dados, config)
        manifesto = assinar(payload, config, carregar_chave_privada())
        verificado = conferir_local(manifesto)
        if verificado.versao != versao:
            raise Falha("o manifesto assinado nao confere consigo mesmo")
        alvo = gravar(manifesto)
        print(f"Manifesto assinado: {alvo}")
        print(f"versao {versao}, key_id {config['key_id']}")
        print(f"instalador sha256: {payload['assets']['windows-setup']['sha256']}")
        print(f"obrigatoria: {'sim' if payload['mandatory'] else 'nao'}")
        if args.publish:
            publicar(config, args.tag, alvo, not args.no_wait)
            conferir_url(config["channel_url"], versao, tentativas=7)
        return 0
    except Falha as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
