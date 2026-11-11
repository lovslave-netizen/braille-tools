# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['글자수세기_web.py'],
    pathex=[],
    binaries=[],
    datas=[('jydbt', 'jydbt'), ('글자수세기.py', '.'), ('역점역기.py', '.')],
    hiddenimports=['tkinter', '_tkinter', 'tkinter.filedialog', 'tkinter.messagebox', 'tkinter.ttk', 'tkinter.font'],
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
    name='글자수세기_web',
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
)
