# -*- mode: python ; coding: utf-8 -*-
import glob as _glob
import os as _os
import re as _re

block_cipher = None

_spec_dir = os.path.abspath(os.path.dirname(SPEC))

# 从 version.py 读取版本号（与 build.bat 对齐）
_version_path = os.path.join(_spec_dir, '..', '..', '..', 'SpecDetect_UI_Atom', 'SpecDetect_Atom', 'src', 'version.py')
_proxy_version = '1.2.0'
if os.path.exists(_version_path):
    try:
        with open(_version_path, 'r', encoding='utf-8') as _f:
            _content = _f.read()
        _m = _re.search(r'PROXY_VERSION\s*=\s*"([^"]+)"', _content)
        if _m:
            _proxy_version = _m.group(1)
    except Exception:
        pass

# Collect runtime DLLs for Win7 app-local deployment (same as SGAtom)
_runtime_dir = os.path.join(_spec_dir, '..', '..', '..', 'SpecDetect_UI_Atom', 'SpecDetect_Atom', 'runtime')
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
    runtime_hooks=[_os.path.join(_spec_dir, '..', 'runtime_hook.py')],
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
    name=f'SOAPProxy_v{_proxy_version}',
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
