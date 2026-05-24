# -*- coding: utf-8 -*-
"""许可证生成工具

用法:
    python gen_license.py                      # 生成到 config/license.dat，设备名=主机名
    python gen_license.py --embed              # 同时生成嵌入式 _data.py 模块（打包进 exe）
    python gen_license.py --name "设备A"        # 指定设备名
    python gen_license.py --merge               # 追加到已有许可证
    python gen_license.py --show                # 查看当前硬件指纹
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from license.hardware import collect_fingerprint
from license.manager import generate_license, hash_fingerprint

_EMBED_MODULE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'license', '_data.py')


def show_fingerprint():
    fp = collect_fingerprint()
    hashed = hash_fingerprint(fp)
    print('当前设备硬件指纹：')
    for key in ('motherboard', 'disk', 'cpu', 'mac'):
        raw = fp.get(key) or 'N/A'
        h = hashed.get(key)
        h_display = f'SHA256:{h[:16]}...' if h else '不可用'
        print(f'  {key}: {str(raw)[:40]:<40s}  ({h_display})')


def write_embed_module(license_path: str):
    """读取 license.dat 内容，写入 _data.py 模块"""
    if not os.path.exists(license_path):
        print(f'错误: 许可证文件不存在: {license_path}', file=sys.stderr)
        sys.exit(1)

    with open(license_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    content = (
        '# -*- coding: utf-8 -*-\n'
        '# 自动生成，请勿手动修改\n'
        '# 生成命令: python gen_license.py --embed\n'
        '#\n'
        f'LICENSE_DATA = {json.dumps(data, indent=4, ensure_ascii=False)}\n'
    )

    os.makedirs(os.path.dirname(_EMBED_MODULE), exist_ok=True)
    with open(_EMBED_MODULE, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'嵌入式许可证已生成: {_EMBED_MODULE}')
    print('  → 打包 exe 时将自动编译到程序中')


def main():
    parser = argparse.ArgumentParser(description='SpecDetect_Atom 许可证生成工具')
    parser.add_argument('--name', '-n', type=str, default='', help='设备名称')
    parser.add_argument('--merge', '-m', action='store_true', help='追加到已有许可证')
    parser.add_argument('--output', '-o', type=str, default=None, help='许可证输出路径')
    parser.add_argument('--show', '-s', action='store_true', help='仅显示当前硬件指纹')
    parser.add_argument('--embed', '-e', action='store_true',
                        help='同时生成嵌入式 _data.py 模块（编译进 exe，无需外部 license.dat）')
    args = parser.parse_args()

    if args.show:
        show_fingerprint()
        return

    try:
        path, current_fp = generate_license(
            license_path=args.output,
            device_name=args.name,
            merge=args.merge
        )
        print(f'许可证已生成: {path}')
        hostname = args.name or __import__('socket').gethostname()
        print(f'设备名: {hostname}')
        print('已注册硬件指纹 (SHA256):')
        for key in ('motherboard', 'disk', 'cpu', 'mac'):
            h = current_fp.get(key)
            h_display = f'{h[:32]}...' if h else '不可用（硬件信息获取失败）'
            print(f'  {key}: {h_display}')

        if args.embed:
            write_embed_module(path)
    except ValueError as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
