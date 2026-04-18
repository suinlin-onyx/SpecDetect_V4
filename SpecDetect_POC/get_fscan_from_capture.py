#!/usr/bin/env python
"""从 rmcp_proxy capture 获取最新 FSCAN 数据"""
import json
import struct
from pathlib import Path

def get_latest_fscan_from_capture():
    """从 rmcp_proxy capture 获取最新的 FSCAN 数据"""
    capture_dir = Path(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\capture")

    # 找最新的 capture 文件
    capture_files = sorted(capture_dir.glob("capture_*.json"), key=lambda p: p.stat().st_mtime)
    if not capture_files:
        return None

    latest = capture_files[-1]
    print(f"读取: {latest.name}")

    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 找 S->C 的 FSCAN 数据
    for entry in reversed(data):
        if entry.get('direction') == 'S->C' and entry.get('data_type') == 'SIMPLE_FSCAN':
            fscan = entry.get('fscan', {})
            levels = fscan.get('levels', [])

            if levels and len(levels) >= 512:
                print(f"找到 FSCAN 数据: {len(levels)} 点")
                print(f"nBdType: {fscan.get('nBdType')}")
                print(f"nArrays: {fscan.get('nArrays')}")
                print(f"counters: {fscan.get('counters')}")
                print(f"levels[0]: {levels[0]}")
                print(f"levels[255]: {levels[255]}")
                print(f"levels[511]: {levels[511]}")
                return levels

    return None

if __name__ == '__main__':
    levels = get_latest_fscan_from_capture()
    if levels:
        print(f"\n成功获取 {len(levels)} 点数据")
    else:
        print("未找到 FSCAN 数据")