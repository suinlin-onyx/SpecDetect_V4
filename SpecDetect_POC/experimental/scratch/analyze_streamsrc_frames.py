#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线解析 streamsrc 原始帧日志
生成完整的频谱数据用于对比分析
"""

import struct
import re
import os
from datetime import datetime
from collections import Counter

SS_MIN = -32768
SS_MAX = 24933
DBUV_MIN = 0.0
DBUV_MAX = 78.9

def streamsrc_to_dbm(val):
    if val == SS_MIN:
        return None
    norm = (val - SS_MIN) / (SS_MAX - SS_MIN)
    norm = max(0, min(1, norm))
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    dbm = dbuv - 107.6
    return round(dbm, 1)

def parse_log_file(log_path):
    """解析 streamsrc 原始帧日志"""
    with open(log_path, 'rb') as f:
        content = f.read().decode('utf-8', errors='replace')

    frames = []
    current = {}
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('=') and line.endswith('='):
            if current and 'hex' in current:
                frames.append(current)
            current = {'ts': line[1:-1]}
        elif line.startswith('size='):
            current['size'] = int(line.split('=')[1].split()[0])
        elif line.startswith('frame_hex='):
            current['hex'] = line[10:]

    if current and 'hex' in current:
        frames.append(current)

    return frames

def parse_frame(data):
    """解析单帧数据"""
    if len(data) < 28:
        return None

    # offset 19: FSCAN 类型
    fscan_type = data[19]

    if fscan_type == 0:
        return None  # STATUS 帧

    if fscan_type not in (0x26, 0x68):
        return None

    frame_type = 'FSCAN-434' if fscan_type == 0x68 else 'FSCAN-529'

    # payload 从 offset 28 开始
    payload = data[28:]
    if len(payload) % 2 != 0:
        payload = payload[:-1]
    num_levels = len(payload) // 2
    if num_levels <= 0:
        return None

    try:
        levels = struct.unpack(f'<{num_levels}h', payload)
    except:
        return None

    return {
        'type': frame_type,
        'levels': list(levels),
    }

def analyze_frames(frames):
    """分析帧数据"""
    print("=" * 70)
    print("streamsrc 原始帧分析")
    print("=" * 70)
    print(f"总帧数: {len(frames)}")

    # 分类统计
    fscan_529 = []
    fscan_434 = []
    unknown = 0

    for f in frames:
        data = bytes.fromhex(f['hex'])
        t19 = data[19]

        if t19 == 0x26:
            result = parse_frame(data)
            if result:
                fscan_529.append((f['ts'], result['levels']))
        elif t19 == 0x68:
            result = parse_frame(data)
            if result:
                fscan_434.append((f['ts'], result['levels']))
        else:
            unknown += 1

    print(f"FSCAN-529: {len(fscan_529)} 帧")
    print(f"FSCAN-434: {len(fscan_434)} 帧")
    print(f"UNKNOWN: {unknown} 帧")

    # 计算总电平数
    total_529 = sum(len(ts[1]) for ts in fscan_529)
    total_434 = sum(len(ts[1]) for ts in fscan_434)
    print(f"\nFSCAN-529 总电平: {total_529} (需要 529)")
    print(f"FSCAN-434 总电平: {total_434} (需要 434)")

    return fscan_529, fscan_434

def load_rmcp_data(log_path):
    """加载 rmcp FSCAN 数据"""
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    frames = []
    current = {}
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('=') and line.endswith('='):
            if current and 'levels' in current:
                frames.append(current)
            ts = line[1:-1]
            current = {'ts': ts}
        elif line.startswith('timestamp='):
            current['timestamp'] = line.split('=', 1)[1]
        elif line.startswith('levels_dbm='):
            # 解析 levels_dbm 数组
            array_str = line.split('=', 1)[1]
            levels = [float(x) for x in re.findall(r'[-.\d]+', array_str)]
            current['levels'] = levels

    if current and 'levels' in current:
        frames.append(current)

    return frames

def compare_data():
    """对比 streamsrc 和 rmcp 数据"""
    print("\n" + "=" * 70)
    print("streamsrc vs rmcp 数据对比")
    print("=" * 70)

    # 使用最新采集的数据
    streamsrc_log = "D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/experimental/logs/streamsrc_raw_20260415_165152.log"
    rmcp_log = "D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/rmcp_proxy/capture/raw_fscan_20260415_165150.log"

    if not os.path.exists(streamsrc_log):
        print(f"[!] streamsrc 日志不存在: {streamsrc_log}")
        return

    if not os.path.exists(rmcp_log):
        print(f"[!] rmcp 日志不存在: {rmcp_log}")
        return

    print(f"streamsrc: {streamsrc_log}")
    print(f"rmcp: {rmcp_log}")

    # 分析 streamsrc
    print("\n--- streamsrc 数据 ---")
    frames = parse_log_file(streamsrc_log)
    fscan_529, fscan_434 = analyze_frames(frames)

    # 加载 rmcp 数据
    print("\n--- rmcp 数据 ---")
    rmcp_frames = load_rmcp_data(rmcp_log)
    print(f"rmcp 帧数: {len(rmcp_frames)}")

    if rmcp_frames:
        # 分析 rmcp 数据范围
        all_dbm = []
        for f in rmcp_frames:
            all_dbm.extend(f['levels'])

        print(f"dBm 范围: [{min(all_dbm):.1f}, {max(all_dbm):.1f}]")
        print(f"前5帧电平数: {[len(f['levels']) for f in rmcp_frames[:5]]}")

        # 时间范围
        if rmcp_frames:
            print(f"时间范围: {rmcp_frames[0]['ts']} - {rmcp_frames[-1]['ts']}")

    # 关键对比
    print("\n" + "=" * 70)
    print("关键对比")
    print("=" * 70)

    print(f"""
