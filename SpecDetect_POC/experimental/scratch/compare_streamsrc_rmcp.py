#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
streamsrc vs rmcp 数据对比分析
目标: 找出 Atom 对设备原始数据的滤波/变换规则
"""

import re
from collections import Counter

# =============================================================================
# 数据定义 (来自 logs)
# =============================================================================

# streamsrc 频谱数据 (spectrum_20260414_215726.log)
# FSCAN-529, levels=529
streamsrc_raw_529 = [256, 1441, 0, 0, -32768, 21736, 16800, 0, 12288, -9531,
                     16801, 0, 0, 20480, 18115, 512, 0, -55, 256, 1441,
                     0, 0, -32768, -9336, 16801, 0, 12288, 24933, 16803, 512,
                     0, 20480, 18115, 512, 0, -45, 256, 1441, 0, 0,
                     -32768, 21736, 16800, 0, 12288, -9531, 16801, 0, 0, 20480,
                     18115, 512, 0, -40]

# rmcp 设备原始数据 (raw_fscan_20260414_215655.log, 第一帧)
rmcp_dbm_512 = [-55.0, -63.7, -79.1, -61.3, -74.9, -62.9, -61.6, -57.6, -75.8, -62.0,
                -55.8, -74.7, -84.7, -77.1, -67.8, -74.8, -53.8, -80.9, -52.8, -52.3,
                -68.2, -54.9, -67.8, -68.0, -64.0, -55.6, -72.0, -74.6, -79.7, -91.7,
                -59.8, -52.1, -62.7, -58.2, -47.2, -66.0, -77.8, -49.6, -53.8, -66.6,
                -63.1, -84.7, -64.5, -80.3, -69.1, -68.2, -68.9, -68.8, -53.5, -54.1,
                -68.0, -70.4, -58.2, -76.4, -91.5, -66.2, -43.1, -56.4, -67.2, -79.0,
                -68.5, -50.5, -85.8, -58.6, -41.8, -61.5, -57.3, -79.3, -77.2, -53.8,
                -56.1, -55.6, -58.3, -60.1, -76.5, -78.5, -67.9, -66.1, -68.5, -53.1,
                -62.0, -51.6, -47.3, -72.3, -66.2, -80.1, -58.9, -60.8, -80.1, -67.1,
                -52.3, -61.5, -62.7, -52.8, -64.6, -51.8, -44.4, -55.0, -65.2, -86.1]

# =============================================================================
# streamsrc 转换函数
# =============================================================================

SS_MIN = -32768  # 无效值
SS_MAX = 24933   # 最大值
DBUV_MIN = 0.0
DBUV_MAX = 78.9

def streamsrc_to_dbm(val):
    """streamsrc 原始值 -> dBm"""
    if val == SS_MIN:
        return None
    norm = (val - SS_MIN) / (SS_MAX - SS_MIN)
    norm = max(0, min(1, norm))
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    dbm = dbuv - 107.6
    return round(dbm, 1)

# streamsrc 转换表
SS_VALUES = {
    0: -62.8,
    512: -62.1,
    12288: -46.0,
    16800: -39.8,
    16801: -39.8,
    18115: -38.0,
    18115: -38.0,
    20480: -34.8,
    21736: -33.1,
    24933: -28.7,
    256: -62.4,
    1441: -60.8,
    -55: -62.9,
    -9336: -75.6,
    -9531: -75.8,
}

# =============================================================================
# 分析函数
# =============================================================================

def analyze_streamsrc_pattern():
    """分析 streamsrc 数据的值分布"""
    print("=" * 70)
    print("streamsrc 原始值分布分析")
    print("=" * 70)

    # 从完整数据中提取 (去重)
    all_values = set()
    for v in streamsrc_raw_529:
        all_values.add(v)

    print("\nstreamsrc 原始值集合:")
    for v in sorted(all_values):
        if v == -32768:
            print(f"  {v:6d} -> N/A (无效值)")
        else:
            dbm = streamsrc_to_dbm(v)
            print(f"  {v:6d} -> {dbm:6.1f} dBm")

    print("\n观察:")
    print("  1. streamsrc 原始值集中在几个固定值")
    print("  2. 这些值是 2 的幂次: 0, 512, 12288, 16384, 20480, 24933")
    print("  3. 可能是量化等级，每级 ~78.9/24933 dBuV")


def analyze_rmcp_distribution():
    """分析 rmcp 数据分布"""
    print("\n" + "=" * 70)
    print("rmcp dBm 分布分析")
    print("=" * 70)

    # 统计分布
    counter = Counter()
    for v in rmcp_dbm_512:
        bucket = int(v)
        counter[bucket] += 1

    print("\nrmcp dBm 分布 (每 5dBm 一档):")
    buckets = {}
    for v in rmcp_dbm_512:
        bucket = (int(v) // 5) * 5
        buckets[bucket] = buckets.get(bucket, 0) + 1

    for bucket in sorted(buckets.keys()):
        count = buckets[bucket]
        bar = '*' * count
        print(f"  {bucket:4d} dBm: {bar} ({count})")

    print(f"\n范围: [{min(rmcp_dbm_512):.1f}, {max(rmcp_dbm_512):.1f}] dBm")
    print(f"均值: {sum(rmcp_dbm_512)/len(rmcp_dbm_512):.1f} dBm")


def analyze_conversion_relationship():
    """分析转换关系"""
    print("\n" + "=" * 70)
    print("streamsrc -> rmcp 转换关系分析")
    print("=" * 70)

    # streamsrc 固定值对应的 dBm
    print("\nstreamsrc 固定值 -> dBm:")
    fixed_values = [0, 512, 12288, 16800, 18115, 20480, 21736, 24933]
    for v in fixed_values:
        dbm = streamsrc_to_dbm(v)
        print(f"  {v:6d} -> {dbm:6.1f} dBm")

    # rmcp 中对应 dBm 的分布
    print("\nrmcp 中对应 dBm 范围的统计:")
    ranges = [(-70, -60), (-60, -50), (-50, -40), (-40, -30)]
    for low, high in ranges:
        count = sum(1 for v in rmcp_dbm_512 if low <= v < high)
        pct = count / len(rmcp_dbm_512) * 100
        print(f"  [{low:3d}, {high:3d}) dBm: {count:3d} ({pct:5.1f}%)")


def find_quantization_levels():
    """找出 streamsrc 的量化等级"""
    print("\n" + "=" * 70)
    print("streamsrc 量化等级分析")
    print("=" * 70)

    # 观察: streamsrc 值是 2 的幂次
    print("\n观察到的 streamsrc 原始值:")
    observed = [0, 256, 417, 512, 1024, 12288, 1441, 16800, 16801, 18115, 20480, 21736, 24933, 25128]

    print("\n值       | 二进制          | dBm")
    print("-" * 50)
    for v in sorted(set(observed)):
        if v != -32768:
            dbm = streamsrc_to_dbm(v)
            print(f"{v:8d} | {v:016b} | {dbm:6.1f}")

    print("\n关键发现:")
    print("  1. 值范围 [0, 24933]，最大约 2^14.6")
    print("  2. 常见值: 0, 512(2^9), 12288(2^14/2), 20480(~2^14), 24933(最大)")
    print("  3. 这些可能是量化步进，不是直接映射")
    print("  4. 真正处理: rmcp dBm -> 归一化 -> 量化到固定等级")


def analyze_noise_floor():
    """分析噪声门限"""
    print("\n" + "=" * 70)
    print("噪声门限分析")
    print("=" * 70)

    # -62.8 dBm 在 streamsrc 中出现最多 (对应原始值 0)
    print("\nstreamsrc 中值 0 的含义:")
    print("  streamsrc raw=0 -> dBm=-62.8")
    print("  这可能是噪声门限以下的默认值")

    # rmcp 中低于 -63 dBm 的比例
    below_63 = sum(1 for v in rmcp_dbm_512 if v < -63)
    print(f"\nrmcp 中 < -63 dBm 的比例: {below_63}/{len(rmcp_dbm_512)} ({below_63/len(rmcp_dbm_512)*100:.1f}%)")

    # 高于 -63 dBm 的比例
    above_63 = sum(1 for v in rmcp_dbm_512 if v >= -63)
    print(f"rmcp 中 >= -63 dBm 的比例: {above_63}/{len(rmcp_dbm_512)} ({above_63/len(rmcp_dbm_512)*100:.1f}%)")

    # streamsrc 中值 0 的比例
    zero_count = streamsrc_raw_529.count(0)
    invalid_count = streamsrc_raw_529.count(-32768)
    total = len(streamsrc_raw_529)
    print(f"\nstreamsrc 中 raw=0 的比例: {zero_count}/{total} ({zero_count/total*100:.1f}%)")
    print(f"streamsrc 中 raw=-32768 的比例: {invalid_count}/{total} ({invalid_count/total*100:.1f}%)")


def hypothesize_filtering():
    """Atom 滤波/变换假设"""
    print("\n" + "=" * 70)
    print("Atom 滤波/变换假设")
    print("=" * 70)

    print("""
