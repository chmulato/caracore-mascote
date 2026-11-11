# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec do Gaspar (Linux, onedir).
# Build: bash packaging/linux/build_linux.sh

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]
ASSETS = ROOT / "assets"

hiddenimports = [
    "pyautogui",
    "pyscreeze",
    "pygetwindow",
    "pymsgbox",
    "pytweening",
    "mouseinfo",
    "psutil",
    "PIL.Image",
    "PIL.ImageTk",
]
for module in ("pystray", "Xlib"):
    try:
        hiddenimports += collect_submodules(module)
    except Exception:
        pass

# Lista fixa: a ponte de SMS e importada em tempo de execucao pelo Gaspar.
hiddenimports += [
    "gaspar.sms",
    "gaspar.sms.bridge",
    "gaspar.sms.client",
    "gaspar.sms.config",
    "gaspar.sms.crypto",
    "gaspar.sms.discovery",
    "gaspar.sms.network",
    "gaspar.sms.protocol",
    "gaspar.sms.qr",
    "gaspar.sms.server",
    "gaspar.sms.store",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ASSETS), "assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="gaspar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="gaspar",
)
