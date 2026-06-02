# -*- coding: utf-8 -*-
"""离线授权码生成工具（私密 — 不公开/不打包分发）

用法:
    python gen_auth_code.py                      # 生成本机授权码
    python gen_auth_code.py --name "设备A"        # 指定设备名
    python gen_auth_code.py --fingerprint <指纹>  # 手动输入指纹（远程授权）

此工具仅供管理员离线使用，与 SGAtom 共享 MASTER_SECRET_KEY。
生成的授权码 20 字符，人工可输入。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from license.hardware import collect_fingerprint
from license.manager import hash_fingerprint
from license.crypto import generate_auth_code


def main():
    parser = argparse.ArgumentParser(description="离线授权码生成器（私密工具）")
    parser.add_argument("--name", "-n", type=str, default="", help="设备名称，默认取主机名")
    parser.add_argument("--fingerprint", "-f", type=str, default=None, metavar="JSON",
                        help="手动输入硬件指纹 JSON（用于远程授权）")
    parser.add_argument("--show-fingerprint", "-s", action="store_true",
                        help="仅显示当前设备硬件指纹（用于远程授权场景）")
    args = parser.parse_args()

    if args.show_fingerprint:
        fp = collect_fingerprint()
        print("硬件指纹（发给管理员生成授权码）：")
        print(json.dumps(fp, indent=2, ensure_ascii=False))
        print()
        hashed = hash_fingerprint(fp)
        print("SHA256 哈希：")
        for k in ("motherboard", "disk", "cpu", "mac"):
            h = hashed.get(k)
            print(f"  {k}: {h[:32] if h else 'N/A'}...")
        return

    import socket

    if args.fingerprint:
        try:
            fp = json.loads(args.fingerprint)
        except json.JSONDecodeError as e:
            print(f"错误: 指纹 JSON 格式不正确: {e}", file=sys.stderr)
            sys.exit(1)
        hostname = args.name or "远程设备"
        print(f"使用手动输入的指纹（远程授权）")
    else:
        fp = collect_fingerprint()
        hostname = args.name or socket.gethostname()

    code = generate_auth_code(hostname, fp)

    print(f"设备名: {hostname}")
    print()
    print("=" * 40)
    print(f"  授权码: {code}")
    print("=" * 40)
    print()
    print("请将此授权码发给用户在 SGAtom 中输入激活。")

    hashed = hash_fingerprint(fp)
    print()
    print("指纹哈希（仅供参考）：")
    for k in ("motherboard", "disk", "cpu", "mac"):
        h = hashed.get(k)
        print(f"  {k}: {h[:32] if h else 'N/A'}...")


if __name__ == "__main__":
    main()
