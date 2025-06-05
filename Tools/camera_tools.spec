# -*- mode: python ; coding: utf-8 -*-
# camera_tools.spec
# PyInstaller 規格檔案用於打包相機標定工具

import os

block_cipher = None

# 內參標定工具
intrinsic_a = Analysis(
    ['內參棋盤格計算可視化工具.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.figure',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'threading',
        'datetime',
        'glob',
        'os'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'tensorflow',
        'pandas',
        'scipy',
        'sklearn'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 外參標定工具
extrinsic_a = Analysis(
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
    excludes=[
        'torch',
        'tensorflow',
        'scipy',
        'sklearn'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 合併分析結果
MERGE((intrinsic_a, '內參標定工具', '內參標定工具'), 
      (extrinsic_a, '外參標定工具', '外參標定工具'))

# 內參標定工具可執行檔
intrinsic_pyz = PYZ(intrinsic_a.pure, intrinsic_a.zipped_data, cipher=block_cipher)

intrinsic_exe = EXE(
    intrinsic_pyz,
    intrinsic_a.scripts,
    [],
    exclude_binaries=True,
    name='相機內參標定工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 使用 CustomTkinter 預設圖示
)

# 外參標定工具可執行檔
extrinsic_pyz = PYZ(extrinsic_a.pure, extrinsic_a.zipped_data, cipher=block_cipher)

extrinsic_exe = EXE(
    extrinsic_pyz,
    extrinsic_a.scripts,
    [],
    exclude_binaries=True,
    name='相機外參標定工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='640.png' if os.path.exists('640.png') else None
)

# 內參工具打包
intrinsic_coll = COLLECT(
    intrinsic_exe,
    intrinsic_a.binaries,
    intrinsic_a.zipfiles,
    intrinsic_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='相機內參標定工具'
)

# 外參工具打包
extrinsic_coll = COLLECT(
    extrinsic_exe,
    extrinsic_a.binaries,
    extrinsic_a.zipfiles,
    extrinsic_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='相機外參標定工具'
)