#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证 Atom streamsrc 数据帧解析器
使用 loopback.pcap 离线数据验证
"""

import struct
from scapy.all import rdpcap, TCP, Raw, IP


def parse_atom_frame(data):
    """
    解析 Atom 18012 端口数据帧

    帧格式:
    Offset 0:   0xEEEEEEEE (4字节) - 帧开始标记
    Offset 4-27: 24字节头
    Offset 28+: 电平数据 (N×2字节) - signed short little-endian
                或 taskid 字符串 (65字节帧)
    """
    if len(data) < 4:
        return None

    if data[:4] != bytes.fromhex('eeeeeeee'):
        return None

    if len(data) == 65:
        taskid = data[28:].decode('ascii', errors='replace').strip('\x00')
        return {'type': 'TASKID', 'taskid': taskid}
    else:
        uint32_1 = struct.unpack('<I', data[4:8])[0]
        uint32_2 = struct.unpack('<I', data[8:12])[0]
        uint32_3 = struct.unpack('<I', data[12:16])[0]
        uint32_4 = struct.unpack('<I', data[16:20])[0]
        uint32_5 = struct.unpack('<I', data[20:24])[0]
        uint32_6 = struct.unpack('<I', data[24:28])[0]

        payload_start = 28
        payload = data[payload_start:]
        num_levels = len(payload) // 2
        levels = struct.unpack(f'<{num_levels}h', payload)

        return {
            'type': 'SPECTRUM',
            'length': len(data),
            'dt_type': uint32_6 & 0xFF,
            'level_count': num_levels,
            'levels': levels,
            'level_min': min(levels),
            'level_max': max(levels),
        }


def main():
    pcap_file = "D:/arvin/claude_workspace/loopback.pcap"

    print("=" * 60)
    print("Atom streamsrc 解析器验证")
    print("=" * 60)
    print(f"\n数据来源: {pcap_file}\n")

    # 读取抓包数据
    packets = rdpcap(pcap_file)

    # 收集 18012 端口数据帧
    frames = []
    for p in packets:
        if IP in p and TCP in p and Raw in p:
            if p[TCP].sport == 18012 or p[TCP].dport == 18012:
                data = p[Raw].load
                if len(data) > 10 and data[:4] == bytes.fromhex('eeeeeeee'):
                    frames.append(data)

    print(f"共解析到 {len(frames)} 帧数据\n")

    # 统计
    spectrum_frames = [f for f in frames if len(f) != 65]
    taskid_frames = [f for f in frames if len(f) == 65]

    print("-" * 60)
    print(f"频谱帧: {len(spectrum_frames)}")
    print(f"taskid帧: {len(taskid_frames)}")
    print("-" * 60)

    # 解析并显示
    spectrum_stats = {
        '1086': {'count': 0, 'levels': []},
        '896': {'count': 0, 'levels': []},
        'other': {'count': 0, 'levels': []},
    }

    for i, frame in enumerate(frames):
        result = parse_atom_frame(frame)

        if result['type'] == 'TASKID':
            print(f"\n帧 {i}: TASKID")
            print(f"  taskid: {result['taskid']}")
        else:
            if result['length'] == 1086:
                key = '1086'
            elif result['length'] == 896:
                key = '896'
            else:
                key = 'other'

            spectrum_stats[key]['count'] += 1

            if spectrum_stats[key]['count'] <= 3:
                print(f"\n帧 {i}: SPECTRUM")
                print(f"  长度: {result['length']}")
                print(f"  DT: {result['dt_type']}")
                print(f"  电平数: {result['level_count']}")
                print(f"  范围: [{result['level_min']}, {result['level_max']}]")

                # 显示电平样本
                levels = result['levels']
                print(f"  前10个电平: {levels[:10]}")
                print(f"  后10个电平: {levels[-10:]}")

    # 汇总
    print("\n" + "=" * 60)
    print("统计汇总")
    print("=" * 60)
    for key, stats in spectrum_stats.items():
        if stats['count'] > 0:
            print(f"  {key} 字节帧: {stats['count']} 帧")

    print("\n[+] 解析验证完成")


if __name__ == '__main__':
    main()
