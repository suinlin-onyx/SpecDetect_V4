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
    print("=" * 50)
    print("  SGAtom 离线授权码生成器")
    print("=" * 50)
    print()
    print("  授权码（请复制发给客户）：")
    print()
    print(f"    {code}")
    print()
    print("  - 该授权码可用于任意一台设备的 SGAtom 激活")
    print("  - 每台设备激活后生成独立的加密许可证")
    print("  - 请通过安全渠道发送，勿公开传播")
    print()
    print("=" * 50)
    input("  按任意键退出...")


if __name__ == "__main__":
    main()
