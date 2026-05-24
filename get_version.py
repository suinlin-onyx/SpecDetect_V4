# -*- coding: utf-8 -*-
"""版本解析工具"""
import re
import sys
import os

path = sys.argv[1] if len(sys.argv) > 1 else 'version.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

m1 = re.search(r'ATOM_VERSION\s*=\s*"([^"]+)"', content)
m2 = re.search(r'PROXY_VERSION\s*=\s*"([^"]+)"', content)

v1 = m1.group(1) if m1 else '1.2.6'
v2 = m2.group(1) if m2 else '1.1.8'

# 输出到文件（不带 SET 前缀）
env_path = os.path.join(os.path.dirname(path), '_version.env')
with open(env_path, 'w', encoding='utf-8') as f:
    f.write(f'ATOM_VERSION={v1}\n')
    f.write(f'PROXY_VERSION={v2}\n')