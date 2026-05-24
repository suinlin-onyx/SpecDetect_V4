# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for gen_license.exe
设备授权许可证生成工具（嵌入exe版）
"""

import os as _os
import sys as _sys

block_cipher = None

try:
    _spec_dir = _os.path.abspath(SPECPATH)
except NameError:
    _spec_dir = _os.path.abspath('.')

a = Analysis(
    [_os.path.join(_spec_dir, '..', 'src', 'gen_license.py')],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'license.manager',
        'license.hardware',
        'license._data',
        'license',
    ],
    hookspath=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='gen_license',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)