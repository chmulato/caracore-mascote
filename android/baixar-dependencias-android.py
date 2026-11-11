#!/usr/bin/env python3
"""
Baixa as dependências do Android SDK necessárias para o build Maven do android-sms-enviar.

Requer: Python 3.6+, Android SDK (Android Studio ou cmdline-tools).
Se sdkmanager não existir, use --install-cmdline-tools para baixar os Command Line Tools.

Uso:
  python baixar-dependencias-android.py
  python baixar-dependencias-android.py --sdk-root=C:/Android/sdk --accept-licenses
  python baixar-dependencias-android.py --install-cmdline-tools
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

# Versão dos cmdline-tools (dl.google.com); atualize se o download falhar com 404.
# Ver: https://developer.android.com/studio#command-tools
_CMDLINE_VERSION = "13114758"
_CMDLINE_URLS = {
    "Windows": f"https://dl.google.com/android/repository/commandlinetools-win-{_CMDLINE_VERSION}_latest.zip",
    "Darwin": f"https://dl.google.com/android/repository/commandlinetools-mac-{_CMDLINE_VERSION}_latest.zip",
    "Linux": f"https://dl.google.com/android/repository/commandlinetools-linux-{_CMDLINE_VERSION}_latest.zip",
}


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _get_sdk_root(sdk_root: str | None) -> Path:
    if sdk_root:
        return Path(sdk_root).resolve()
    env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if env:
        return Path(env).resolve()
    if _is_windows():
        local = os.environ.get("LOCALAPPDATA", "")
        return Path(local) / "Android" / "Sdk" if local else Path("C:/Android/Sdk")
    return Path.home() / "Android" / "Sdk"


def _find_sdkmanager(sdk_root: Path) -> Path | None:
    for base, names in [
        ("cmdline-tools/latest/bin", ("sdkmanager.bat", "sdkmanager")),
        ("tools/bin", ("sdkmanager.bat", "sdkmanager")),
    ]:
        for name in names:
            p = sdk_root / base / name
            if p.exists():
                return p
    return None


def _run_sdkmanager(sdk_root: Path, sdkmanager: Path, args: list[str], input_data: bytes | None = None) -> int:
    base = [str(sdkmanager), f"--sdk_root={sdk_root}"]
    cmd = base + args
    if _is_windows() and (str(sdkmanager).endswith(".bat") or str(sdkmanager).endswith(".cmd")):
        cmd = ["cmd", "/c"] + cmd
    r = subprocess.run(cmd, input=input_data, encoding="utf-8" if input_data is None else None)
    return r.returncode


def _ensure_tools_source_properties(sdk_root: Path) -> None:
    tools_dir = sdk_root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    prop = tools_dir / "source.properties"
    if not prop.exists():
        prop.write_text("Pkg.Revision=1\n", encoding="utf-8")
        print(f"Criado: {prop}")


def _read_platform_from_pom(pom: Path) -> int:
    if not pom.exists():
        return 35
    text = pom.read_text(encoding="utf-8")
    m = re.search(r"<android\.platform>\s*(\d+)\s*</android\.platform>", text)
    return int(m.group(1)) if m else 35


def _download_cmdline_tools(sdk_root: Path) -> bool:
    url = _CMDLINE_URLS.get(platform.system(), _CMDLINE_URLS.get("Linux"))
    print(f"Baixando: {url}")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=120) as resp:
            if resp.status != 200:
                print(f"Erro HTTP {resp.status}", file=sys.stderr)
                return False
            data = resp.read()
    except Exception as e:
        print(f"Erro ao baixar: {e}", file=sys.stderr)
        return False

    dest_dir = sdk_root / "cmdline-tools" / "latest"
    if dest_dir.exists():
        print(f"Removendo instalacao antiga: {dest_dir}")
        shutil.rmtree(dest_dir)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="android-cmdline-"))
    try:
        zip_path = tmp / "cmdline.zip"
        zip_path.write_bytes(data)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)
        # O zip pode ter: (a) bin,lib na raiz; (b) um unico diretorio (ex. cmdline-tools) com bin,lib
        items = [p for p in tmp.iterdir() if p.name != "cmdline.zip"]
        if len(items) == 1 and items[0].is_dir():
            source = items[0]
        else:
            source = tmp
        dest_dir.mkdir(parents=True, exist_ok=True)
        for c in source.iterdir():
            shutil.move(str(c), str(dest_dir / c.name))
        print(f"Command Line Tools instalados em: {dest_dir}")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Baixa dependências do Android SDK para android-sms-enviar (build Maven)."
    )
    ap.add_argument("--sdk-root", help="Caminho do Android SDK (ou ANDROID_HOME)")
    ap.add_argument("--platform", type=int, help="API level (padrão: lido do pom.xml ou 35)")
    ap.add_argument("--accept-licenses", action="store_true", help="Aceitar licenças do SDK automaticamente")
    ap.add_argument(
        "--install-cmdline-tools",
        action="store_true",
        help="Se sdkmanager não existir, baixar e instalar Android Command Line Tools",
    )
    args = ap.parse_args()

    sdk_root = _get_sdk_root(args.sdk_root)
    print(f"SDK root: {sdk_root}")

    sdkmanager = _find_sdkmanager(sdk_root)
    if not sdkmanager:
        if args.install_cmdline_tools:
            if not sdk_root.exists():
                sdk_root.mkdir(parents=True, exist_ok=True)
            if not _download_cmdline_tools(sdk_root):
                return 1
            sdkmanager = _find_sdkmanager(sdk_root)
        if not sdkmanager:
            print("sdkmanager não encontrado.", file=sys.stderr)
            print("Instale o Android SDK Command Line Tools:", file=sys.stderr)
            print("  Android Studio: Settings > Android SDK > SDK Tools > Android SDK Command-line Tools", file=sys.stderr)
            print("  Ou: https://developer.android.com/studio#command-tools", file=sys.stderr)
            print("  Ou execute: python baixar-dependencias-android.py --install-cmdline-tools", file=sys.stderr)
            return 1

    script_dir = Path(__file__).resolve().parent
    pom = script_dir / "pom.xml"
    platform_api = args.platform if args.platform is not None else _read_platform_from_pom(pom)

    _ensure_tools_source_properties(sdk_root)

    if args.accept_licenses:
        print("Aceitando licenças do SDK...")
        _run_sdkmanager(sdk_root, sdkmanager, ["--licenses"], input_data=b"y\n" * 30)

    packages = [
        "platform-tools",
        "build-tools;27.0.3",
        f"platforms;android-{platform_api}",
    ]
    print("Instalando:", ", ".join(packages))
    ret = _run_sdkmanager(sdk_root, sdkmanager, packages)
    if ret != 0:
        return ret
    print("Concluído. Execute build.bat para compilar o APK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
