#!/usr/bin/env python3
"""
SpecDetect_V4 服务重启脚本
Usage: python restart_services.py
"""
import subprocess
import time
import os
import sys

def run_cmd(cmd, desc):
    """执行命令并输出结果"""
    print(f"    {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"      成功")
        return True
    else:
        print(f"      {result.stdout.strip()}")
        return False

def main():
    print("=" * 50)
    print("SpecDetect_V4 服务重启脚本")
    print("=" * 50)

    # 停止服务
    print("\n[1/4] 停止服务...")

    run_cmd('cmd //c "taskkill /F /IM AtomSvcV3.exe"', '停止 AtomSvcV3')
    run_cmd('cmd //c "taskkill /F /IM python.exe"', '停止 python')

    print("\n[2/4] 等待服务停止...")
    time.sleep(2)

    # 启动服务
    print("\n[3/4] 启动 AtomSvcV3...")

    # AtomSvcV3 路径 - 需要用户确认
    atom_path = r"D:\arvin\claude_workspace\RXAtomSvcV3\AtomSvcV3.exe"
    if os.path.exists(atom_path):
        subprocess.Popen(atom_path)
        print(f"      AtomSvcV3 启动命令已发送")
    else:
        print(f"      [!] AtomSvcV3 路径不存在: {atom_path}")
        print(f"      请手动启动 AtomSvcV3")

    print("\n[4/4] 启动 rmcp_proxy...")

    rmcp_path = r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\rmcp_proxy.py"
    if os.path.exists(rmcp_path):
        subprocess.Popen(["python", rmcp_path])
        print(f"      rmcp_proxy 启动命令已发送")
    else:
        print(f"      [!] rmcp_proxy 路径不存在: {rmcp_path}")
        print(f"      请手动启动 rmcp_proxy")

    print("\n" + "=" * 50)
    print("服务重启完成")
    print("=" * 50)

if __name__ == '__main__':
    main()
