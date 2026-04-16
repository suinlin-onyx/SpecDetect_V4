#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绘制 rmcp vs streamsrc 频谱对比图

用法: python plot_spectrum_compare.py [rmcp_log] [streamsrc_raw_log]
"""

import re
import sys
import os
import struct
from datetime import datetime

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    print("[!] 请先安装 matplotlib: pip install matplotlib")
    sys.exit(1)


TS_PAT = re.compile(r'^=([0-9\- :.]+)=\s*$')
LEVELS_PAT = re.compile(r'^dbm=\[(.*)\]\s*$')
FRAME_PAT = re.compile(r'^frame_hex=([0-9a-fA-F]+)\s*$')


def parse_rmcp_log(path):
    """返回 [(ts, [dbm,...]), ...]"""
    out = []
    ts = None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = TS_PAT.match(line)
            if m:
                ts = m.group(1)
                continue
            m = LEVELS_PAT.match(line)
            if m and ts:
                try:
                    vals = [float(x) for x in m.group(1).split(',') if x.strip()]
                    out.append((ts, vals))
                except ValueError:
                    pass
                ts = None
    return out


def parse_streamsrc_raw(path):
    """解析 streamsrc 原始帧日志，返回 [(ts, fscan_type, [dbm_values]), ...]"""
    out = []
    ts = None
    frame_hex = None

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            m = TS_PAT.match(line)
            if m:
                ts = m.group(1)
                continue
            m = FRAME_PAT.match(line)
            if m and ts:
                frame_hex = m.group(1)
                try:
                    # 解析帧
                    data = bytes.fromhex(frame_hex)

                    # offset 19: FSCAN 类型
                    fscan_type = data[19]  # 0x26=529, 0x68=434

                    # offset 28+: 18 int16 值 (5元数据 + 13电平)
                    levels = []
                    for i in range(13):
                        offset = 28 + i * 2
                        val = struct.unpack('<h', data[offset:offset+2])[0]
                        # 转换: raw → dBm (streamsrc 原始值是直接 dBm * 100?)
                        # 根据之前分析, streamsrc raw 值范围 [0, 24933]
                        # 实际 dBm = raw / 100 - 62.8 (底噪补偿) 或直接 raw/100
                        dbm = val / 100.0
                        if val == -32768:
                            dbm = None  # 无效值
                        levels.append(dbm)
                    out.append((ts, fscan_type, levels))
                except Exception as e:
                    pass
                ts = None
    return out


def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    rmcp_dir = os.path.join(base, '..', 'rmcp_proxy', 'capture')
    ss_dir = os.path.join(base, 'logs')

    if len(sys.argv) >= 3:
        rmcp_path = sys.argv[1]
        ss_path = sys.argv[2]
    else:
        rmcp_path = os.path.join(rmcp_dir, 'raw_fscan_20260415_163533.log')
        ss_path = os.path.join(ss_dir, 'streamsrc_raw_20260415_163535.log')

    print(f"rmcp log     : {rmcp_path}")
    print(f"streamsrc log: {ss_path}")

    if not os.path.exists(rmcp_path):
        print(f"[!] rmcp 日志未找到: {rmcp_path}")
        return
    if not os.path.exists(ss_path):
        print(f"[!] streamsrc 日志未找到: {ss_path}")
        return

    rmcp = parse_rmcp_log(rmcp_path)
    ss = parse_streamsrc_raw(ss_path)

    print(f"\nrmcp 数据块数   : {len(rmcp)}")
    print(f"streamsrc 帧数: {len(ss)}")

    if not rmcp or not ss:
        print("[!] 解析数据为空")
        return

    # rmcp 每3帧为一组完整扫描 (512+512+417=1441)
    rmcp_groups = []
    i = 0
    while i + 2 < len(rmcp):
        g = rmcp[i:i+3]
        if len(g) == 3:
            combined = g[0][1] + g[1][1] + g[2][1]
            rmcp_groups.append((g[0][0], combined))
        i += 3

    print(f"rmcp 完整扫描组数: {len(rmcp_groups)}")

    # streamsrc: 收集同一FSCAN的所有帧
    # 根据offset19类型分组, 时间间隔~110ms内属于同一FSCAN
    ss_fscans = []
    current_fscan = None
    last_ts = None

    for ts, ftype, levels in ss:
        t = parse_ts(ts)
        if current_fscan is None:
            current_fscan = {'type': ftype, 'ts': ts, 'frames': [levels], 'last_ts': t}
        elif t and current_fscan['last_ts'] and (t - current_fscan['last_ts']).total_seconds() > 0.2:
            # 时间间隔>200ms, 新FSCAN
            ss_fscans.append(current_fscan)
            current_fscan = {'type': ftype, 'ts': ts, 'frames': [levels], 'last_ts': t}
        else:
            current_fscan['frames'].append(levels)
            current_fscan['last_ts'] = t

    if current_fscan:
        ss_fscans.append(current_fscan)

    print(f"streamsrc FSCAN组数: {len(ss_fscans)}")

    # 取第一组完整 rmcp 扫描
    rmcp0_ts, rmcp0_vals = rmcp_groups[0] if rmcp_groups else (rmcp[0][0], rmcp[0][1])

    # 取第一组 streamsrc
    ss0 = ss_fscans[0] if ss_fscans else None

    # 绘图
    fig, axes = plt.subplots(3, 1, figsize=(16, 12))

    # Plot 1: rmcp full 1441-point spectrum
    ax1 = axes[0]
    ax1.plot(rmcp0_vals, 'b-', linewidth=0.5, alpha=0.8)
    ax1.set_title(f'rmcp Spectrum (Full Scan, {len(rmcp0_vals)} pts) - {rmcp0_ts}', fontsize=12)
    ax1.set_xlabel('Frequency Index')
    ax1.set_ylabel('dBm')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-120, -20)

    # Plot 2: streamsrc reassembled spectrum
    ax2 = axes[1]
    if ss0:
        ss0_combined = []
        for f in ss0['frames']:
            ss0_combined.extend([v for v in f if v is not None])
        ax2.plot(ss0_combined, 'r-', linewidth=0.5, alpha=0.8)
        ax2.set_title(f'streamsrc Spectrum (FSCAN-{ss0["type"]}, {len(ss0_combined)} pts) - {ss0["ts"]}', fontsize=12)
        ax2.set_xlabel('Frequency Index')
        ax2.set_ylabel('dBm')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(-120, -20)

    # Plot 3: Overlay comparison
    ax3 = axes[2]
    if ss0:
        ss0_combined = []
        for f in ss0['frames']:
            ss0_combined.extend([v for v in f if v is not None])

        # Downsample rmcp to match streamsrc length
        if len(rmcp0_vals) >= len(ss0_combined):
            step = len(rmcp0_vals) / len(ss0_combined)
            rmcp_down = [rmcp0_vals[int(i * step)] for i in range(len(ss0_combined))]
        else:
            rmcp_down = rmcp0_vals[:len(ss0_combined)]

        ax3.plot(rmcp_down, 'b-', linewidth=0.8, alpha=0.7, label=f'rmcp (downsampled to {len(ss0_combined)} pts)')
        ax3.plot(ss0_combined, 'r-', linewidth=0.8, alpha=0.7, label=f'streamsrc FSCAN-{ss0["type"]}')
        ax3.set_title('rmcp vs streamsrc Overlay (Normalized)', fontsize=12)
        ax3.set_xlabel('Frequency Index')
        ax3.set_ylabel('dBm')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(-120, -20)

    plt.tight_layout()

    out_path = os.path.join(base, 'spectrum_comparison.png')
    plt.savefig(out_path, dpi=150)
    print(f"\n图片已保存: {out_path}")

    # 额外: 多帧时序图
    if len(ss) >= 10:
        fig2, axes2 = plt.subplots(2, 1, figsize=(16, 8))

        # rmcp first 3 groups
        ax = axes2[0]
        for idx, (ts, vals) in enumerate(rmcp_groups[:3]):
            x = range(idx * len(vals), idx * len(vals) + len(vals))
            ax.plot(list(x), vals, linewidth=0.5, alpha=0.8)
        ax.set_title('rmcp - First 3 Complete Scans')
        ax.set_xlabel('Frequency Index')
        ax.set_ylabel('dBm')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(-120, -20)

        # streamsrc first 15 frames timeline
        ax = axes2[1]
        offset = 0
        colors = plt.cm.tab10.colors
        for idx, (ts, ftype, levels) in enumerate(ss[:15]):
            valid_levels = [v if v is not None else -100 for v in levels]
            ax.plot(range(offset, offset + len(valid_levels)), valid_levels,
                    color=colors[idx % 10], linewidth=0.5, alpha=0.7,
                    label=f'F{idx+1} T{ftype}')
            offset += len(valid_levels)
        ax.set_title('streamsrc - First 15 Frames (Timeline)')
        ax.set_xlabel('Cumulative Frequency Index')
        ax.set_ylabel('dBm')
        ax.legend(fontsize=7, ncol=3)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(-120, -20)

        plt.tight_layout()
        out_path2 = os.path.join(base, 'spectrum_multi_frame.png')
        plt.savefig(out_path2, dpi=150)
        print(f"多帧对比图已保存: {out_path2}")


if __name__ == '__main__':
    main()
