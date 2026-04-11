#!/usr/bin/env python3
"""
FSCAN 数据帧解析器

解析 rmcp_proxy 捕获的 FSCAN 业务数据
"""

import struct
import sys


def parse_fscan_frame(data: bytes) -> dict:
    """解析 FSCAN 数据帧

    RMCPTP 帧头 (18字节) + 业务数据

    业务数据头结构:
    - LEADER (4 bytes): 0xEEEE1DE6 (-286331154)
    - VER (1 byte): 版本号
    - STC (4 bytes): 时间戳计数器
    - TS (8 bytes): FILETIME 时间戳
    - PL (4 bytes): 负载长度
    - EL (2 bytes): 结束标记?

    扫频频谱观测数据结构:
    - DT (1 byte): 数据类型 (12 = FSCAN)
    - DL (4 bytes): 数据长度
    - 频段序号 (4 bytes)
    - 信道总数 (4 bytes)
    - 起始频率 (8 bytes, double)
    - 结束频率 (8 bytes, double)
    - 起始频率序号 (4 bytes)
    - 步长 (8 bytes, double)
    - 帧信道数量 (4 bytes)
    - 电平数据 (n * 2 bytes, short)
    """
    result = {
        'raw_size': len(data),
        'rmcp_header': None,
        'fscan_header': None,
        'error': None
    }

    # 解析 RMCPTP 帧头
    if len(data) < 18:
        result['error'] = f"数据长度 {len(data)} < 18 (RMCPTP头)"
        return result

    try:
        rmcp_header = struct.unpack('<LLHBBH', data[0:18])
        result['rmcp_header'] = {
            'dwLength': rmcp_header[0],
            'tmStamp': rmcp_header[1],
            'nVersion': rmcp_header[2],
            'nMsgType': rmcp_header[3],
            'nFlags': rmcp_header[4],
            'nCheckSum': rmcp_header[5]
        }
    except struct.error as e:
        result['error'] = f"RMCPTP头解析失败: {e}"
        return result

    # 业务数据起始位置
    payload = data[18:]
    offset = 0

    # 解析 FSCAN 数据头
    if len(payload) < 35:
        result['error'] = f"Payload 长度 {len(payload)} < 35"
        return result

    try:
        # LEADER (4 bytes) - 应该是 0xEEEE1DE6
        leader = struct.unpack('<I', payload[0:4])[0]
        ver = payload[4]  # VER (1 byte)
        stc = struct.unpack('<I', payload[5:9])[0]  # STC (4 bytes)
        ts = struct.unpack('<Q', payload[9:17])[0]  # TS (8 bytes)
        pl = struct.unpack('<I', payload[17:21])[0]  # PL (4 bytes)
        el = struct.unpack('<H', payload[21:23])[0]  # EL (2 bytes)

        result['fscan_header'] = {
            'LEADER': leader,
            'VER': ver,
            'STC': stc,
            'TS': ts,
            'PL': pl,
            'EL': el
        }

        offset = 23

        # 解析扫频数据内容
        if len(payload) - offset < 1:
            result['error'] = "没有足够的字节解析 DT"
            return result

        dt = payload[offset]  # DT (1 byte)
        offset += 1

        dl = struct.unpack('<I', payload[offset:offset+4])[0]
        offset += 4

        result['fscan_header']['DT'] = dt
        result['fscan_header']['DL'] = dl

        # 解析频段信息
        if len(payload) - offset >= 28:
            band_no = struct.unpack('<I', payload[offset:offset+4])[0]
            offset += 4

            total_channels = struct.unpack('<I', payload[offset:offset+4])[0]
            offset += 4

            start_freq = struct.unpack('<d', payload[offset:offset+8])[0]
            offset += 8

            end_freq = struct.unpack('<d', payload[offset:offset+8])[0]
            offset += 8

            start_index = struct.unpack('<I', payload[offset:offset+4])[0]
            offset += 4

            step = struct.unpack('<d', payload[offset:offset+8])[0]
            offset += 8

            result['fscan_header']['频段序号'] = band_no
            result['fscan_header']['信道总数'] = total_channels
            result['fscan_header']['起始频率'] = start_freq
            result['fscan_header']['结束频率'] = end_freq
            result['fscan_header']['起始频率序号'] = start_index
            result['fscan_header']['步长'] = step

        # 解析帧信道数量
        if len(payload) - offset >= 4:
            frame_channels = struct.unpack('<I', payload[offset:offset+4])[0]
            offset += 4
            result['fscan_header']['帧信道数量'] = frame_channels

            # 解析电平数据 (每个电平 2 bytes, little-endian short)
            level_count = (len(payload) - offset) // 2
            levels = []
            for i in range(level_count):
                if offset + 2 <= len(payload):
                    level = struct.unpack('<h', payload[offset:offset+2])[0]
                    levels.append(level)
                    offset += 2

            result['fscan_header']['电平数据'] = levels
            result['fscan_header']['电平数量'] = len(levels)

    except struct.error as e:
        result['error'] = f"FSCAN 解析失败: {e}"

    return result


