#!/usr/bin/env python3
"""Compila o Gaspar e o BlackBox para Windows e gera o instalador Inno Setup.

Uso:
    python packaging/windows/build_windows.py
    python packaging/windows/build_windows.py --no-installer
    python packaging/windows/build_windows.py --app-only
    python packaging/windows/build_windows.py --blackbox-only
    python packaging/windows/build_windows.py --installer-only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist" / "windows"
WORK = ROOT / "build" / "windows"
SPEC_APP = ROOT / "packaging" / "windows" / "gaspar.spec"
SPEC_BLACKBOX = ROOT / "packaging" / "windows" / "gaspar_blackbox.spec"
ISS_FILE = ROOT / "packaging" / "windows" / "gaspar.iss"
ASSETS = ROOT / "assets"


def read_version() -> str:
    content = (ROOT / "gaspar" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else "0.0.0"


def find_iscc() -> Path | None:
    env_path = os.environ.get("INNO_SETUP_ISCC")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 5" / "ISCC.exe",
    ]
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        # O winget instala o Inno Setup por usuario em %LOCALAPPDATA%\Programs.
        candidates.insert(0, Path(local_appdata) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def run(command: list[str]) -> None:
    print(">>", " ".join(command))
    subprocess.run(command, cwd=str(ROOT), check=True)


def clean_outputs() -> None:
    for target in (DIST, WORK):
        if target.exists():
            print(f"Limpando {target}")
            shutil.rmtree(target)


def build_spec(spec: Path) -> None:
    if not spec.exists():
        raise FileNotFoundError(f"Spec nao encontrado: {spec}")
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(WORK),
            str(spec),
        ]
    )


def verify_artifacts(need_app: bool, need_blackbox: bool) -> bool:
    ok = True
    checks = [
        (need_app, DIST / "gaspar" / "gaspar.exe", "Gaspar"),
        (need_blackbox, DIST / "gaspar_blackbox" / "gaspar_blackbox.exe", "BlackBox"),
    ]
    for needed, path, label in checks:
        if not needed:
            continue
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"OK {label}: {path} ({size_mb:.1f} MB)")
        else:
            print(f"ERRO: {label} nao encontrado em {path}", file=sys.stderr)
            ok = False
    return ok


def build_installer(version: str) -> int:
    if not ISS_FILE.exists():
        print(f"ERRO: script Inno Setup nao encontrado: {ISS_FILE}", file=sys.stderr)
        return 1
    iscc = find_iscc()
    if iscc is None:
        print(
            "\nInno Setup nao encontrado.\n"
            "Instale o Inno Setup 6 (https://jrsoftware.org/isdl.php) e rode novamente,\n"
            "ou defina INNO_SETUP_ISCC com o caminho do ISCC.exe.\n"
            "Os executaveis em dist/windows ja estao prontos.",
            file=sys.stderr,
        )
        return 2
    try:
        run(
            [
                str(iscc),
                f"/DMyAppVersion={version}",
                f"/DMySourceRoot={ROOT}",
                str(ISS_FILE),
            ]
        )
    except subprocess.CalledProcessError as exc:
        print(f"ERRO ao compilar o instalador: {exc}", file=sys.stderr)
        return 1

    installer = ROOT / "dist" / "installer" / f"GasparSetup-{version}.exe"
    if installer.exists():
        size_mb = installer.stat().st_size / (1024 * 1024)
        print(f"Instalador: {installer} ({size_mb:.1f} MB)")
        return 0
    print(f"ERRO: instalador esperado nao foi gerado: {installer}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Windows do Gaspar.")
    parser.add_argument("--app-only", action="store_true", help="compila somente o Gaspar")
    parser.add_argument("--blackbox-only", action="store_true", help="compila somente o BlackBox")
    parser.add_argument("--no-installer", action="store_true", help="nao gera o instalador Inno Setup")
    parser.add_argument("--installer-only", action="store_true", help="apenas gera o instalador")
    parser.add_argument("--no-clean", action="store_true", help="nao apaga dist/ e build/ anteriores")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("ERRO: este script gera executaveis Windows; rode no Windows.", file=sys.stderr)
        return 1
    if args.app_only and args.blackbox_only:
        print("ERRO: use apenas um entre --app-only e --blackbox-only.", file=sys.stderr)
        return 1
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(
            "PyInstaller nao instalado. Rode: python -m pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1
    if not all((ASSETS / name).exists() for name in ("gaspar.ico", "gaspar.png", "gaspar_flutuando.gif")):
        print(f"ERRO: ativos incompletos em {ASSETS}", file=sys.stderr)
        return 1

    version = read_version()
    need_app = not args.blackbox_only
    need_blackbox = not args.app_only

    try:
        if args.installer_only:
            if not verify_artifacts(True, True):
                print("ERRO: compile o app e o BlackBox antes do instalador.", file=sys.stderr)
                return 1
        else:
            if not args.no_clean:
                clean_outputs()
            if need_app:
                build_spec(SPEC_APP)
            if need_blackbox:
                build_spec(SPEC_BLACKBOX)
            if not verify_artifacts(need_app, need_blackbox):
                return 1
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERRO durante a compilacao: {exc}", file=sys.stderr)
        return 1

    if args.no_installer:
        print("Instalador ignorado (--no-installer).")
        return 0
    if not (need_app and need_blackbox):
        print("Instalador ignorado: ele inclui o Gaspar e o BlackBox.")
        return 0
    return build_installer(version)


if __name__ == "__main__":
    raise SystemExit(main())
