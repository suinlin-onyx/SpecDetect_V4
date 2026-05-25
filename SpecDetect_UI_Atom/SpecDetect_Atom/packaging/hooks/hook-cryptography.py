# Minimal hook for cryptography compatible with PyInstaller 4.10
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules('cryptography')
datas = copy_metadata('cryptography')
