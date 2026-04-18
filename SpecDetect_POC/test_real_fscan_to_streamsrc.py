#!/usr/bin/env python
"""用真实抓包数据测试 streamsrc 帧构建"""
import struct
import json
from pathlib import Path

def build_streamsrc_with_real_data(levels, n_arrays=512, counters=[512, 0, 0, 0], n_bd_type=15):
    """用真实数据构建 streamsrc 帧"""
    # streamsrc 1086B 帧
    frame = bytearray(1086)

    # Sync: 0xEEEEEEEE
    struct.pack_into('<I', frame, 0, 0xEEEEEEEE)

    # Header (44 bytes, offset 4-47)
    header = bytearray(44)
    header[0] = 0x01
    header[15] = n_bd_type  # FSCAN type = 15
    frame[4:48] = header

    # Metadata (7 int16, offset 48-61)
    # 保持原有硬编码结构，只替换关键值
    metadata = [
        16801,        # metadata[0] - 固定
        0,            # metadata[1]
        0,            # metadata[2]
        n_arrays,     # metadata[3] = 512 (nArrays)
        18115,        # metadata[4] - 固定
        n_arrays,     # metadata[5] = 512 (nArrays)
        0             # metadata[6]
    ]

    for i, val in enumerate(metadata):
        struct.pack_into('<h', frame, 48 + i * 2, val)

    # Spectrum (512 int16, offset 62+)
    for i, val in enumerate(levels[:512]):
        struct.pack_into('<h', frame, 62 + i * 2, int(val))

    return bytes(frame)

def main():
    # 从抓包读取真实数据
    capture_file = Path(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\capture\capture_20260416_151359.json")
    with open(capture_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 找第一条 FSCAN
    for entry in data:
        if entry.get('direction') == 'S->C' and entry.get('data_type') == 'SIMPLE_FSCAN':
            fscan = entry.get('fscan', {})
            levels = fscan.get('levels', [])
            n_arrays = fscan.get('nArrays', 512)
            counters = fscan.get('counters', [512, 0, 0, 0])
            n_bd_type = fscan.get('nBdType', 15)

            print(f"真实 rmcp 数据:")
            print(f"  nBdType: {n_bd_type}")
            print(f"  nArrays: {n_arrays}")
            print(f"  counters: {counters}")
            print(f"  levels (前5点): {levels[:5]}")
            print(f"  levels (后5点): {levels[-5:]}")

            # 构建 streamsrc 帧
            frame = build_streamsrc_with_real_data(levels, n_arrays, counters, n_bd_type)

            # 解析验证
            print(f"\n构建的 streamsrc 帧:")
            sync = struct.unpack('<I', frame[0:4])[0]
            print(f"  Sync: 0x{sync:08X}")
            header_type = frame[19]  # offset 19 = header[15]
            print(f"  header[15] (type): 0x{header_type:02X}")

            print(f"  Metadata (7 int16):")
            meta = []
            for i in range(7):
                val = struct.unpack('<h', frame[48 + i*2 : 50 + i*2])[0]
                meta.append(val)
                print(f"    [{i}]: {val}")

            spec_start = struct.unpack('<h', frame[62:64])[0]
            spec_end = struct.unpack('<h', frame[62 + 511*2: 64 + 511*2])[0]
            print(f"  Spectrum[0]: {spec_start}")
            print(f"  Spectrum[255]: {struct.unpack('<h', frame[62 + 255*2: 64 + 255*2])[0]}")
            print(f"  Spectrum[511]: {spec_end}")

            # 对比 rmcp levels vs streamsrc spectrum
            print(f"\n对比 (前5点):")
            for i in range(5):
                rmcp_val = levels[i]
                ss_val = struct.unpack('<h', frame[62 + i*2 : 64 + i*2])[0]
                match = "OK" if rmcp_val == ss_val else "FAIL"
                print(f"    [{i}]: rmcp={rmcp_val}, streamsrc={ss_val} {match}")

            break

if __name__ == '__main__':
    main()