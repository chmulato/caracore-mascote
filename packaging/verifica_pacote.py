#!/usr/bin/env python3
"""Confere se os modulos que o Gaspar so carrega em tempo de execucao estao
mesmo dentro do pacote gerado (ressalva D6 da auditoria da Fase Alpha).

O Portao roda os testes a partir da arvore de codigo, entao um pacote sem o
modulo passa no Portao e chega ao balcao com a peca desligada em silencio.
Este script abre o executavel e compara a lista de modulos congelados com a
lista dos modulos que existem no codigo-fonte.

Uso:
    python packaging/verifica_pacote.py
    python packaging/verifica_pacote.py --arquivo dist/windows/gaspar
    python packaging/verifica_pacote.py --arquivo AppDir/usr/bin/gaspar \\
        --esperar gaspar.messaging --esperar gaspar.sms
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PADRAO = ROOT / "dist" / "windows" / "gaspar"
#: Pacote Windows (onedir) e pacote Linux (AppImage extraido) colocam o
#: executavel principal em lugares diferentes.
PROCURAS = ("gaspar.exe", "gaspar", "gaspar_blackbox.exe")


class VerificacaoIndisponivel(RuntimeError):
    """Sem executavel legivel ou sem o leitor de pacotes do PyInstaller."""


def modulos_no_codigo(pacote: str) -> list[str]:
    """O nome do pacote e todos os submodulos dele, incluidos os de subpacote."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    modulo = importlib.import_module(pacote)
    nomes = [modulo.__name__]
    for item in pkgutil.walk_packages(modulo.__path__, modulo.__name__ + "."):
        nomes.append(item.name)
    return sorted(set(nomes))


def localizar_executavel(caminho: Path) -> Path:
    """Aceita o proprio executavel ou a pasta do pacote, e devolve o arquivo."""
    caminho = caminho.resolve()
    if caminho.is_file():
        return caminho
    if not caminho.is_dir():
        raise VerificacaoIndisponivel(f"caminho nao existe: {caminho}")
    for nome in PROCURAS:
        candidato = caminho / nome
        if candidato.is_file():
            return candidato
    raise VerificacaoIndisponivel(
        f"nenhum executavel encontrado em {caminho} (procurado: {', '.join(PROCURAS)})"
    )


def modulos_no_pacote(caminho: Path) -> list[str]:
    """Todos os modulos congelados dentro do PYZ do executavel."""
    try:
        from PyInstaller.archive.readers import ArchiveReadError, CArchiveReader
    except ImportError as exc:  # o verificador roda na maquina de build
        raise VerificacaoIndisponivel(f"PyInstaller nao esta instalado: {exc}") from exc
    try:
        arquivo = CArchiveReader(str(caminho))
    except (ArchiveReadError, OSError) as exc:
        raise VerificacaoIndisponivel(f"nao consegui abrir {caminho}: {exc}") from exc
    nomes_pyz = [nome for nome in arquivo.toc if nome.upper().startswith("PYZ")]
    if not nomes_pyz:
        raise VerificacaoIndisponivel(f"{caminho} nao tem um arquivo PYZ")
    congelados: set[str] = set()
    for nome in nomes_pyz:
        congelados.update(arquivo.open_embedded_archive(nome).toc)
    return sorted(congelados)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Confere os modulos do pacote gerado.")
    parser.add_argument(
        "--arquivo",
        default=str(PADRAO),
        help="executavel gerado ou a pasta do pacote (padrao: %(default)s)",
    )
    parser.add_argument(
        "--esperar",
        action="append",
        default=[],
        metavar="PACOTE",
        help="pacote que precisa estar inteiro no pacote gerado (repetivel)",
    )
    args = parser.parse_args(argv)
    pacotes = args.esperar or ["gaspar.messaging"]

    try:
        executavel = localizar_executavel(Path(args.arquivo))
        congelados = set(modulos_no_pacote(executavel))
    except VerificacaoIndisponivel as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 2

    faltando_total = 0
    for pacote in pacotes:
        esperados = modulos_no_codigo(pacote)
        faltando = [nome for nome in esperados if nome not in congelados]
        faltando_total += len(faltando)
        print(f"{pacote}: {len(esperados) - len(faltando)}/{len(esperados)} no pacote")
        for nome in esperados:
            print(f"  {'PRESENTE ' if nome in congelados else 'AUSENTE  '} {nome}")

    gaspar_no_pacote = sorted(nome for nome in congelados if nome == "gaspar" or nome.startswith("gaspar."))
    print(f"resumo: {len(congelados)} modulos congelados, {len(gaspar_no_pacote)} do Gaspar")
    if faltando_total:
        print(f"FALHA: {faltando_total} modulos fora do pacote", file=sys.stderr)
        return 1
    print("OK: todos os modulos esperados estao no pacote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
