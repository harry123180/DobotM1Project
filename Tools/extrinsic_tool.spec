# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['外參標定可視化工具.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'numpy',
        'cv2',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.cm',
        'matplotlib.colors',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.figure',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'pandas',
        'datetime',
        'platform'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='相機外參標定工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 使用 CustomTkinter 預設圖示
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='相機外參標定工具'
)