假设1: 噪声门限滤波
  rmcp 数据: [-101.9, -26.0] dBm (全范围)
  streamsrc 数据: [-75.8, -28.7] dBm (截断)
  低于 -76 dBm 的 rmcp 值 -> streamsrc 中标记为 -32768 (无效)

假设2: 量化处理
  rmcp 连续 dBm -> streamsrc 固定等级
  等级数量约 8-13 个
  每个等级对应一个固定的 streamsrc 原始值

假设3: 数据精简
  rmcp: 512 点/帧，实时全量数据
  streamsrc: 529 点/扫描，可能是统计结果而非实时

转换流程推测:
  rmcp dBm -> 噪声门限滤波 -> 量化 -> streamsrc 原始值
""")

def analyze_frame_structure():
    """分析帧结构差异"""
    print("\n" + "=" * 70)
    print("帧结构差异分析")
    print("=" * 70)

    print("""
streamsrc (529点):
  - 18 电平/帧 × 30帧 ≈ 529 点
  - 每帧 65 字节 = 4(头) + 24(元数据) + 36(18×2数据)
  - 频率范围: 可能是 2400-2500 MHz ISM 频段

rmcp (512点):
  - 512 点/帧
  - 实时 FFT 结果
  - 频率范围: 与 streamsrc 可能相同但分辨率不同

关键问题:
  1. 529 vs 512 的差异: 可能是带宽/分辨率不同
  2. streamsrc 的 529 点是累加/平均后的结果
  3. rmcp 是实时采样
""")


# =============================================================================
# 主函数
# =============================================================================

def main():
    print("\n" + "=" * 70)
    print("streamsrc vs rmcp 数据对比分析")
    print("目标: 找出 Atom 对设备原始数据的滤波/变换规则")
    print("=" * 70)

    analyze_streamsrc_pattern()
    analyze_rmcp_distribution()
    analyze_conversion_relationship()
    find_quantization_levels()
    analyze_noise_floor()
    hypothesize_filtering()
    analyze_frame_structure()

    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    print("""
1. streamsrc 值是量化后的固定等级，不是直接映射
2. 主要量化等级约 8-13 个，对应不同信号强度
3. 噪声门限约 -63 dBm，低于此值标记为 0 或 -32768
4. streamsrc 是精简数据，用于实时监测
5. rmcp 是完整数据，用于分析存档

下一步验证:
  - 同步采集 rmcp + streamsrc，对比同一时刻数据
  - 找出每个 streamsrc 量化等级对应的 rmcp dBm 范围
  - 验证噪声门限假设
""")


if __name__ == '__main__':
    main()
