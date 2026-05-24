"""
PScan流数据分析工具 - 离线分析bin文件中的PScan分片数据

用法:
    python pscan_analyzer.py <bin文件路径>
"""

import struct
import sys
import os
from datetime import datetime

LOG_DIR = "D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/soap_proxy/logs"

def parse_stream_frame(data):
    """解析Stream帧 - 与transparent_proxy.py中的parse_stream_frame_data保持一致"""
    if len(data) < 26 or data[:4] != b'\xee\xee\xee\xee':
        return None

    pl = (data[18] << 8) | data[19]  # PL at bytes 18-19
    dt = data[24]
    dl = data[25]

    dt_names = {
        12: 'FSCAN', 13: 'DSCAN', 14: 'SGLFREQ',
        33: 'DSCAN_META', 36: 'DEVICE_INFO', 99: 'DSCAN_META', 201: 'PSD'
    }
    dt_name = dt_names.get(dt, f'DT{dt}')

    frame_len = 26 + pl
    if len(data) < frame_len:
        return None

    # 帧头26字节: sync(4) + timestamp(8) + device_id(10) + unknown(2) + dt(1) + dl(1) = 26
    # payload从byte 26开始
    payload = data[26:frame_len]

    counters = None
    total_channels = 0
    # counters在payload[4:12]
    if len(payload) >= 12:
        try:
            counters = struct.unpack('<4h', payload[4:12])
            if counters and counters[0] > 0:
                total_channels = counters[0]
        except:
            pass

    return {
        'dt': dt,
        'dt_name': dt_name,
        'pl': pl,
        'dl': dl,
        'frame_len': frame_len,
        'counters': counters,
        'total_channels': total_channels,
        'payload': payload
    }


def analyze_pscan_stream(bin_file_path):
    """分析PScan流文件"""
    print(f"分析文件: {bin_file_path}")

    with open(bin_file_path, 'rb') as f:
        data = f.read()

    print(f"文件大小: {len(data)} bytes")

    # 查找所有EEEE帧
    pos = 0
    frame_num = 0
    frames = []

    while pos < len(data) - 26:
        sync_pos = data.find(b'\xee\xee\xee\xee', pos)
        if sync_pos == -1:
            break

        if sync_pos + 26 > len(data):
            break

        pl = (data[sync_pos + 18] << 8) | data[sync_pos + 19]
        frame_len = 26 + pl

        if sync_pos + frame_len > len(data):
            break

        frame_data = data[sync_pos:sync_pos + frame_len]
        parsed = parse_stream_frame(frame_data)

        if parsed:
            # 计算gap（当前帧结束到下一帧开始之间的数据）
            gap_start = sync_pos + frame_len
            next_sync = data.find(b'\xee\xee\xee\xee', gap_start)

            gap_spectrum = []
            if next_sync > gap_start:
                gap_data = data[gap_start:next_sync]
                if len(gap_data) >= 2 and len(gap_data) % 2 == 0:
                    num_vals = len(gap_data) // 2
                    gap_spectrum = list(struct.unpack(f'<{num_vals}h', gap_data))

            frames.append({
                'frame_num': frame_num + 1,
                'offset': sync_pos,
                'dt_name': parsed['dt_name'],
                'dt': parsed['dt'],
                'pl': parsed['pl'],
                'total_channels': parsed['total_channels'],
                'counters': parsed['counters'],
                'gap_spectrum': gap_spectrum,
                'gap_size': len(gap_spectrum) if gap_spectrum else 0
            })

        pos = sync_pos + frame_len
        frame_num += 1

    print(f"找到 {len(frames)} 个帧")

    # 分析分片重组
    if not frames:
        return

    # 收集PScan相关的FSCAN帧
    pscan_frames = [f for f in frames if f['dt_name'] in ('FSCAN', 'DSCAN') and f['total_channels'] > 0]

    if not pscan_frames:
        print("未找到PScan数据帧")
        return

    print(f"PScan数据帧: {len(pscan_frames)}")

    # 使用第一个帧的total_channels
    expected_total = pscan_frames[0]['total_channels']
    print(f"期望信道数: {expected_total}")

    # 重组分析
    accumulated = []
    scan_results = []

    for frame in pscan_frames:
        if frame['gap_size'] > 0:
            accumulated.extend(frame['gap_spectrum'])

            if len(accumulated) >= expected_total:
                # 完成一次扫描
                scan_data = accumulated[:expected_total]
                scan_results.append(scan_data)
                print(f"扫描 #{len(scan_results)}: {len(scan_data)} 点, gap片段累加")

                # 重置，准备下一次扫描
                accumulated = accumulated[expected_total:]

    print(f"\n重组结果: {len(scan_results)} 次完整扫描")

    # 输出日志文件
    if scan_results:
        log_file = os.path.join(LOG_DIR, f"pscan_analyzer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"PScan流分析结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"源文件: {bin_file_path}\n")
            f.write(f"文件大小: {len(data)} bytes\n")
            f.write(f"帧数量: {len(frames)}\n")
            f.write(f"PScan帧: {len(pscan_frames)}\n")
            f.write(f"期望信道: {expected_total}\n")
            f.write(f"重组扫描次数: {len(scan_results)}\n")
            f.write("=" * 80 + "\n\n")

            for i, scan in enumerate(scan_results):
                f.write(f"[扫描 #{i+1}] {len(scan)}点\n")
                if len(scan) <= 100:
                    f.write(f"  levels={scan}\n")
                else:
                    f.write(f"  levels={scan[:100]} ... (+{len(scan)-100} more)\n")
                f.write("\n")

        print(f"\n日志已写入: {log_file}")

        # 打印前3个扫描结果的前20个值
        print("\n前3个扫描结果预览:")
        for i, scan in enumerate(scan_results[:3]):
            print(f"  扫描 #{i+1}: {scan[:20]} ...")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        # 默认分析最新的bin文件
        import glob
        logs_dir = LOG_DIR
        bin_files = glob.glob(os.path.join(logs_dir, "stream_*.bin"))
        if bin_files:
            bin_files.sort(key=os.path.getmtime, reverse=True)
            bin_file = bin_files[0]
            print(f"使用最新文件: {bin_file}")
        else:
            print("请提供bin文件路径")
            sys.exit(1)
    else:
        bin_file = sys.argv[1]

    analyze_pscan_stream(bin_file)