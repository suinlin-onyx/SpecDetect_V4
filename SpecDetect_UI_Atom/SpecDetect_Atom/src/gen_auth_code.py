# -*- coding: utf-8 -*-
"""离线授权码生成工具（私密 — 不公开/不打包分发）

双击运行，输入客户标识，生成对应授权码。
不同标识 = 不同码，可在任意机器上激活 SGAtom。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from license.crypto import generate_auth_code


def main():
    print()
    print("=" * 50)
    print("  SGAtom 离线授权码生成器")
    print("=" * 50)
    print()

    label = input("  请输入客户标识（名称或编号）: ").strip()
    if not label:
        print()
        print("  标识不能为空。")
        input("  按任意键退出...")
        return

    code = generate_auth_code(label)

    print()
    print(f"  客户标识: {label}")
    print()
    print(f"  授权码:   {code}")
    print()
    print("  - 该授权码可在任意一台设备的 SGAtom 上激活")
    print("  - 不同标识对应不同授权码，请记录对应关系")
    print("  - 请通过安全渠道发送，勿公开传播")
    print()
    print("=" * 50)
    input("  按任意键退出...")


if __name__ == "__main__":
    main()