def format_fscan(result: dict) -> str:
    """格式化输出 FSCAN 结果"""
    lines = []

    if result['error']:
        lines.append(f"错误: {result['error']}")
        return '\n'.join(lines)

    lines.append(f"原始数据长度: {result['raw_size']} bytes")
    lines.append("")

    if result['rmcp_header']:
        h = result['rmcp_header']
        lines.append("RMCPTP 帧头:")
        lines.append(f"  dwLength: {h['dwLength']}")
        lines.append(f"  nVersion: {h['nVersion']}")
        lines.append(f"  nMsgType: {h['nMsgType']} (0=DATA)")
        lines.append(f"  nFlags: 0x{h['nFlags']:02x}")
        lines.append(f"  nCheckSum: {h['nCheckSum']}")

        # 转换时间戳
        try:
            unix_time = (h['tmStamp'] - 116444736000000000) / 10000000
            from datetime import datetime
            dt = datetime.fromtimestamp(unix_time)
            lines.append(f"  FrameTime: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        except:
            pass

    lines.append("")

    if result['fscan_header']:
        h = result['fscan_header']
        lines.append("FSCAN 数据头:")

        for key in ['LEADER', 'VER', 'STC', 'DT', 'DL']:
            if key in h:
                lines.append(f"  {key}: {h[key]}")

        for key in ['频段序号', '信道总数', '起始频率序号', '帧信道数量']:
            if key in h:
                lines.append(f"  {key}: {h[key]}")

        for key in ['起始频率', '结束频率', '步长']:
            if key in h:
                lines.append(f"  {key}: {h[key]} Hz ({h[key]/1e6:.4f} MHz)")

        if '电平数据' in h:
            levels = h['电平数据']
            lines.append(f"  电平数量: {len(levels)}")
            if levels:
                lines.append(f"  电平样本 (前10个): {levels[:10]}")
                lines.append(f"  电平样本 (后10个): {levels[-10:]}")

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python parse_fscan_data.py <raw_file>")
        print("  解析 rmcp_proxy 捕获的 .raw 文件中的 FSCAN 数据")
        return 1

    raw_file = sys.argv[1]

    with open(raw_file, 'rb') as f:
        data = f.read()

    print(f"读取文件: {raw_file}")
    print(f"文件大小: {len(data)} bytes")
    print("")

    # 查找 FSCAN 数据帧 (nMsgType=0, nFlags=0x01)
    # 每个帧前18字节是RMCPTP头

    offset = 0
    frame_num = 0

    while offset + 18 < len(data):
        # 检查是否是 FSCAN 数据帧
        if offset + 18 <= len(data):
            header = struct.unpack('<LLHBBH', data[offset:offset+18])
            dwLength = header[0]
            nMsgType = header[3]
            nFlags = header[4]

            # nMsgType=0 且 nFlags=0x01 表示数据帧
            if nMsgType == 0 and nFlags == 0x01:
                frame_num += 1
                print(f"{'='*60}")
                print(f"FSCAN 数据帧 #{frame_num}")
                print(f"{'='*60}")

                frame_data = data[offset:offset+18+dwLength]
                result = parse_fscan_frame(frame_data)
                print(format_fscan(result))
                print("")

                offset += 18 + dwLength
            else:
                offset += 1
        else:
            break

    if frame_num == 0:
        print("未找到 FSCAN 数据帧")

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)