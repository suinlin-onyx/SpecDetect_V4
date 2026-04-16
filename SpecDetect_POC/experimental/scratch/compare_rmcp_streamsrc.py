#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rmcp vs streamsrc 数据对比分析

输入:
  - rmcp 原始日志 (block 格式, levels_dbm=[...])
  - streamsrc 频谱日志 (spectrum_*.log, 每个频谱一行 dBm(前100)=[...])

输出:
  - 时间戳对齐
  - dBm 分布直方图对比
  - 量化等级分析 (streamsrc 是否只有少数几个固定值)
"""

import re
import os
import sys
import glob
from collections import Counter
from datetime import datetime

TS_PAT_RMCP = re.compile(r'^=([0-9\- :.]+)=\s*$')
LEVELS_PAT = re.compile(r'^levels_dbm=\[(.*)\]\s*$')
SPEC_HDR = re.compile(r'^\[([0-9\- :.]+)\] 频谱 #(\d+): FSCAN-(\d+) levels=(\d+)')
DBM_LINE = re.compile(r'^\s*dBm\(前100\): \[(.*)\]\s*$')


def parse_rmcp_log(path):
    """返回 [(ts, [dbm,...]), ...]"""
    out = []
    ts = None
    levels = None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = TS_PAT_RMCP.match(line)
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


def parse_streamsrc_spectrum(path):
    """返回 [(ts, fscan_type, dbm_list), ...] —— 只取 前100 段"""
    out = []
    current = None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = SPEC_HDR.match(line)
            if m:
                if current:
                    out.append(current)
                current = [m.group(1), int(m.group(3)), None]
                continue
            m = DBM_LINE.match(line)
            if m and current and current[2] is None:
                vals = []
                for x in m.group(1).split(','):
                    x = x.strip()
                    if x == 'N/A' or not x:
                        continue
                    try:
                        vals.append(float(x))
                    except ValueError:
                        pass
                current[2] = vals
    if current and current[2] is not None:
        out.append(current)
    return out


def summarize(vals, label):
    if not vals:
        print(f"  {label}: <empty>")
        return
    print(f"  {label}: n={len(vals)}  range=[{min(vals):.1f}, {max(vals):.1f}]  "
          f"mean={sum(vals)/len(vals):.2f}")
    rounded = [round(v, 1) for v in vals]
    cnt = Counter(rounded)
    uniq = len(cnt)
    print(f"    唯一值数: {uniq}")
    for v, c in cnt.most_common(8):
        pct = c * 100 / len(vals)
        print(f"    {v:>7.1f} dBm  ×{c:>4}  ({pct:5.1f}%)")


def find_latest(pattern, base):
    matches = sorted(glob.glob(os.path.join(base, pattern)))
    return matches[-1] if matches else None


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    rmcp_dir = os.path.join(base, '..', 'rmcp_proxy', 'capture')
    ss_dir = os.path.join(base, 'logs')

    if len(sys.argv) >= 3:
        rmcp_path = sys.argv[1]
        ss_path = sys.argv[2]
    else:
        rmcp_path = find_latest('raw_fscan_*.log', rmcp_dir)
        ss_path = find_latest('spectrum_*.log', ss_dir)

    print("=" * 70)
    print("rmcp vs streamsrc 对比分析")
    print("=" * 70)
    print(f"rmcp log     : {rmcp_path}")
    print(f"streamsrc log: {ss_path}")

    if not rmcp_path or not os.path.exists(rmcp_path):
        print("[!] rmcp 日志未找到")
        return
    if not ss_path or not os.path.exists(ss_path):
        print("[!] streamsrc 日志未找到")
        return

    rmcp = parse_rmcp_log(rmcp_path)
    ss = parse_streamsrc_spectrum(ss_path)

    print(f"\nrmcp 数据块数   : {len(rmcp)}")
    print(f"streamsrc 频谱数: {len(ss)}")

    # 全量 dBm 分布
    rmcp_all = [v for _, vals in rmcp for v in vals]
    ss_all = [v for _, _, vals in ss for v in vals]

    print("\n--- rmcp dBm 分布 ---")
    summarize(rmcp_all, "rmcp 全部电平")

    print("\n--- streamsrc dBm 分布 (前100样本) ---")
    summarize(ss_all, "streamsrc 全部电平")

    # 按 FSCAN 类型拆分 streamsrc
    for ftype in sorted({t for _, t, _ in ss}):
        vals = [v for _, t, lv in ss if t == ftype for v in lv]
        print(f"\n--- streamsrc FSCAN-{ftype} ---")
        summarize(vals, f"FSCAN-{ftype}")

    # 时间对齐: 配对每个 streamsrc 频谱最近的 rmcp 块
    print("\n--- 时间对齐 (streamsrc → 最近 rmcp 块) ---")
    def parse_ts(s):
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    rmcp_ts = [(parse_ts(ts), ts, vals) for ts, vals in rmcp]
    rmcp_ts = [r for r in rmcp_ts if r[0]]
    shown = 0
    for ts, ftype, lv in ss[:5]:
        t = parse_ts(ts)
        if not t or not rmcp_ts:
            continue
        nearest = min(rmcp_ts, key=lambda r: abs((r[0] - t).total_seconds()))
        delta = (nearest[0] - t).total_seconds()
        print(f"  ss {ts} FSCAN-{ftype} <-> rmcp {nearest[1]} (delta={delta:+.3f}s)")
        shown += 1
    if not shown:
        print("  (无法解析时间戳)")

    # 量化等级对比
    print("\n--- 量化假设验证 ---")
    r_unique = len(set(round(v, 1) for v in rmcp_all))
    s_unique = len(set(round(v, 1) for v in ss_all))
    print(f"  rmcp      唯一 dBm 值数: {r_unique}")
    print(f"  streamsrc 唯一 dBm 值数: {s_unique}")
    if s_unique < r_unique / 5:
        print(f"  => streamsrc 量化明显 (≈{s_unique}级 vs rmcp {r_unique}级)")
    else:
        print(f"  => 量化差异不显著")


if __name__ == '__main__':
    main()
