# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\outros\\mascote_py\\mascote.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\outros\\mascote_py\\mascote.gif', '.'), ('D:\\outros\\mascote_py\\mascote.ico', '.'), ('D:\\outros\\mascote_py\\boneco.ico', '.')],
    hiddenimports=['pyautogui', 'PIL', 'PIL.Image', 'PIL.ImageTk'],
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
    name='mascote',
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
    icon=['mascote.ico'],
)
