"""
RMCPTP 协议解析器
从 pcap 文件中提取并解析 RMCPTP 帧

用法:
    python rmcp_parser.py                          # 解析默认文件 rmcp_capture.pcap
    python rmcp_parser.py capture.pcap            # 解析指定文件
    python rmcp_parser.py capture.pcap --detail   # 显示详细解析
"""

import struct
import sys
import os
import argparse
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

# ============================================================================
# RMCPTP 协议配置
# ============================================================================

RMCPTP_HEADER_SIZE = 18
BUSINESS_HEADER_SIZE = 11

RMCPTP_DATA_TYPE = {
    0x00: '监测业务数据',
    0x01: '音频描述头',
    0x02: '音频数据',
    0x03: '分发请求',
    0x04: '信息数据',
    0x06: '业务数据描述头',
}

BUSINESS_DATA_TYPE = {
    0x10: 'SGLFREQ',       # 单频测量
    0x11: 'IFANALYSIS',    # 中频分析
    0x12: 'DF',            # 单频测向
    0x13: 'IFDF',          # 中频测向
    0x14: 'DFSEARCH',      # 搜索测向
    0x15: 'FSCAN',         # 频段扫描
    0x16: 'DSCAN',         # 数字扫描
    0x17: 'PSCAN',         # 频谱扫描
    0x18: 'SPANALYSIS',    # 频谱分析
    0x19: 'WBMONDF',       # 宽带监测测向
    0x1A: 'TDANALYSIS',    # 时域分析
    0x1C: 'WBFFTMon',      # 宽带FFT观测
    0x1D: 'DIGDEM',        # IQ数字解调
    0x1F: 'EDETN',         # 能量探测
    0x22: 'MODREC',        # 信号识别
    0x24: 'ITUMEAS',       # ITU测量
}


# ============================================================================
# RMCPTP 解析器
# ============================================================================

