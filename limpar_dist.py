#!/usr/bin/env python3
"""
Remove o diretório dist (e opcionalmente build) do workspace local.

Uso:
  python limpar_dist.py           # remove apenas dist/
  python limpar_dist.py --build   # remove dist/ e build/
  python limpar_dist.py -n       # simula, nao remove (dry-run)
"""

import shutil
import sys
from pathlib import Path


def main():
    script_dir = Path(__file__).resolve().parent
    dist_dir = script_dir / "dist"
    build_dir = script_dir / "build"

    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    include_build = "--build" in sys.argv or "-b" in sys.argv

    if dry_run:
        print("Modo simulação (nenhum arquivo será removido).")

    removed = []

    if dist_dir.exists():
        if dry_run:
            print(f"Seriam removidos: {dist_dir}")
        else:
            try:
                shutil.rmtree(dist_dir)
                print(f"Removido: {dist_dir}")
                removed.append("dist")
            except Exception as e:
                print(f"Erro ao remover {dist_dir}: {e}", file=sys.stderr)
                sys.exit(1)
    else:
        print(f"Diretório não encontrado: {dist_dir}")

    if include_build and build_dir.exists():
        if dry_run:
            print(f"Seriam removidos: {build_dir}")
        else:
            try:
                shutil.rmtree(build_dir)
                print(f"Removido: {build_dir}")
                removed.append("build")
            except Exception as e:
                print(f"Erro ao remover {build_dir}: {e}", file=sys.stderr)
                sys.exit(1)
    elif include_build and not build_dir.exists():
        print(f"Diretório não encontrado: {build_dir}")

    if not dry_run and removed:
        print("Concluído.")
    elif dry_run:
        print("Fim da simulação.")


if __name__ == "__main__":
    main()
