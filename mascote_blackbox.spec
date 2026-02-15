# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para Mascote BlackBox (bloqueio de telemetria).
# Gera executável que solicita execução como Administrador (UAC).
# Build: pyinstaller mascote_blackbox.spec

import sys
from pathlib import Path

script_dir = Path(sys.argv[0]).resolve().parent

a = Analysis(
    [str(script_dir / "mascote_blackbox.py")],
    pathex=[],
    binaries=[],
    datas=[
        (str(script_dir / "mascote.ico"), "."),
    ],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name="mascote_blackbox",
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
    icon="mascote.ico",
    uac_admin=True,
)
