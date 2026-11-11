# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec do Gaspar (Windows, onedir).
# Build: python packaging/windows/build_windows.py

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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "gaspar.ico"),
    version=str(ROOT / "packaging" / "windows" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="gaspar",
)
