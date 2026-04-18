#!/usr/bin/env python
"""从抓包 JSON 中提取 FSCAN 数据并分析"""
import json
import struct
import sys
from pathlib import Path

def extract_fscan_from_capture(capture_file):
    """从抓包文件提取 FSCAN 数据"""
    with open(capture_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fscan_entries = []
    for entry in data:
        if entry.get('direction') == 'S->C' and entry.get('data_type') == 'SIMPLE_FSCAN':
            fscan_entries.append(entry)

    print(f"找到 {len(fscan_entries)} 条 FSCAN 数据")

    if not fscan_entries:
        return

    # 分析第一条完整数据
    entry = fscan_entries[0]
    print(f"\n=== 第一条 FSCAN 分析 ===")
    print(f"时间: {entry['timestamp']}")
    print(f"大小: {entry['size']} bytes")
    print(f"header: {entry['header']}")

    fscan = entry.get('fscan', {})
    print(f"\nFSCAN 字段:")
    print(f"  nBdType: {fscan.get('nBdType')}")
    print(f"  nArrays: {fscan.get('nArrays')}")
    print(f"  counters: {fscan.get('counters')}")
    print(f"  levels (前10点): {fscan.get('levels', [])[:10]}")

    # 分析原始 hex
    hex_str = entry.get('hex', '')
    if hex_str:
        raw_bytes = bytes.fromhex(hex_str)
        print(f"\n原始 hex ({len(raw_bytes)} bytes):")
        print(f"  前50字节 hex: {raw_bytes[:50].hex()}")

        # 解析 RMCPTP 头
        if len(raw_bytes) >= 18:
            dw_length = struct.unpack('<I', raw_bytes[0:4])[0]
            tm_stamp = struct.unpack('<Q', raw_bytes[4:12])[0]
            n_version = struct.unpack('>H', raw_bytes[12:14])[0]
            n_msg_type = raw_bytes[14]
            n_flags = raw_bytes[15]
            n_check_sum = struct.unpack('<H', raw_bytes[16:18])[0]

            print(f"\nRMCPTP 帧头:")
            print(f"  dwLength: {dw_length}")
            print(f"  tmStamp: {tm_stamp}")
            print(f"  nVersion: {n_version}")
            print(f"  nMsgType: {n_msg_type}")
            print(f"  nFlags: {n_flags}")
            print(f"  nCheckSum: {n_check_sum}")

            # 业务数据
            if len(raw_bytes) >= 25:
                print(f"\n业务数据 (从 offset 18):")
                dt = raw_bytes[18]
                dl = struct.unpack('<I', raw_bytes[19:23])[0] if len(raw_bytes) >= 23 else 0
                print(f"  DT (offset 18): {dt}")
                print(f"  DL (offset 19-22): {dl}")

if __name__ == '__main__':
    capture_dir = Path(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\capture")
    # 使用有 FSCAN 数据的文件
    target = capture_dir / "capture_20260416_151359.json"
    if not target.exists():
        files = sorted(capture_dir.glob("capture_*.json"))
        target = files[-2] if len(files) > 1 else files[-1]
    print(f"分析文件: {target.name}")
    extract_fscan_from_capture(target)