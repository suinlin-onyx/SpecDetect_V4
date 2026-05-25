# -*- coding: utf-8 -*-
"""Runtime hook: 设置 DLL 搜索路径以支持 Win7 系统"""
import sys
import os
import ctypes

if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))

    # 将 exe 目录和 _MEIPASS 添加到 DLL 搜索路径（Win7 兼容）
    k32 = ctypes.WinDLL('kernel32')
    AddDllDirectory = getattr(k32, 'AddDllDirectory', None)
    if AddDllDirectory:
        k32.AddDllDirectory(exe_dir)
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            k32.AddDllDirectory(meipass)