streamsrc FSCAN-529:
  - 帧数: {len(fscan_529)}
  - 总电平: {sum(len(t[1]) for t in fscan_529)}
  - 需要 529 电平/频谱

rmcp FSCAN:
  - 帧数: {len(rmcp_frames)}
  - 每帧 512 电平
  - 每 ~100ms 一帧

问题: streamsrc 帧数不足以拼出完整频谱
  - 需要 529/18 ≈ 30 帧 FSCAN-529
  - 实际收到 {len(fscan_529)} 帧
  - 需要 434/18 ≈ 25 帧 FSCAN-434
  - 实际收到 {len(fscan_434)} 帧

可能原因:
  1. Atom 只发送了部分帧
  2. 数据发送速率与之前不同
  3. 需要更长时间采集
""")

def analyze_existing_logs():
    """分析已有的成功日志"""
    print("\n" + "=" * 70)
    print("分析已有成功日志 (20260414_215726)")
    print("=" * 70)

    streamsrc_log = "D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/experimental/logs/streamsrc_raw_20260414_215726.log"

    if not os.path.exists(streamsrc_log):
        print("[!] 日志不存在")
        return

    frames = parse_log_file(streamsrc_log)
    print(f"总帧数: {len(frames)}")

    fscan_529, fscan_434 = analyze_frames(frames)

    # 收集所有电平数据
    all_529_levels = []
    for ts, levels in fscan_529:
        all_529_levels.extend(levels)

    print(f"\nFSCAN-529 完整数据:")
    print(f"  总电平: {len(all_529_levels)}")

    if len(all_529_levels) >= 529:
        # 取前 529 个电平
        spectrum = all_529_levels[:529]
        valid = [v for v in spectrum if v != SS_MIN]
        if valid:
            print(f"  原始值范围: [{min(valid)}, {max(valid)}]")
            dbm_values = [streamsrc_to_dbm(v) for v in valid]
            print(f"  dBm 范围: [{min(dbm_values):.1f}, {max(dbm_values):.1f}]")

            # 统计分布
            counter = Counter(dbm_values)
            print(f"\n  dBm 值分布 (前10):")
            for dbm, count in counter.most_common(10):
                print(f"    {dbm:6.1f} dBm: {count:4d} 次")

def main():
    # 对比 streamsrc 和 rmcp
    compare_data()

    # 分析已有成功日志
    analyze_existing_logs()

if __name__ == '__main__':
    main()