class RMCPTPFrame:
    """RMCPTP 帧"""
    def __init__(self, timestamp: float, src_ip: str, dst_ip: str,
                 src_port: int, dst_port: int, direction: str,
                 raw_data: bytes):
        self.timestamp = timestamp
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.direction = direction  # "req" (atom->device) or "resp" (device->atom)
        self.raw_data = raw_data
        self.header: Optional[Dict[str, Any]] = None
        self.business_header: Optional[Dict[str, Any]] = None
        self.business_data: Optional[Dict[str, Any]] = None
        self.parse_error: Optional[str] = None

    def parse(self):
        """解析帧"""
        try:
            if len(self.raw_data) < RMCPTP_HEADER_SIZE:
                self.parse_error = f"数据长度不足: {len(self.raw_data)} < {RMCPTP_HEADER_SIZE}"
                return

            # 解析帧头
            self.header = self._parse_header(self.raw_data)

            # 解析业务数据
            business_raw = self.raw_data[RMCPTP_HEADER_SIZE:]
            if len(business_raw) >= BUSINESS_HEADER_SIZE:
                self.business_header, biz_content = self._parse_business_header(business_raw)

                if biz_content and self.business_header:
                    self.business_data = self._parse_business_data(
                        biz_content,
                        self.business_header['n_bd_type'],
                        self.business_header['n_arrays'],
                        self.business_header['n_flags']
                    )

        except Exception as e:
            self.parse_error = str(e)

    def _parse_header(self, data: bytes) -> Dict[str, Any]:
        """解析帧头"""
        dw_length, tm_stamp, n_version, n_data_type, n_flags, n_checksum = \
            struct.unpack('!IQHBBH', data[:RMCPTP_HEADER_SIZE])

        return {
            'dw_length': dw_length,
            'tm_stamp': tm_stamp,
            'n_version': n_version,
            'n_data_type': n_data_type,
            'n_data_type_name': RMCPTP_DATA_TYPE.get(n_data_type, f"0x{n_data_type:02X}"),
            'n_flags': n_flags,
            'n_checksum': n_checksum,
            'total_length': dw_length + RMCPTP_HEADER_SIZE
        }

    def _parse_business_header(self, data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """解析业务数据头"""
        n_bd_type, n_flags, n_arrays, n_offset = struct.unpack('!B H I I', data[:BUSINESS_HEADER_SIZE])

        return {
            'n_bd_type': n_bd_type,
            'n_bd_type_name': BUSINESS_DATA_TYPE.get(n_bd_type, f"0x{n_bd_type:02X}"),
            'n_flags': n_flags,
            'n_arrays': n_arrays,
            'n_offset': n_offset
        }, data[BUSINESS_HEADER_SIZE:]

    def _parse_business_data(self, data: bytes, bd_type: int, n_arrays: int, n_flags: int) -> Dict[str, Any]:
        """根据业务类型解析业务数据"""
        try:
            if bd_type == 0x10:  # SGLFREQ
                return self._parse_sglfreq(data, n_arrays)
            elif bd_type == 0x15:  # FSCAN
                return self._parse_fscan(data, n_arrays, n_flags)
            elif bd_type in (0x12, 0x13):  # DF, IFDF
                return self._parse_df(data)
            else:
                return {'raw_data': data.hex()[:64]}
        except Exception as e:
            return {'parse_error': str(e), 'raw_data': data.hex()[:64]}

    def _parse_sglfreq(self, data: bytes, n_arrays: int) -> Dict[str, Any]:
        """解析 SGLFREQ 单频测量数据"""
        result = {'frequency': 0, 'itu_values': []}

        if len(data) < 8:
            return result

        freq = struct.unpack('!Q', data[:8])[0]
        result['frequency'] = freq

        offset = 8
        for i in range(min(n_arrays, 10)):
            if len(data) >= offset + 8:
                itu_value, occ, thr = struct.unpack('!f h h', data[offset:offset + 8])
                result['itu_values'].append({
                    'value': itu_value,
                    'occupancy': occ / 100.0,
                    'threshold': thr / 100.0
                })
                offset += 8

        return result

    def _parse_fscan(self, data: bytes, n_arrays: int, n_flags: int) -> Dict[str, Any]:
        """解析 FSCAN 频段扫描数据"""
        result = {
            'values': [],
            'has_auto_noise': bool(n_flags & 0x02),
            'has_occupancy': bool(n_flags & 0x04),
            'has_manual_noise': bool(n_flags & 0x08)
        }

        for i in range(min(n_arrays, 200)):
            if len(data) >= (i + 1) * 2:
                level = struct.unpack('!h', data[i * 2:(i + 1) * 2])[0]
                result['values'].append(level / 100.0)

        if n_arrays > 200:
            result['values'].append(f'... 还有 {n_arrays - 200} 个点')

        return result

    def _parse_df(self, data: bytes) -> Dict[str, Any]:
        """解析 DF 测向数据"""
        if len(data) < 20:
            return {'error': '数据长度不足'}

        level, df_level, quality, azimuth, elevation, compass = struct.unpack('!hhff ff', data[:20])

        return {
            'level': level / 100.0,
            'df_level': df_level / 100.0,
            'quality': quality,
            'azimuth': azimuth,
            'elevation': elevation,
            'compass': compass
        }

    def to_summary(self) -> str:
        """生成摘要"""
        ts = datetime.fromtimestamp(self.timestamp).strftime('%H:%M:%S.%f')[:-3]

        arrow = ">>>" if self.direction == "req" else "<<<"
        lines = [f"\n{ts} {arrow} {'atom -> device' if self.direction == 'req' else 'device -> atom'}"]

        if self.parse_error:
            lines.append(f"  [解析错误] {self.parse_error}")
            lines.append(f"  [原始数据] {self.raw_data.hex(' ')}")
            return "\n".join(lines)

        if self.header:
            h = self.header
            lines.append(f"  帧头: dwLength={h['dw_length']}, nDataType={h['n_data_type_name']}, "
                        f"nFlags=0x{h['n_flags']:02X}, Version=0x{h['n_version']:04X}")

        if self.business_header:
            bh = self.business_header
            lines.append(f"  业务: nBdType={bh['n_bd_type_name']}, nArrays={bh['n_arrays']}, "
                        f"nFlags=0x{bh['n_flags']:04X}")

        if self.business_data:
            lines.append(f"  数据: {self.business_data}")

        return "\n".join(lines)

    def to_detail(self) -> str:
        """生成详细输出"""
        lines = [self.to_summary()]

        if self.header:
            h = self.header
            lines.append(f"    帧头详情:")
            lines.append(f"      dwLength (报文长度): {h['dw_length']} bytes")
            lines.append(f"      tmStamp (时间戳): {h['tm_stamp']}")
            lines.append(f"      nVersion (版本号): 0x{h['n_version']:04X}")
            lines.append(f"      nDataType (数据类型): 0x{h['n_data_type']:02X} ({h['n_data_type_name']})")
            lines.append(f"      nFlags (标志位): 0x{h['n_flags']:02X}")
            lines.append(f"      nCheckSum (校验和): 0x{h['n_checksum']:04X}")
            lines.append(f"      total_length (总长度): {h['total_length']} bytes")

        if self.business_header:
            bh = self.business_header
            lines.append(f"    业务头详情:")
            lines.append(f"      nBdType (业务类型): 0x{bh['n_bd_type']:02X} ({bh['n_bd_type_name']})")
            lines.append(f"      nFlags (业务标志): 0x{bh['n_flags']:04X}")
            lines.append(f"      nArrays (数组数目): {bh['n_arrays']}")
            lines.append(f"      nOffset (偏移量): {bh['n_offset']}")

        lines.append(f"    原始数据: {self.raw_data.hex(' ')}")

        return "\n".join(lines)


# ============================================================================
# PCAP 解析器
# ============================================================================

def read_pcap(filepath: str) -> list:
    """读取 pcap 文件并返回 RMCPTP 帧列表"""
    frames = []

    try:
        from scapy.all import rdpcap, IP, TCP
    except ImportError:
        print("错误: 需要安装 scapy")
        print("运行: pip install scapy")
        sys.exit(1)

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return frames

    print(f"读取文件: {filepath}")
    print(f"文件大小: {os.path.getsize(filepath)} bytes")

    try:
        packets = rdpcap(filepath)
        print(f"数据包数量: {len(packets)}\n")
    except Exception as e:
        print(f"读取 pcap 文件错误: {e}")
        return frames

    # TCP 流重组
    tcp_streams = {}

    for pkt in packets:
        if not pkt.haslayer(IP) or not pkt.haslayer(TCP):
            continue

        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        payload = bytes(pkt[TCP].payload)

        if not payload:
            continue

        # 判断方向 (atom -> device 为请求)
        # 假设 atom 发起连接，所以源端口小的是 atom
        direction = "req" if tcp_sport < tcp_dport else "resp"

        # 用五元组做 key 进行流重组
        stream_key = tuple(sorted([ip_src, ip_dst]) + [tcp_sport, tcp_dport])

        if stream_key not in tcp_streams:
            tcp_streams[stream_key] = []

        tcp_streams[stream_key].append({
            'timestamp': float(pkt.time),
            'src_ip': ip_src,
            'dst_ip': ip_dst,
            'src_port': tcp_sport,
            'dst_port': tcp_dport,
            'direction': direction,
            'payload': payload
        })

    # 解析每个 TCP 流的载荷
    for stream_key, packets_data in tcp_streams.items():
        for pkt_data in packets_data:
            frame = RMCPTPFrame(
                timestamp=pkt_data['timestamp'],
                src_ip=pkt_data['src_ip'],
                dst_ip=pkt_data['dst_ip'],
                src_port=pkt_data['src_port'],
                dst_port=pkt_data['dst_port'],
                direction=pkt_data['direction'],
                raw_data=pkt_data['payload']
            )
            frame.parse()
            frames.append(frame)

    # 按时间排序
    frames.sort(key=lambda x: x.timestamp)

    return frames


def print_statistics(frames: list):
    """打印统计信息"""
    print("=" * 60)
    print("统计信息")
    print("=" * 60)

    req_count = sum(1 for f in frames if f.direction == "req")
    resp_count = sum(1 for f in frames if f.direction == "resp")
    error_count = sum(1 for f in frames if f.parse_error)

    print(f"总帧数: {len(frames)}")
    print(f"请求帧: {req_count}")
    print(f"响应帧: {resp_count}")
    print(f"解析错误: {error_count}")

    # 按业务类型统计
    biz_types = {}
    for f in frames:
        if f.business_header:
            bt = f.business_header['n_bd_type_name']
            biz_types[bt] = biz_types.get(bt, 0) + 1

    if biz_types:
        print("\n业务类型分布:")
        for bt, count in sorted(biz_types.items()):
            print(f"  {bt}: {count}")

    print()


# ============================================================================
# 主入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='RMCPTP 协议解析器')
    parser.add_argument('file', nargs='?', default='rmcp_capture.pcap', help='pcap 文件路径')
    parser.add_argument('-d', '--detail', action='store_true', help='显示详细信息')
    parser.add_argument('-s', '--statistics', action='store_true', help='显示统计信息')
    parser.add_argument('-o', '--output', help='输出到文件')
    parser.add_argument('--no-summary', action='store_true', help='不显示摘要')

    args = parser.parse_args()

    # 读取并解析 pcap
    frames = read_pcap(args.file)

    if not frames:
        print("没有找到可解析的 RMCPTP 帧")
        print("\n提示:")
        print("1. 确认 pcap 文件存在且包含 TCP 流量")
        print("2. 确认目标端口是 9999")
        print("3. 确认抓包时使用了正确的过滤条件")
        return

    # 输出
    output = []

    # 统计
    if args.statistics or '-s' in sys.argv:
        print_statistics(frames)

    # 摘要
    if not args.no_summary:
        print("=" * 60)
        print("RMCPTP 帧解析结果")
        print("=" * 60)

        for frame in frames:
            if args.detail:
                output.append(frame.to_detail())
            else:
                output.append(frame.to_summary())

    result_text = "\n".join(output)

    # 打印
    print(result_text)

    # 保存
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result_text)
        print(f"\n结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
