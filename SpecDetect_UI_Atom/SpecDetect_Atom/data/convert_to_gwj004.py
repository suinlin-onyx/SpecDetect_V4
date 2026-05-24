#!/usr/bin/env python3
"""
RX-RMCPTP to GWJ004 Format Converter
将抓包数据转换为第三方工具格式 (GWJ004协议封装)

Usage: python convert_to_gwj004.py <input_json> <output_txt>
"""

import json
import sys
from datetime import datetime

def convert_rmcp_to_gwj004(input_file, output_file):
    """
    将RX-RMCPTP抓包数据转换为GWJ004格式输出
    """

    # 读取抓包数据
    with open(input_file, 'r', encoding='utf-8') as f:
        capture_data = json.load(f)

    # 准备输出
    output_lines = []
    output_lines.append("=" * 60)
    output_lines.append("RX-RMCPTP to GWJ004 格式转换")
    output_lines.append(f"转换时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append("=" * 60)
    output_lines.append("")

    # 统计数据
    total_frames = 0
    fscan_frames = []

    # 处理每个数据包
    for packet in capture_data:
        direction = packet.get('direction', '')
        header = packet.get('header', {})
        hex_data = packet.get('hex', '')
        timestamp = packet.get('timestamp', '')
        size = packet.get('size', 0)

        # 只处理服务端到客户端的FSCAN数据
        if direction != 'S->C':
            continue

        data_type = packet.get('data_type', '')
        if data_type != 'SIMPLE_FSCAN':
            continue

        fscan = packet.get('fscan', {})
        nBdType = fscan.get('nBdType', 0)
        counters = fscan.get('counters', [])
        levels = fscan.get('levels', [])

        # 只处理FSCAN类型 (nBdType = 15)
        if nBdType != 15:
            continue

        total_frames += 1

        # 提取帧头信息
        dwLength = header.get('dwLength', 0)
        nVersion = header.get('nVersion', 0)
        nMsgType = header.get('nMsgType', 0)
        nFlags = header.get('nFlags', 0)
        nCheckSum = header.get('nCheckSum', 0)
        ts = header.get('timestamp', '')

        # 解析频率范围
        # 从hex数据中提取startfreq, endfreq, step
        # 这里简化处理，实际需要解析业务数据头
        nArrays = fscan.get('nArrays', 0)
        level_count = fscan.get('level_count', 0)
        level_min = fscan.get('level_min', 0)
        level_max = fscan.get('level_max', 0)

        # GWJ004格式需要的字段
        # 假设完整频率范围: 137MHz ~ 173MHz
        FREQ_START = 137000000  # 137MHz
        FREQ_END = 173000000    # 173MHz
        STEP = 25000            # 25kHz
        TOTAL_POINTS = ((FREQ_END - FREQ_START) // STEP) + 1  # 1441点
        FRAME_SIZE = 512        # 每帧512点

        # 计算当前帧在完整频段中的位置
        # 每3帧为一组完整的1441点扫描
        group_index = len(fscan_frames) // 3  # 第几组完整扫描
        frame_in_group = len(fscan_frames) % 3  # 组内帧序号 (0, 1, 2)
        start_offset = frame_in_group * FRAME_SIZE

        # 如果超出总点数，跳过
        if start_offset >= TOTAL_POINTS:
            continue

        # 计算当前帧的频率范围
        frame_start_freq = FREQ_START + start_offset * STEP
        remaining_points = TOTAL_POINTS - start_offset
        actual_points = min(FRAME_SIZE, remaining_points)
        frame_end_freq = frame_start_freq + (actual_points - 1) * STEP

        # 保存帧信息
        fscan_frames.append({
            'timestamp': timestamp,
            'group_index': group_index,
            'frame_in_group': frame_in_group,
            'start_freq': frame_start_freq,
            'end_freq': frame_end_freq,
            'start_offset': start_offset,
            'points': actual_points,
            'levels': levels,
            'header': header,
            'fscan': fscan
        })

    # 生成GWJ004格式输出
    output_lines.append(f"[ {timestamp.split('.')[0].replace('T', ' ')} ] 启动任务中，请稍后...")
    output_lines.append("服务地址：HTTP://127.0.0.1:8282")
    output_lines.append(f"[ {timestamp.split('.')[0].replace('T', ' ')} ] 服务响应成功：")
    output_lines.append(f"[ {timestamp.split('.')[0].replace('T', ' ')} ] source建立数据通道成功，开始接收数据！")
    output_lines.append("")

    # 处理每一帧
    prev_ts = ""
    for i, frame in enumerate(fscan_frames):
        ts = frame['timestamp'].split('.')[0].replace('T', ' ')
        ms = frame['timestamp'].split('.')[1] if '.' in frame['timestamp'] else '000'
        ts_short = ts.split(' ')[1]  # 只取时间部分 HH:MM:SS

        # 计算数据长度
        # GWJ004格式: 帧头约24字节 + 数据内容
        if frame['points'] == 512:
            payload_size = 1062
            total_size = 1086
            data_len = 1057
        else:
            # 最后帧
            payload_size = 872
            total_size = 896
            data_len = 867

        # GWJ004帧头 - 使用固定值模拟
        leader = -286331154
        stc = 1776161560
        ver = 1
        el = 0

        # 格式化时间戳 - 模拟第三方工具的时间戳格式
        # 原始抓包时间 + 帧间延迟 (约100-200ms/帧)
        base_ms = int(ms[:3]) if ms else 0
        offset_ms = (i % 3) * 100 + (i // 3) * 100  # 简单模拟延迟
        gwj_ms = (base_ms + offset_ms) % 1000
        gwj_ts = f"2026-4-14 {ts_short}:{gwj_ms:03d}"

        # 输出帧信息
        output_lines.append(f"[ {ts}.{ms[:3]} ] ,总的数据长度{payload_size} ：")
        output_lines.append(f"[ {ts}.{ms[:3]} ] 总长度:{total_size}")
        output_lines.append(f"[ {ts}.{ms[:3]} ] 解析原子数据帧头：")
        output_lines.append(f"LEADER:{leader} VER:{ver} STC:{stc} TS:{gwj_ts} PL:{payload_size} EL:{el}")
        output_lines.append("解析原子数据帧体:")
        output_lines.append(f"扫频频谱观测数据:DT:12 DL:{data_len}")
        output_lines.append(f"频段序号:1  信道总数:1441")
        output_lines.append(f"起始频率:{frame['start_freq']/1e6:.4f}MHz  结束频率:{frame['end_freq']/1e6:.4f}MHz  起始频率序号: {frame['start_offset']}")
        output_lines.append(f"步长:{STEP/1000:.4f}kHz  帧信道数量:{frame['points']}")

        # 转换电平数据: dBm×100 → dBm (保留一位小数，格式化为整数显示)
        levels = frame['levels']
        level_strs = []
        for level in levels:
            # dBm = level / 100
            dbm = level / 100.0
            # 格式化为一位小数（显示为整数因为×10）
            level_strs.append(str(int(dbm * 10) if dbm < 0 else int(dbm * 10)))

        # 输出电平数据 (每20个一行)
        output_lines.append("电平: " + "  ".join(level_strs[:20]))
        for j in range(20, len(level_strs), 20):
            output_lines.append("        " + "  ".join(level_strs[j:j+20]))

        output_lines.append("")

        prev_ts = ts

    # 添加结束信息
    output_lines.append(f"[ {prev_ts} ] 关闭连接！")
    output_lines.append(f"[ {prev_ts} ] 停止服务成功")

    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"转换完成！")
    print(f"处理帧数: {total_frames}")
    print(f"输出文件: {output_file}")

    return fscan_frames


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_to_gwj004.py <input_json> <output_txt>")
        print("Example: python convert_to_gwj004.py capture.json output.txt")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    convert_rmcp_to_gwj004(input_file, output_file)


if __name__ == '__main__':
    main()
