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

# D6, ressalva da auditoria da Fase Alpha. A lista fixa abaixo nao e o que poe os
# modulos dentro do executavel: o PyInstaller enxerga o import ate dentro de
# funcao, e e por isso que gaspar.sms.audit, .e2e, .signing e .templates saem no
# pacote sem estar listados aqui. Lista fixa e colete salva-vidas para o modulo
# que ainda nao e importado por ninguem, que e o caso da mensageria 2.0: ela so
# e chamada pelo motorista escolhido na configuracao. E como o import vive
# dentro de um try que apenas desliga a peca em silencio, um executavel sem o
# modulo nao da erro - chega ao balcao com a mensageria apagada. Por isso a
# prova e no pacote gerado: python packaging/verifica_pacote.py

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

# Lista fixa: os meios da mensageria 2.0 sao escolhidos por origem na
# configuracao. tests/test_packaging_manifest.py cobra esta lista contra o
# conteudo de gaspar/messaging nos dois specs.
hiddenimports += [
    "gaspar.messaging",
    "gaspar.messaging.config",
    "gaspar.messaging.convivencia",
    "gaspar.messaging.credentials",
    "gaspar.messaging.dispatcher",
    "gaspar.messaging.errors",
    "gaspar.messaging.local_api",
    "gaspar.messaging.model",
    "gaspar.messaging.service",
    "gaspar.messaging.store",
    "gaspar.messaging.transport",
    "gaspar.messaging.transports",
    "gaspar.messaging.transports.android_lan",
    "gaspar.messaging.transports.factory",
    "gaspar.messaging.transports.loopback",
    "gaspar.messaging.transports.smtp_email",
    "gaspar.messaging.vault",
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
