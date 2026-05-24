# -*- mode: python ; coding: utf-8 -*-
import glob as _glob
import os as _os

block_cipher = None

_spec_dir = os.path.abspath(os.path.dirname(SPEC))

# runtime dir is at project root (parent of packaging)
_runtime_dir = os.path.join(_spec_dir, '..', 'runtime')
_binaries = []
if os.path.isdir(_runtime_dir):
    for _dll in _glob.glob(os.path.join(_runtime_dir, '*.dll')):
        _binaries.append((_dll, '.'))

a = Analysis(
    ['../transparent_proxy.py'],
    pathex=[_spec_dir],
    binaries=_binaries,
    datas=[
        ('../config/proxy_settings.json', 'config'),
    ],
    hiddenimports=[
        'encodings',
        'encodings.aliases',
        'encodings.ascii',
        'encodings.latin_1',
        'encodings.mbcs',
        'encodings.utf_8',
        'encodings.utf_16',
        'encodings.utf_16_le',
        'encodings.utf_16_be',
        'encodings.utf_32',
        'encodings.utf_7',
        'encodings.cp437',
        'encodings.cp850',
        'encodings.cp1252',
        'encodings.idna',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SOAPProxy_v1.1.7',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
