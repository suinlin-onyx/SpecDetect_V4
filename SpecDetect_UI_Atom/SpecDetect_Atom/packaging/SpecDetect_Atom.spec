# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SGAtom (SpecGuardAtom)

Usage:
    pyinstaller SpecDetect_Atom.spec
"""
import glob as _glob
import os as _os

block_cipher = None

# Collect all runtime DLLs for Win7 app-local deployment
# SPECPATH is provided by PyInstaller (spec file's directory)
try:
    _spec_dir = os.path.abspath(SPECPATH)
except NameError:
    _spec_dir = os.path.abspath('.')

# runtime dir is at project root (parent of packaging)
_runtime_dir = os.path.join(_spec_dir, '..', 'runtime')
_binaries = []
if os.path.isdir(_runtime_dir):
    for _dll in _glob.glob(os.path.join(_runtime_dir, '*.dll')):
        _binaries.append((_dll, '.'))

a = Analysis(
    ['../src/main.py'],
    pathex=[],
    binaries=_binaries,
    datas=[
        ('../config', 'config'),
        ('../src/preset/templates', 'preset/templates'),
    ],
    hiddenimports=[
        'atom.service',
        'atom.stream.server',
        'atom.rmcp.client',
        'atom.session_manager',
        'atom.soap.server',
        'atom.config',
        'atom.validator',
        'atom.fscan_processor',
        'atom.stream.frame',
        'atom.rmcp.frame',
        'preset.device_preset',
        'preset.templates',
        'log.logger',
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
    runtime_hooks=[_os.path.join(_spec_dir, '..', 'src', 'runtime_hook.py')],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
        'api-ms-win-core-path-l1-1-0',
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
    name='SGAtom',
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
    version='version_info.txt',
    icon='../src/res/icon/sg_atom.ico',
)
