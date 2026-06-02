# -*- coding: utf-8 -*-
"""Cython 编译 license 模块为 .pyd（Windows 原生扩展）

用法:
    python setup_cython.py build_ext --inplace

输出:
    src/license/manager.cp37-win_amd64.pyd
    src/license/hardware.cp37-win_amd64.pyd
"""

import os
import sys
from setuptools import setup
from Cython.Build import cythonize

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
_LICENSE_DIR = os.path.join(_SRC_DIR, 'license')

setup(
    name='specdetect_license',
    ext_modules=cythonize(
        [
            os.path.join(_LICENSE_DIR, 'manager.py'),
            os.path.join(_LICENSE_DIR, 'hardware.py'),
            os.path.join(_LICENSE_DIR, 'crypto.py'),
        ],
        compiler_directives={
            'language_level': '3',
            'boundscheck': False,
            'wraparound': False,
        },
    ),
    options={
        'build_ext': {
            'build_lib': _LICENSE_DIR,
            'build_temp': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_cython'),
        }
    },
    zip_safe=False,
)
