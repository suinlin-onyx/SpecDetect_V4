# Win7 runtime hook for SOAPProxy
# Adds exe directory to DLL search path for api-ms-win-core-*.dll

import ctypes
import os
import sys

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)

_add_dll = getattr(_k32, 'AddDllDirectory', None)
if _add_dll:
    exe_dir = os.path.dirname(sys.executable)
    _add_dll(exe_dir)
