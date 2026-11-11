# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec do Gaspar BlackBox (Linux, onedir).
# Build: bash packaging/linux/build_linux.sh

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]
ASSETS = ROOT / "assets"

a = Analysis(
    [str(ROOT / "run_blackbox.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ASSETS), "assets")],
    hiddenimports=["PIL.Image", "PIL.ImageTk"],
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
    name="gaspar_blackbox",
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
    name="gaspar_blackbox",
)
