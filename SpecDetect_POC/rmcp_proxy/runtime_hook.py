# Win7 runtime hook for rmcp_proxy
# 注册 DLL 搜索路径：exe 目录 + runtime/ 子目录
import ctypes
import os
import sys

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_add_dll = getattr(_k32, 'AddDllDirectory', None)
if _add_dll:
    exe_dir = os.path.dirname(sys.executable)
    _add_dll(exe_dir)
    # 同时注册 runtime/ 子目录（部署时备用）
    runtime_dir = os.path.join(exe_dir, 'runtime')
    if os.path.isdir(runtime_dir):
        _add_dll(runtime_dir)
