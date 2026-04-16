#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步采集 rmcp + streamsrc 数据
同时启动两个监听器，收集配对数据用于对比分析
"""

import subprocess
import threading
import time
import os
import sys
from datetime import datetime

# 设置路径
EXPERIMENTAL_DIR = os.path.dirname(os.path.abspath(__file__))
RMCPDIR = os.path.join(os.path.dirname(EXPERIMENTAL_DIR), 'rmcp_proxy')
LOG_DIR = os.path.join(EXPERIMENTAL_DIR, 'logs')

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)


def run_streamsrc_listener(duration=20):
    """运行 streamsrc 监听器"""
    print("[*] 启动 streamsrc 监听器...")
    listener_path = os.path.join(EXPERIMENTAL_DIR, 'atom_streamsrc_listener.py')

    # 使用 timeout 限制运行时间
    cmd = [
        sys.executable,
        listener_path
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        cwd=EXPERIMENTAL_DIR,
        timeout=duration + 10
    )

    print("[+] streamsrc 监听器完成")
    return result.stdout, result.stderr


def run_rmcp_proxy(duration=20):
    """运行 rmcp_proxy"""
    print("[*] 启动 rmcp_proxy...")
    proxy_path = os.path.join(RMCPDIR, 'rmcp_proxy.py')

    # 使用 timeout 限制运行时间
    cmd = [
        sys.executable,
        proxy_path
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        cwd=RMCPDIR,
        timeout=duration + 10
    )

    print("[+] rmcp_proxy 完成")
    return result.stdout, result.stderr


def main():
    print("=" * 70)
    print("同步采集 rmcp + streamsrc 数据")
    print("=" * 70)

    DURATION = 65  # streamsrc 采集时长 (秒)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f"\n[*] 采集开始: {timestamp}")
    print(f"[*] streamsrc 采集时长: {DURATION} 秒")

    start_time = time.time()

    print("\n" + "-" * 70)
    print("Step 1: 启动 rmcp_proxy (后台)")
    print("-" * 70)

    rmcp_proc = subprocess.Popen(
        [sys.executable, os.path.join(RMCPDIR, 'rmcp_proxy.py')],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=RMCPDIR,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(f"[+] rmcp_proxy 已启动 (PID={rmcp_proc.pid})")
    time.sleep(2)  # 等待启动

    print("\n" + "-" * 70)
    print("Step 2: 启动 streamsrc_listener")
    print("-" * 70)

    listener_result = subprocess.run(
        [sys.executable, os.path.join(EXPERIMENTAL_DIR, 'atom_streamsrc_listener.py')],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        cwd=EXPERIMENTAL_DIR,
        timeout=DURATION + 20
    )

    print(listener_result.stdout)
    if listener_result.stderr:
        print(f"[!] streamsrc_listener stderr: {listener_result.stderr[-500:]}")

    print("\n" + "-" * 70)
    print("Step 3: 停止 rmcp_proxy")
    print("-" * 70)

    rmcp_proc.terminate()
    try:
        rmcp_stdout, rmcp_stderr = rmcp_proc.communicate(timeout=5)
        if rmcp_stdout:
            print(rmcp_stdout[-3000:] if len(rmcp_stdout) > 3000 else rmcp_stdout)
    except subprocess.TimeoutExpired:
        rmcp_proc.kill()
        rmcp_stdout, rmcp_stderr = rmcp_proc.communicate()
        print("[!] rmcp_proxy 被强制终止")

    elapsed = time.time() - start_time
    print(f"\n[+] 采集完成，耗时 {elapsed:.1f} 秒")

    # 列出生成的日志文件
    print("\n" + "-" * 70)
    print("生成的日志文件:")
    print("-" * 70)

    log_files = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.log')],
                      key=lambda x: os.path.getmtime(os.path.join(LOG_DIR, x)),
                      reverse=True)[:10]

    for f in log_files:
        path = os.path.join(LOG_DIR, f)
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%H:%M:%S')
        print(f"  {f} ({size:,} bytes, {mtime})")

    # rmcp 日志
    rmcp_log_dir = os.path.join(RMCPDIR, 'capture')
    if os.path.exists(rmcp_log_dir):
        rmcp_logs = sorted([f for f in os.listdir(rmcp_log_dir) if f.endswith('.log')],
                          key=lambda x: os.path.getmtime(os.path.join(rmcp_log_dir, x)),
                          reverse=True)[:5]
        print(f"\n  rmcp_proxy 日志:")
        for f in rmcp_logs:
            path = os.path.join(rmcp_log_dir, f)
            size = os.path.getsize(path)
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%H:%M:%S')
            print(f"    {f} ({size:,} bytes, {mtime})")

    print("\n" + "=" * 70)
    print("下一步: 使用 compare_logs.py 分析同步采集的数据")
    print("=" * 70)


if __name__ == '__main__':
    main()
