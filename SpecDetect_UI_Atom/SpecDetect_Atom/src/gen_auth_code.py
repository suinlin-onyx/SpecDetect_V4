# -*- coding: utf-8 -*-
"""离线授权码生成工具（私密 — 不公开/不打包分发）

双击运行，显示授权码，按任意键退出。
授权码是通用的（与设备无关），可在任意机器上激活 SGAtom。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from license.crypto import generate_auth_code


def main():
    code = generate_auth_code()

    print()
    print("=" * 40)
    print(f"  {code}")
    print("=" * 40)
    print()
    input("按任意键退出...")


if __name__ == "__main__":
    main()
