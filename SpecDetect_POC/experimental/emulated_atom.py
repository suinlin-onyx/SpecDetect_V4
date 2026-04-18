#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Emulated Atom Service - 简化版

替代 Real Atom 的能力:
1. 接收 SOAP 请求，转发到目标设备
2. 接收目标设备回传的数据
3. 整理并转发给调用侧:
   - SOAP 回调 (HTTP响应)
   - streamsrc 回传 (TCP 18013端口)

端口映射:
- SOAP: 8283
- streamsrc: 18013
- 目标设备: 1449 (真实设备)

注意: 此版本使用模拟数据进行测试，因为 Real Device 可能不支持我们的命令格式
"""

import socket
import struct
import threading
import time
import random
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sys
import os
import io

# 设置输出编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 配置
SOAP_PORT = 8283
STREAMSRC_PORT = 18013
#TARGET_HOST = '127.0.0.1'
#TARGET_PORT = 9997  # 使用 9997 端口（emulated_atom 专用测试通道）
# TARGET_PORT = 9996  # 使用 9996 端口（与真实 Atom 相同）
TARGET_HOST = '100.72.95.36'  # 目标设备IP
TARGET_PORT = 1449             # 目标设备端口

# 设备信息缓存目录
DEVINFO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'devinfo')

# 日志
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'emulated_atom')
os.makedirs(LOG_DIR, exist_ok=True)

# 模拟数据开关
USE_MOCK_DATA = False  # 设为 False 尝试连接 Real Device

# 日志文件
LOG_FILE = os.path.join(LOG_DIR, f'emul_atom_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
DEBUG_LOG = open(LOG_FILE, 'w', encoding='utf-8')


def log(msg, prefix="ATOM"):
    """日志输出 - 带清晰前缀标识来源

    前缀规则:
    - ATOM: 主服务日志 (默认)
    - STREAM: streamsrc 服务器相关
    - SOAP: SOAP 处理相关
    - SESSION: Session 管理相关
    - RMCP: RMCP 通信相关
    - PARSE: 数据解析相关
    """
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    line = f"[{ts}] [{prefix:6}] {msg}"
    print(line, flush=True)
    DEBUG_LOG.write(line + '\n')
    DEBUG_LOG.flush()


# ==================== GWJ004 5.17 streamsrc 帧格式 ====================

# 数据帧头常量
STREAMSRC_LEADER = 0xEEEEEEEE  # 帧同步 (4 bytes)
STREAMSRC_VER = 0x0100         # 版本号 1.00 (2 bytes, big-endian)
STREAMSRC_EL = 0               # 扩展帧头长度 (1 byte)

# 数据类型 (GWJ004 5.14)
DT_FSCAN = 12                  # 频率扫描数据
DT_MSCAN = 13                 # 频率时间扫描
DT_IQ = 6                     # IQ数据
DT_SPECTRUM = 7               # 频谱数据

# RMCP 功能 ID
FUNCID_FSCAN = 15
FUNCID_MSCAN = 16
FUNCID_ITU = 20
FUNCID_SPECTRUM = 30

# RMCP MSG TYPE
MSG_TYPE_REQUEST = 90
MSG_TYPE_RESPONSE = 6
MSG_TYPE_DATA_1 = 29
MSG_TYPE_DATA_2 = 95


def get_msg_type_name(msg_type):
    """获取消息类型名称"""
    names = {
        MSG_TYPE_REQUEST: 'REQUEST',
        MSG_TYPE_RESPONSE: 'RESPONSE',
        MSG_TYPE_DATA_1: 'DATA_29',
        MSG_TYPE_DATA_2: 'DATA_95',
    }
    return names.get(msg_type, f'UNKNOWN({msg_type})')


def format_filetime(timestamp: int) -> str:
    """将 FILETIME 转换为可读时间"""
    try:
        unix_time = (timestamp - FILETIME_EPOCH) / 10000000
        dt = datetime.fromtimestamp(unix_time)
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    except:
        return str(timestamp)


class RMCPFrameLogger:
    """RMCP 帧日志记录器"""

    def __init__(self, log_dir: str, port: int):
        self.log_dir = log_dir
        self.port = port
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join(log_dir, f'capture_{port}_{timestamp}.log')
        self.json_file = os.path.join(log_dir, f'capture_{port}_{timestamp}.json')
        self.frames = []
        # 初始化日志文件头
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RMCP Traffic Capture Log (Emulated Atom)\n")
            f.write(f"Session: {timestamp}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

    def _parse_fscan_payload(self, payload: bytes) -> dict:
        """解析 FSCAN payload，返回解析结果"""
        if len(payload) < 25:
            return {}

        try:
            n_bd_type = payload[0]
            if n_bd_type != 15:
                return {}

            # counters (4 x int16 little-endian)
            counters = struct.unpack('<4h', payload[3:11])
            n_arrays = counters[0]

            if n_arrays == 0 or n_arrays > 2000:
                return {}

            # 解析 levels
            spectrum_offset = 11
            levels = []
            for i in range(min(n_arrays, 512)):
                if spectrum_offset + 2 > len(payload):
                    break
                level_raw = struct.unpack('<h', payload[spectrum_offset:spectrum_offset+2])[0]
                levels.append(level_raw)
                spectrum_offset += 2

            if not levels:
                return {}

            # 计算 dBm
            dbm_values = [v / 10.0 for v in levels]
            return {
                'data_type': 'SIMPLE_FSCAN',
                'nBdType': n_bd_type,
                'counters': list(counters),
                'nArrays': n_arrays,
                'level_count': len(levels),
                'level_min': min(levels),
                'level_max': max(levels),
                'dbm_min': min(dbm_values),
                'dbm_max': max(dbm_values),
                'dbm_avg': sum(dbm_values) / len(dbm_values),
                'levels': levels[:100]  # 只保存前100个作为样本
            }
        except Exception:
            return {}

    def log_frame(self, direction: str, data: bytes, addr: tuple):
        """记录 RMCP 帧"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # 解析帧头
        if len(data) < 18:
            return

        dw_length = struct.unpack('<I', data[0:4])[0]
        tm_stamp = struct.unpack('<Q', data[4:12])[0]
        n_version = struct.unpack('>H', data[12:14])[0]
        n_msg_type = data[14]
        n_flags = data[15]
        n_checksum = struct.unpack('<H', data[16:18])[0]

        msg_type_name = get_msg_type_name(n_msg_type)

        # 解析 FSCAN payload (如果 nMsgType=0)
        extra = ""
        fscan_info = {}
        if n_msg_type == 0 and len(data) >= 18:
            payload = data[18:]
            fscan_info = self._parse_fscan_payload(payload)
            if fscan_info.get('dbm_min') is not None:
                extra = f" | {fscan_info['level_count']} points | dBm: {fscan_info['dbm_min']:.1f}~{fscan_info['dbm_max']:.1f}"

        # 终端输出 - 目标设备风格
        console_line = f"[{timestamp}]:{self.port} {direction:4s} {msg_type_name:12s} len={len(data):5d} from={addr[0]}:{addr[1]}{extra}"
        print(console_line, flush=True)

        # 文件日志
        frame_info = {
            'timestamp': timestamp,
            'direction': direction,
            'src': addr[0],
            'src_port': addr[1],
            'size': len(data),
            'header': {
                'dwLength': dw_length,
                'nVersion': n_version,
                'nMsgType': n_msg_type,
                'nMsgTypeName': msg_type_name,
                'nFlags': n_flags,
                'nCheckSum': n_checksum,
                'FrameTime': format_filetime(tm_stamp)
            }
        }
        if fscan_info:
            frame_info['fscan'] = fscan_info

        self.frames.append(frame_info)

        # 写入日志文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"Time: {timestamp}:{self.port}\n")
            f.write(f"Direction: {direction}\n")
            f.write(f"Source: {addr[0]}:{addr[1]}\n")
            f.write(f"Size: {len(data)} bytes\n")
            f.write(f"Frame Header:\n")
            f.write(f"  dwLength: {dw_length}\n")
            f.write(f"  nVersion: {n_version}\n")
            f.write(f"  nMsgType: {n_msg_type} ({msg_type_name})\n")
            f.write(f"  nFlags: 0x{n_flags:02x}\n")
            f.write(f"  nCheckSum: {n_checksum}\n")
            f.write(f"  FrameTime: {format_filetime(tm_stamp)}\n")

            if fscan_info:
                f.write(f"\nFSCAN Data:\n")
                f.write(f"  电平数量: {fscan_info.get('level_count', 0)}\n")
                if fscan_info.get('dbm_min') is not None:
                    f.write(f"  dBm范围: {fscan_info['dbm_min']:.1f} ~ {fscan_info['dbm_max']:.1f} (avg: {fscan_info['dbm_avg']:.1f})\n")
                f.write(f"  Counters: {fscan_info.get('counters', [])}\n")
                if fscan_info.get('levels'):
                    dbm_sample = [f"{v/10:.1f}" for v in fscan_info['levels'][:20]]
                    f.write(f"  dBm样本: [{', '.join(dbm_sample)}]\n")

            f.write("\n" + "-" * 80 + "\n\n")

        # 写入 JSON
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.frames, f, ensure_ascii=False, indent=2)
        except:
            pass

# FILETIME epoch (100纳秒间隔，从1601-01-01开始)
FILETIME_EPOCH = 116444736000000000


def _get_filetime() -> int:
    """获取当前 FILETIME 时间戳"""
    return int(time.time() * 10000000) + FILETIME_EPOCH


def _get_current_stc() -> int:
    """获取当前同步通道号 (简单的递增计数器)"""
    # 使用时间作为基础，配合计数器避免重复
    return int(time.time() * 1000) & 0xFFFFFFFF


def _get_streamsrc_timestamp() -> bytes:
    """生成与真实设备匹配的 streamsrc 时间戳 (8 bytes)

    格式: [year_lo, year_hi, month, day, hour, minute, second, ms]
    - year: 2 bytes little-endian (e.g., 0x07ea = 2026)
    - month, day, hour, minute, second, ms: 1 byte each
    """
    now = time.localtime()
    year = now.tm_year
    month = now.tm_mon
    day = now.tm_mday
    hour = now.tm_hour
    minute = now.tm_min
    second = now.tm_sec
    ms = int(time.time() * 1000) % 256  # 当前毫秒，取低字节 (真实设备用1字节)

    # Year in little-endian 2 bytes
    year_bytes = struct.pack('<H', year)  # little-endian
    # Rest of the fields
    rest = bytes([month, day, hour, minute, second, ms])

    return year_bytes + rest


def build_streamsrc_frame(spectrum_data: list,
                          dt: int = DT_FSCAN,
                          stc: int = None,
                          ts: int = None,
                          metadata: list = None,
                          start_index: int = 0) -> bytes:
    """
    构建 streamsrc 1086 字节 FSCAN-529 数据帧

    帧格式 (1086 bytes):
    - Offset 0-3:   Sync (0xEEEEEEEE)
    - Offset 4-61:  Header + Metadata
    - Offset 62+:    Spectrum (交替字节模式 [dBm][0xFF][dBm][0xFF]...)

    频谱编码:
    - dBm 值转换为字节: value = 256 + dBm (dBm < 0时)
    - 交替放置 0xFF 作为分隔符

    Args:
        spectrum_data: 频谱数据点 (list of dBm values)
        dt: 数据类型 (默认 12=FSCAN)
        stc: 同步通道号 (默认自动生成)
        ts: FILETIME 时间戳 (默认自动生成)
        start_index: 起始频率序号 (Band1=0, Band2=512)
        metadata: 元数据列表 (默认 [16801, 0, 0, 20480, 18115, 512, 0])

    Returns:
        streamsrc 1086 字节数据帧 (bytes)
    """
    spectrum_dbm = [float(level) for level in spectrum_data[:512]]
    n_points = len(spectrum_dbm)

    if stc is None:
        stc = _get_current_stc()
    if ts is None:
        ts = _get_streamsrc_timestamp()

    # frame_counter 用于生成动态 metadata
    if not hasattr(build_streamsrc_frame, '_counter'):
        build_streamsrc_frame._counter = 0
    frame_counter = build_streamsrc_frame._counter
    build_streamsrc_frame._counter += 1

    if metadata is None:
        # metadata 字段参考真实设备捕获
        metadata = [
            16801,                            # [0]: 固定 (真实设备用 16801)
            0,                                # [1]: 固定 0 (真实设备也是 0)
            0,                                # [2]: 0
            20480,                            # [3]: 固定
            18115,                            # [4]: 固定
            512,                              # [5]: 512 点
            0                                 # [6]: 0
        ]

    # 构建 1086 字节帧
    frame = bytearray(1086)

    # Offset 0-3: Sync (4 bytes)
    struct.pack_into('<I', frame, 0, STREAMSRC_LEADER)

    # Offset 4-5: VER (2 bytes, big-endian)
    struct.pack_into('>H', frame, 4, STREAMSRC_VER)

    # Offset 6-9: STC (4 bytes, little-endian)
    struct.pack_into('<I', frame, 6, stc)

    # Offset 10-17: TS (8 bytes, encoded timestamp)
    if isinstance(ts, bytes):
        frame[10:18] = ts
    else:
        struct.pack_into('<Q', frame, 10, ts)

    # Offset 18-19: Indicator (2 bytes, big-endian)
    # 根据start_index设置不同的indicator，与Real Atom一致
    if start_index == 0:
        # Band1: 0x0026
        struct.pack_into('>H', frame, 18, 0x0026)
    elif start_index == 512:
        # Band2: 0x0126
        struct.pack_into('>H', frame, 18, 0x0126)
    else:
        # Band3 (FSCAN-434): 0x0168
        struct.pack_into('>H', frame, 18, 0x0168)

    # Offset 20-23: FSCAN-529 type indicator = 0x04000000
    frame[20:24] = bytes([0x04, 0x00, 0x00, 0x00])

    # Offset 24: DT (1 byte) = 0x0C (FSCAN)
    frame[24] = 0x0C

    # Offset 25-28: DL (4 bytes, little-endian) = payload length (频谱1024 + metadata 33 = 1057)
    struct.pack_into('<I', frame, 25, 1057)

    # Offset 29-61: Private metadata (33 bytes) - 按真实设备格式
    # 注意: 不同Band使用不同的private_metadata，编码了频率范围信息
    # 来源: Real Atom pcap capture_1449_20260416_190539 中提取的实际数据
    if start_index == 0:
        # Band1: 137.0 - 149.775 MHz
        private_metadata = bytes([
            0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x80, 0xe8, 0x54, 0xa0, 0x41, 0x00, 0x00, 0x00,
            0x30, 0xc5, 0xda, 0xa1, 0x41, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x50, 0xc3, 0x46, 0x00, 0x02, 0x00,
            0x00
        ])
    elif start_index == 512:
        # Band2: 149.8 - 162.575 MHz
        private_metadata = bytes([
            0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x80, 0x88, 0xdb, 0xa1, 0x41, 0x00, 0x00, 0x00,
            0x30, 0x65, 0x61, 0xa3, 0x41, 0x00, 0x02, 0x00,
            0x00, 0x00, 0x50, 0xc3, 0x46, 0x00, 0x02, 0x00,
            0x00
        ])
    else:
        # Band3: 162.6 - 173.0 MHz
        private_metadata = bytes([
            0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x80, 0x28, 0x62, 0xa3, 0x41, 0x00, 0x00, 0x00,
            0x80, 0x8a, 0x9f, 0xa4, 0x41, 0x00, 0x04, 0x00,
            0x00, 0x00, 0x50, 0xc3, 0x46, 0xa1, 0x01, 0x00,
            0x00
        ])
    frame[29:62] = private_metadata

    # 设置 start_index (frame[50:52] = little-endian uint16)
    # Band1: start_index=0, Band2: start_index=512
    struct.pack_into('<H', frame, 50, start_index)

    # Offset 62+: Spectrum (交替字节模式 [dBm][0xFF][dBm][0xFF]...)
    # dBm 转换为字节: value = 256 + dBm (当 dBm < 0)
    # 例如: -84 -> 172, -70 -> 186
    spectrum_offset = 62
    for dbm in spectrum_dbm:
        # dBm 转字节: value = 256 + dBm (dBm < 0)
        if dbm < 0:
            byte_val = int(256 + dbm)
        else:
            byte_val = int(dbm)
        frame[spectrum_offset] = byte_val
        frame[spectrum_offset + 1] = 0xFF
        spectrum_offset += 2

    return bytes(frame)


def build_streamsrc_frame_simple(spectrum_data: list, n_bd_type: int = 15) -> bytes:
    """
    简化版 streamsrc 帧 (兼容旧接口)

    Args:
        spectrum_data: 512点频谱数据 (dBm值)
        n_bd_type: 数据类型 (15=FSCAN)

    Returns:
        1086字节的 streamsrc 帧
    """
    return build_streamsrc_frame(spectrum_data, dt=DT_FSCAN)


def build_streamsrc_frame_434(spectrum_data: list,
                              stc: int = None,
                              ts: int = None,
                              n_arrays: int = 417,
                              start_index: int = 1024) -> bytes:
    """
    构建 streamsrc 896 字节 FSCAN-434 数据帧

    帧格式 (896 bytes):
    - Offset 0-3:   Sync (0xEEEEEEEE)
    - Offset 4-61:  Header + Metadata
    - Offset 62+:    Spectrum (417 点, 交替字节模式)

    Args:
        spectrum_data: 频谱数据点 (list of dBm values, 取前 417 点)
        stc: 同步通道号 (默认自动生成)
        ts: FILETIME 时间戳 (默认自动生成)
        n_arrays: 数据点数 (默认 417)
        start_index: 起始序号 (默认 1024, 对应band3)

    Returns:
        streamsrc 896 字节数据帧 (bytes)
    """
    spectrum_dbm = [float(level) for level in spectrum_data[:n_arrays]]

    if stc is None:
        stc = _get_current_stc()
    if ts is None:
        ts = _get_streamsrc_timestamp()

    # frame_counter 用于生成动态 metadata
    if not hasattr(build_streamsrc_frame_434, '_counter'):
        build_streamsrc_frame_434._counter = 0
    frame_counter = build_streamsrc_frame_434._counter
    build_streamsrc_frame_434._counter += 1

    # 根据起始序号确定频段参数
    # start_index: 0=band1, 512=band2, 1024=band3
    if start_index == 1024:
        # Band3: 162.6-173.0MHz
        start_freq = 162600000.0
        stop_freq = 173000000.0
    elif start_index == 512:
        # Band2: 149.8-162.575MHz
        start_freq = 149800000.0
        stop_freq = 162575000.0
    else:
        # Band1: 137.0-149.775MHz
        start_freq = 137000000.0
        stop_freq = 149775000.0

    metadata = [
        16804 + frame_counter,  # [0]: 帧计数
        start_index,            # [1]: 起始序号
        0,                      # [2]: 0
        20480,                  # [3]: 固定
        18115,                  # [4]: 固定
        n_arrays,               # [5]: 数据点数
        0                       # [6]: 0
    ]

    # 构建 896 字节帧
    frame = bytearray(896)

    # Offset 0-3: Sync (4 bytes)
    struct.pack_into('<I', frame, 0, STREAMSRC_LEADER)

    # Offset 4-5: VER (2 bytes, big-endian)
    struct.pack_into('>H', frame, 4, STREAMSRC_VER)

    # Offset 6-9: STC (4 bytes, little-endian)
    struct.pack_into('<I', frame, 6, stc)

    # Offset 10-17: TS (8 bytes, encoded timestamp)
    if isinstance(ts, bytes):
        frame[10:18] = ts
    else:
        struct.pack_into('<Q', frame, 10, ts)

    # Offset 18-19: Indicator (2 bytes, big-endian) = 0x0168 for FSCAN-434 Band3
    struct.pack_into('>H', frame, 18, 0x0168)

    # Offset 20-23: FSCAN-434 type indicator = 0x03000000
    frame[20:24] = bytes([0x03, 0x00, 0x00, 0x00])

    # Offset 24: DT (1 byte) = 0x0C (FSCAN)
    frame[24] = 0x0C

    # Offset 25-28: DL (4 bytes, little-endian) = payload length (频谱834 + metadata 33 = 867)
    struct.pack_into('<I', frame, 25, 867)

    # Offset 29-61: Private metadata (33 bytes) - FSCAN-434 Band3 专用
    # 从 Real Atom pcap 中提取的实际数据
    # Band3: 162.6 - 173.0 MHz
    private_metadata_434 = bytes([
        0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,  # 0-7
        0x80, 0x28, 0x62, 0xa3, 0x41, 0x00, 0x00, 0x00,  # 8-15
        0x80, 0x8a, 0x9f, 0xa4, 0x41, 0x00, 0x04, 0x00,  # 16-23
        0x00, 0x00, 0x50, 0xc3, 0x46, 0xa1, 0x01, 0x00,  # 24-31
        0x00                                           # 32
    ])
    frame[29:62] = private_metadata_434

    # Offset 62+: Spectrum (交替字节模式 [dBm][0xFF][dBm][0xFF]...)
    spectrum_offset = 62
    for dbm in spectrum_dbm:
        if dbm < 0:
            byte_val = int(256 + dbm)
        else:
            byte_val = int(dbm)
        frame[spectrum_offset] = byte_val
        frame[spectrum_offset + 1] = 0xFF
        spectrum_offset += 2

    return bytes(frame)


class BandCollector:
    """三频段收集器 - 使用 Queue 实现严格 FIFO 同步

    设备持续发送频段数据（可能乱序），此收集器确保：
    1. 按收到顺序处理每帧数据
    2. 只有凑齐完整三频段才输出（顺序: Band1 → Band2 → Band3）
    3. 线程安全，支持多生产者/单消费者
    """

    def __init__(self, timeout=2.0):
        import queue
        self._input_queue = queue.Queue(maxsize=200)  # 输入队列
        self._output_queue = queue.Queue(maxsize=10)  # 输出队列（完整三频段组）
        self._band_buffer = {}  # 当前缓冲: {start_index: band_data}
        self._timeout = timeout  # 超时时间（秒）
        self._logger_thread = None
        self._running = False

    def put(self, band_info):
        """放入一个频段数据（通常在接收线程中调用）"""
        self._input_queue.put(band_info)
        self.process_input()  # 自动处理，尝试组成完整三频段

    def get(self):
        """获取完整三频段组（阻塞等待）

        Returns:
            list: [Band1, Band2, Band3] 按顺序排列的频段列表
            None: 超时返回 None
        """
        # 先处理已有输入，避免长时间阻塞
        self.process_input()
        try:
            return self._output_queue.get(timeout=self._timeout)
        except:
            return None

    def process_input(self):
        """处理输入队列，尝试组成完整三频段（在消费者线程中调用）"""
        try:
            # 非阻塞尝试从输入队列获取数据
            while True:
                try:
                    band = self._input_queue.get_nowait()
                    start_idx = band['counters'][2]
                    self._band_buffer[start_idx] = band
                except:
                    break

            # 检查是否完整
            if 0 in self._band_buffer and 512 in self._band_buffer and 1024 in self._band_buffer:
                complete = [
                    self._band_buffer[0],
                    self._band_buffer[512],
                    self._band_buffer[1024]
                ]
                self._output_queue.put(complete)
                self._band_buffer.clear()

        except Exception as e:
            log(f"BandCollector process_input 错误: {e}")

    def clear(self):
        """清空缓冲"""
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except:
                break
        self._band_buffer.clear()
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except:
                break

    def get_status(self):
        """获取状态信息"""
        return {
            'input_size': self._input_queue.qsize(),
            'output_size': self._output_queue.qsize(),
            'buffer_keys': list(self._band_buffer.keys()),
            'has_band1': 0 in self._band_buffer,
            'has_band2': 512 in self._band_buffer,
            'has_band3': 1024 in self._band_buffer,
        }


# ==================== streamsrc 服务器 ====================

class StreamSession:
    """配对的 streamsrc/RMCP 会话"""

    def __init__(self, streamsrc_client: socket.socket, taskid: str, fscan_params: dict = None):
        self.streamsrc_client = streamsrc_client
        self.target_client: Optional[TargetDeviceClient] = None
        self.taskid = taskid
        self.lock = threading.Lock()
        self.data_received = False  # 是否收到过数据
        self.last_data_time = time.time()
        self.fscan_params = fscan_params or {}  # 存储 fscan 参数用于持续推送
        self.push_thread = None  # 推送线程
        self.push_running = False  # 推送运行标志 (保留用于兼容性，实际用_stop_event控制)
        self._stop_event = threading.Event()  # 线程停止事件
        self.debug_file = None  # 调试文件（一次fscan请求的所有帧保存在同一文件）
        self._fscan_bands_cache = None  # 缓存的 FSCAN bands 数据
        self._fscan_bands_time = 0  # 缓存时间戳
        self._closing = False  # 标记 session 正在关闭，不要在 _get_fscan_bands 中使用 target_client
        self._band_buffer = []  # 频段缓冲，用于收集未完成的频段
        self._band_buffer_time = 0  # 缓冲开始时间，用于判断超时
        self._fscan_request_sent = False  # 标记是否已发送 FSCAN RMCP 请求
        self._band_collector = None  # 三频段收集器（Queue实现）

    def attach_target(self, target_client: 'TargetDeviceClient'):
        """关联 RMCP 客户端"""
        with self.lock:
            self.target_client = target_client

    def close_all(self):
        """关闭所有连接（幂等操作）"""
        with self.lock:
            if self.streamsrc_client is None and self.target_client is None:
                log(f"连接已关闭，跳过", "SESSION")
                return
            log(f"关闭所有连接", "SESSION")
            # 停止推送线程 - 使用Event确保线程能正确收到停止信号
            self.push_running = False
            self._stop_event.set()
            # 标记正在关闭，这样 _get_fscan_bands 会检测到并提前返回
            self._closing = True
            # 关闭 streamsrc 客户端
            if self.streamsrc_client:
                try:
                    self.streamsrc_client.close()
                except Exception as e:
                    log(f"关闭 streamsrc 失败: {e}", "SESSION")
                self.streamsrc_client = None
            # 关闭 RMCP 客户端（延迟关闭，让 _get_fscan_bands 有机会检测到 _closing 并自行关闭）
            if self.target_client:
                try:
                    self.target_client.disconnect()
                except Exception as e:
                    log(f"关闭 target_client 失败: {e}", "SESSION")
                self.target_client = None

    def update_data_time(self):
        """更新最后收数据时间"""
        self.last_data_time = time.time()
        self.data_received = True


class SessionManager:
    """会话管理器 - 追踪所有配对的 streamsrc/RMCP 会话"""

    def __init__(self):
        self.sessions: Dict[socket.socket, StreamSession] = {}
        self.taskid_to_session: Dict[str, StreamSession] = {}
        self.lock = threading.Lock()

    def create_session(self, streamsrc_client: socket.socket, taskid: str) -> StreamSession:
        """创建新会话"""
        session = StreamSession(streamsrc_client, taskid)
        with self.lock:
            self.sessions[streamsrc_client] = session
            self.taskid_to_session[taskid] = session
        log(f"创建会话: taskid={taskid}, client={streamsrc_client.getpeername()}", "SESSION")
        return session

    def get_session_by_socket(self, sock: socket.socket) -> Optional[StreamSession]:
        """通过 socket 获取会话"""
        with self.lock:
            return self.sessions.get(sock)

    def get_session_by_taskid(self, taskid: str) -> Optional[StreamSession]:
        """通过 taskid 获取会话"""
        with self.lock:
            return self.taskid_to_session.get(taskid)

    def remove_session(self, sock: socket.socket):
        """移除会话"""
        with self.lock:
            if sock in self.sessions:
                session = self.sessions[sock]
                if session.taskid in self.taskid_to_session:
                    del self.taskid_to_session[session.taskid]
                del self.sessions[sock]
                return session
        return None

    def close_session(self, sock: socket.socket):
        """关闭并移除会话（成对关闭）"""
        session = self.remove_session(sock)
        if session:
            session.close_all()

    def get_active_sessions_count(self) -> int:
        """获取活跃会话数"""
        with self.lock:
            return len(self.sessions)


class StreamSrcServer:
    """streamsrc TCP 服务器 - 推送数据到连接的客户端"""

    def __init__(self, port: int, session_manager: SessionManager, atom_service=None):
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = []
        self.lock = threading.Lock()
        self.session_manager = session_manager
        self.atom_service = atom_service  # EmulatedAtomService 引用

    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.running = True
            log(f"streamsrc 服务器已启动: 0.0.0.0:{self.port}")

            thread = threading.Thread(target=self._accept_loop, daemon=True)
            thread.start()

        except Exception as e:
            log(f"streamsrc 服务器启动失败: {e}")
            raise

    def _accept_loop(self):
        """接受连接的循环"""
        log(f"_accept_loop started, running={self.running}", "STREAM")
        last_check_time = time.time()
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client_socket, client_addr = self.server_socket.accept()
                    log(f"客户端连接: {client_addr}", "STREAM")

                    with self.lock:
                        self.clients.append(client_socket)

                    # 尝试关联到已有的等待中的会话
                    self._try_match_pending_session(client_socket)

                except socket.timeout:
                    # 每3秒检查一次死客户端
                    now = time.time()
                    if now - last_check_time >= 3:
                        self._check_dead_clients()
                        last_check_time = now
                    continue
            except Exception as e:
                if self.running:
                    log(f"接受连接错误: {e}")

    def _check_dead_clients(self):
        """检查并移除死掉的客户端"""
        disconnected = []
        with self.lock:
            for client in self.clients:
                try:
                    # 设置短超时检测客户端是否存活
                    client.settimeout(0.1)
                    try:
                        # 尝试接收数据，如果客户端断开会抛出异常
                        data = client.recv(1, socket.MSG_PEEK)
                        if data == b'':
                            # 客户端关闭了连接
                            log(f"检测到死客户端", "STREAM")
                            disconnected.append(client)
                    except socket.timeout:
                        pass  # 客户端还活着
                    except (ConnectionResetError, BrokenPipeError, OSError) as e:
                        log(f"客户端已断开: {e}", "STREAM")
                        disconnected.append(client)
                except Exception as e:
                    log(f"检测客户端状态异常: {e}", "STREAM")
                    disconnected.append(client)

        # 移除死客户端并关闭对应的 RMCP 连接
        for client in disconnected:
            with self.lock:
                if client in self.clients:
                    self.clients.remove(client)
                    log(f"移除死客户端，剩余: {len(self.clients)}", "STREAM")
                else:
                    log(f"客户端不在 clients 列表中，可能已移除", "STREAM")
            # 成对关闭 RMCP - 先从 session_manager 移除，避免重复关闭
            session = self.session_manager.get_session_by_socket(client)
            if session:
                self.session_manager.remove_session(client)  # 确保只移除一次
                log(f"找到对应 session={session.taskid}，调用关闭", "STREAM")
                self._close_session_with_stop(session)
            else:
                log(f"未找到对应 session", "STREAM")

    def _try_match_pending_session(self, client_socket: socket.socket):
        """尝试将新客户端关联到等待中的会话

        从 atom_service.pending_sessions 获取最早的待关联会话并关联

        Registration frame 格式 (65 bytes):
        - Offset 00-03: Sync (0xEEEEEEEE)
        - Offset 04-07: Seq (uint32 LE)
        - Offset 08-11: Field1
        - Offset 12-15: Field2
        - Offset 16-17: Field3 (uint16 LE)
        - Offset 18-19: Field4 (uint16 LE)
        - Offset 20-23: Field5
        - Offset 24-25: TaskID length (uint16 LE) = 36
        - Offset 26-61: TaskID (36 bytes ASCII)
        """
        import struct

        atom = self.atom_service
        if not atom:
            log("没有 atom_service 引用，无法匹配 pending_session", "STREAM")
            return

        # 接收 registration frame (65 bytes)
        try:
            client_socket.settimeout(5.0)
            reg_data = b''
            while len(reg_data) < 65:
                chunk = client_socket.recv(65 - len(reg_data))
                if not chunk:
                    log("Registration frame 接收不完整", "STREAM")
                    client_socket.close()
                    return
                reg_data += chunk
            log(f"收到 Registration frame: {reg_data[:20].hex()}...", "STREAM")
        except socket.timeout:
            log("接收 Registration frame 超时", "STREAM")
            client_socket.close()
            return
        except Exception as e:
            log(f"接收 Registration frame 失败: {e}", "STREAM")
            client_socket.close()
            return

        # 解析 taskid (offset 29, 36 bytes ASCII)
        if reg_data[0:4] == b'\xee\xee\xee\xee':
            taskid_from_client = reg_data[29:65].decode('ascii', errors='replace').strip('\x00')
            log(f"从 Registration 提取 taskid: {taskid_from_client}", "STREAM")
        else:
            taskid_from_client = None
            log("Registration frame sync 不正确", "STREAM")

        # 查找匹配的 pending_session
        session = None
        if taskid_from_client:
            with atom.session_manager.lock:
                log(f"pending_sessions: {list(atom.pending_sessions.keys())}", "STREAM")
                log(f"taskid_from_client: {taskid_from_client}", "STREAM")
                if taskid_from_client in atom.pending_sessions:
                    session = atom.pending_sessions.pop(taskid_from_client)
                    log(f"按 taskid 匹配 pending_session: {taskid_from_client}", "STREAM")

        # 如果没找到，按先进先出匹配
        if not session:
            with atom.session_manager.lock:
                if atom.pending_sessions:
                    oldest_taskid = next(iter(atom.pending_sessions))
                    session = atom.pending_sessions.pop(oldest_taskid)
                    log(f"无 exact match，按 FIFO 匹配: {session.taskid}", "STREAM")

        if session:
            # 关联 streamsrc 客户端
            session.streamsrc_client = client_socket
            self.session_manager.sessions[client_socket] = session
            self.session_manager.taskid_to_session[session.taskid] = session

            # 添加到 clients 列表（用于 push_frame）
            with self.lock:
                self.clients.append(client_socket)

            # 发送 Registration ACK (回显收到的 Registration frame)
            self._send_registration_ack(client_socket, reg_data)

            log(f"关联 streamsrc 到 session: taskid={session.taskid}, rmcp={session.target_client is not None}", "STREAM")

            # 启动持续推送线程
            if session.fscan_params:
                self._start_fscan_push(session)

            return session

        # 没有待关联会话，创建一个新的
        taskid = f'SRC-{int(time.time())}'
        session = StreamSession(streamsrc_client=client_socket, taskid=taskid)
        with self.session_manager.lock:
            self.session_manager.sessions[client_socket] = session
            self.session_manager.taskid_to_session[taskid] = session

        # 添加到 clients 列表
        with self.lock:
            self.clients.append(client_socket)

        # 发送 Registration ACK
        self._send_registration_ack(client_socket, reg_data)

        log(f"新建会话: taskid={taskid}", "STREAM")
        return session

    def _start_fscan_push(self, session: StreamSession):
        """启动 FSCAN 持续推送线程"""
        def push_loop():
            log(f"启动 FSCAN 推送线程: taskid={session.taskid}", "STREAM")
            session.push_running = True
            session._stop_event.clear()  # 确保Event初始为未设置状态

            # 创建三频段收集器
            session._band_collector = BandCollector(timeout=2.0)

            # 调试：创建单一文件保存所有帧
            import os
            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            session.debug_file = os.path.join(debug_dir, f'sent_fscan_{int(time.time()*1000)}.bin')

            while not session._stop_event.is_set():
                try:
                    # 首次调用时，发送 RMCP REQUEST 并建立连接
                    if not session._fscan_request_sent:
                        success = self.atom_service._send_fscan_request(
                            session.fscan_params['start_freq'],
                            session.fscan_params['end_freq'],
                            session.fscan_params['step'],
                            session.fscan_params['taskid']
                        )
                        if success:
                            session._fscan_request_sent = True
                            log(f"已发送 FSCAN RMCP REQUEST", "STREAM")
                        else:
                            log(f"发送 FSCAN RMCP REQUEST 失败，使用模拟数据", "STREAM")
                            session._fscan_request_sent = True  # 标记避免重复尝试

                    # 循环读取设备数据直到收到完整三频段
                    all_bands = None
                    read_attempts = 0
                    while not session._stop_event.is_set():
                        # 读取设备数据并放入收集器
                        self.atom_service._read_fscan_bands(
                            session.fscan_params['start_freq'],
                            session.fscan_params['end_freq'],
                            session.fscan_params['step'],
                            session.fscan_params['taskid'],
                            session._band_collector
                        )

                        # 尝试获取完整三频段（非阻塞）
                        all_bands = session._band_collector.get()
                        if all_bands:
                            break  # 收到完整三频段

                        read_attempts += 1
                        if read_attempts > 100:  # 避免无限循环
                            log(f"读取三频段超时，已尝试 {read_attempts} 次", "STREAM")
                            break

                        time.sleep(0.05)  # 短暂等待让数据到达

                    if not all_bands:
                        # 仍然超时，继续下一次循环
                        continue

                    # 使用真实的 Band 映射（已按 Band1→Band2→Band3 顺序排列）
                    stc = session.fscan_params.get('stc')

                    for band in all_bands:
                        spectrum = band['levels']
                        counters = band['counters']
                        start_index = counters[2] if counters else 0
                        n_arrays = band['n_arrays']

                        # 数据验证：计算 dBm 统计
                        if spectrum:
                            dbm_min = min(spectrum)
                            dbm_max = max(spectrum)
                            dbm_avg = sum(spectrum) / len(spectrum)
                        else:
                            dbm_min = dbm_max = dbm_avg = 0

                        # 根据 start_index 确定 Band 类型
                        if start_index == 0 and n_arrays == 512:
                            streamsrc_frame = build_streamsrc_frame(spectrum, stc=stc, start_index=0)
                            log(f"推送 Band1: {len(spectrum)} 点, dBm范围: {dbm_min:.1f}~{dbm_max:.1f}", "STREAM")
                        elif start_index == 512 and n_arrays == 512:
                            streamsrc_frame = build_streamsrc_frame(spectrum, stc=stc, start_index=512)
                            log(f"推送 Band2: {len(spectrum)} 点, dBm范围: {dbm_min:.1f}~{dbm_max:.1f}", "STREAM")
                        elif start_index == 1024:
                            streamsrc_frame = build_streamsrc_frame_434(spectrum, stc=stc, n_arrays=n_arrays, start_index=1024)
                            log(f"推送 Band3: {len(spectrum)} 点, dBm范围: {dbm_min:.1f}~{dbm_max:.1f}", "STREAM")
                        else:
                            log(f"跳过未知 Band: start_index={start_index}, n_arrays={n_arrays}", "STREAM")
                            continue

                        # 推送帧
                        self.push_frame_to_session(session, streamsrc_frame)

                except Exception as e:
                    log(f"FSCAN 推送错误: {e}", "STREAM")
                    break

            # 清理
            session.push_running = False
            session._stop_event.clear()
            if session.debug_file:
                session.debug_file = None
            if session._band_collector:
                session._band_collector.clear()
                session._band_collector = None
            log(f"FSCAN 推送线程结束: taskid={session.taskid}", "STREAM")

        session.push_thread = threading.Thread(target=push_loop, daemon=True)
        session.push_thread.start()

    def push_frame_to_session(self, session: StreamSession, frame: bytes):
        """推送帧到指定会话的 streamsrc 客户端

        优化：锁与IO分离 - 锁只保护共享状态，sendall在锁外执行
        """
        # 调试：保存发送的帧到文件（同一线程写入，无需锁）
        import os
        if session.debug_file:
            with open(session.debug_file, 'ab') as f:
                f.write(frame)

        # 网络发送（sendall本身线程安全，锁外执行）
        # 这样其他线程调用close_all时不会被阻塞
        client = session.streamsrc_client
        if client:
            try:
                client.sendall(frame)
                session.update_data_time()
                # 调试日志：显示发送的帧信息
                if len(frame) == 1086:
                    import struct
                    indicator = struct.unpack('>H', frame[18:20])[0]
                    meta0 = struct.unpack('<h', frame[48:50])[0]
                    meta5 = struct.unpack('<h', frame[58:60])[0]
                    log(f"发送 FSCAN-529: indicator=0x{indicator:04x}, meta[0]={meta0}, meta[5]={meta5}", "STREAM")
                elif len(frame) == 896:
                    log(f"发送 FSCAN-434: {len(frame)} bytes", "STREAM")
            except Exception as e:
                log(f"推送帧失败: {e}", "STREAM")

    def _send_registration_ack(self, client_socket: socket.socket, reg_data: bytes = None):
        """发送 Registration ACK (65 bytes)

        真实设备在收到 registration 后回显相同的 frame
        """
        import struct
        import time

        if reg_data and len(reg_data) == 65:
            # 回显收到的 Registration frame，只更新时间戳
            frame = bytearray(reg_data)
            ts = int(time.time() * 10000000) + 116444736000000000
            struct.pack_into('<Q', frame, 10, ts)
            # 修正 indicator 为 Registration ACK (0x0029)
            struct.pack_into('>H', frame, 18, 0x0029)
        else:
            # 构造 65 字节的 Registration ACK 帧
            frame = bytearray(65)
            struct.pack_into('<I', frame, 0, 0xEEEEEEEE)
            struct.pack_into('>H', frame, 4, 0x0100)
            struct.pack_into('<I', frame, 6, 0)
            ts = int(time.time() * 10000000) + 116444736000000000
            struct.pack_into('<Q', frame, 10, ts)
            struct.pack_into('>H', frame, 18, 0x0029)
            struct.pack_into('<I', frame, 20, 0)
            struct.pack_into('<H', frame, 24, 0x0024)
            for i in range(36):
                frame[26 + i] = 0
            struct.pack_into('<H', frame, 62, 0)
            frame[64] = 0x38

        try:
            client_socket.sendall(bytes(frame))
            # 调试日志：显示 ACK 的 indicator
            import struct
            indicator = struct.unpack('>H', frame[18:20])[0]
            log(f"发送 Registration ACK: {len(frame)} bytes, indicator=0x{indicator:04x}", "STREAM")
            # 调试：保存 ACK 到文件
            import os
            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f'sent_ack_{int(time.time()*1000)}.bin')
            with open(debug_file, 'wb') as f:
                f.write(bytes(frame))
        except Exception as e:
            log(f"发送 Registration ACK 失败: {e}", "STREAM")

    def push_frame(self, frame: bytes):
        """推送帧到所有连接的客户端"""
        if not frame or len(frame) not in (1086, 896):
            log(f"推送帧无效: length={len(frame) if frame else 0}")
            return

        log(f"push_frame: {len(self.clients)} clients, frame_len={len(frame)}", "STREAM")

        disconnected = []
        with self.lock:
            for client in self.clients:
                try:
                    client.sendall(frame)
                    # 更新会话的数据接收时间
                    session = self.session_manager.get_session_by_socket(client)
                    if session:
                        session.update_data_time()
                except Exception as e:
                    log(f"推送失败: {e}")
                    disconnected.append(client)

            for client in disconnected:
                try:
                    client.close()
                except:
                    pass
                if client in self.clients:
                    self.clients.remove(client)
                # 成对关闭：断开 streamsrc 时也关闭对应的 RMCP
                session = self.session_manager.remove_session(client)
                if session:
                    self._close_session_with_stop(session)

        if disconnected:
            log(f"已移除 {len(disconnected)} 个断开的客户端")

    def _close_session_with_stop(self, session: StreamSession):
        """关闭会话并发送 B_StopMeas 请求"""
        taskid = session.taskid
        log(f"客户端断开，发送 B_StopMeas...", "SESSION")

        # 发送 B_StopMeas 到设备
        try:
            xml_content = build_stopmeas_xml()
            result = send_to_target(xml_content, timeout=3.0)
            if result:
                log(f"B_StopMeas 响应成功", "SESSION")
            else:
                log(f"B_StopMeas 无响应", "SESSION")
        except Exception as e:
            log(f"B_StopMeas 失败: {e}", "SESSION")

        # 关闭所有连接
        session.close_all()

    def stop(self):
        """停止服务器"""
        self.running = False
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        log("streamsrc 服务器已停止")


# ==================== SOAP 处理 ====================

def parse_soap_request(request: bytes) -> Dict[str, Any]:
    """解析 SOAP 请求 (支持完整 HTTP 请求或纯 SOAP XML)"""
    try:
        text = request.decode('utf-8', errors='replace')

        import re
        action_match = re.search(r'SOAPAction:\s*"?([^"\n]+)"?', text)
        operation = action_match.group(1).strip() if action_match else ''

        # 提取 SOAP XML (从 <soapenv: 开始)
        soap_start = text.find('<soapenv:Envelope')
        if soap_start == -1:
            soap_start = text.find('<soap:Envelope')
        if soap_start == -1:
            soap_start = text.find('<srrc:requestbody')
        if soap_start == -1:
            log(f"未找到 SOAP XML 开始标签")
            return {'operation': operation, 'params': {}}

        soap_xml = text[soap_start:]
        log(f"提取到 SOAP XML: {len(soap_xml)} 字符")

        try:
            from lxml import etree
            root = etree.fromstring(soap_xml.encode('utf-8'))
            params = {}
            NS = {'srrc': 'http://www.srrc.org.cn', 'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/'}
            # 尝试多个命名空间
            for ns_prefix, ns_uri in NS.items():
                equpara = root.find(f'.//{{{ns_uri}}}equpara')
                if equpara is not None:
                    break
            if equpara is not None:
                for item in equpara.findall(f'.//{{{ns_uri}}}item', namespaces=NS):
                    paraname = item.find(f'{{{ns_uri}}}paraname')
                    paravalue = item.find(f'{{{ns_uri}}}paravalue')
                    if paraname is not None and paravalue is not None:
                        params[paraname.text] = paravalue.text
            else:
                # 尝试直接从 B_FScanRequest / B_PScanRequest 等子元素提取参数
                for ns_prefix, ns_uri in NS.items():
                    # 查找 B_FScanRequest 或 B_PScanRequest
                    for req_name in ['B_FScanRequest', 'B_PScanRequest', 'B_FScanDFRequest']:
                        req_elem = root.find(f'.//{{{ns_uri}}}{req_name}')
                        if req_elem is not None:
                            break
                    if req_elem is not None:
                        break
                if req_elem is not None:
                    # 直接提取所有子元素作为参数
                    for child in req_elem:
                        tag = child.tag.split('}')[-1]  # 去掉命名空间前缀
                        params[tag] = child.text
            return {'operation': operation, 'params': params}
        except ImportError:
            return {'operation': operation, 'params': {}}
        except Exception as e:
            log(f"lxml 解析失败: {e}")
            return {'operation': operation, 'params': {}}

    except Exception as e:
        log(f"SOAP 解析失败: {e}")
        return {'operation': '', 'params': {}}


# Atom 标识符 (模拟真实设备的 Atom ID)
ATOM_ID = '00D8612F75B8'  # 第五段固定值

def generate_taskid(flags: int = 0x8002) -> str:
    """生成符合真实设备格式的 taskid

    格式: XXXXXXXX-XXXX-11F1-XXXX-00D8612F75B8

    Args:
        flags: 第四段值, 0x8002表示激活会话, 0x8000可能表示其他状态

    Returns:
        taskid 字符串 (36字符 UUID 格式)
    """
    import random

    # 第一段: 基于时间戳的会话ID
    import time
    ts = int(time.time() * 1000) & 0xFFFFFFFF
    part1 = f'{ts:08X}'

    # 第二段: 随机值 (模拟会话随机性)
    part2 = f'{random.randint(0, 0xFFFF):04X}'

    # 第三段: 固定值 (协议标识)
    part3 = '11F1'

    # 第四段: 状态标志
    part4 = f'{flags:04X}'

    # 第五段: Atom ID (固定)
    part5 = ATOM_ID

    return f'{part1}-{part2}-{part3}-{part4}-{part5}'


def build_soap_response(success: bool, taskid: str = None, error: str = None, mfid: str = '53090001140012', equid: str = '51cd8dfe-e543-40c9-bdc3-a292766fee7f', outputchannel: dict = None, priority: int = 9, executetime: int = 0, equpara: dict = None) -> bytes:
    """构建 SOAP 响应 (匹配真实设备格式)

    Args:
        outputchannel: dict with keys: host, port, stc, mode, datachannel
        priority: task priority (default 9)
        executetime: execute time (default 0)
        equpara: dict with keys: startfreq, stopfreq, step, gain, rfworkmode, scanmode
    """
    if success:
        # 真实设备 B_FScan 响应格式
        outputchannel_xml = ''
        if outputchannel:
            outputchannel_xml = f'''<srrc:outputchannel>
  <srrc:mode>{outputchannel.get('mode', 'source')}</srrc:mode>
  <srrc:datachannel>{outputchannel.get('datachannel', 'stream')}</srrc:datachannel>
  <srrc:host>{outputchannel.get('host', '127.0.0.1')}</srrc:host>
  <srrc:port>{outputchannel.get('port', 18013)}</srrc:port>
  <srrc:stc>{outputchannel.get('stc', 0)}</srrc:stc>
</srrc:outputchannel>'''

        # equpara echo
        equpara_xml = ''
        if equpara:
            equpara_xml = f'''<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid><srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>{equpara.get('startfreq', 0)}</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>{equpara.get('stopfreq', 0)}</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>{equpara.get('step', 0)}</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>{equpara.get('gain', 'AGC')}</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>{equpara.get('rfworkmode', 0)}</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>scanmode</srrc:paraname><srrc:paravalue>{equpara.get('scanmode', 0)}</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>'''

        body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Header><srrc:ProviderResponse><srrc:bizResCd>BIZ-000001</srrc:bizResCd><srrc:bizResText>&#x64CD;&#x7528;&#x6210;&#x529F;</srrc:bizResText></srrc:ProviderResponse></soapenv:Header>
<soapenv:Body><srrc:responsebody><srrc:result><srrc:appid>123456</srrc:appid><srrc:userid>RX_admin</srrc:userid><srrc:priority>{priority}</srrc:priority><srrc:executetime>{executetime}</srrc:executetime><srrc:mfid>{mfid}</srrc:mfid><srrc:equid>{equid}</srrc:equid>{equpara_xml}<srrc:taskid>{taskid or 'TASK-ID'}</srrc:taskid>{outputchannel_xml}</srrc:result></srrc:responsebody></soapenv:Body></soapenv:Envelope>'''
    else:
        body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:responsebody>
<srrc:error>{error or "Unknown error"}</srrc:error>
</srrc:responsebody></soapenv:Body></soapenv:Envelope>'''

    response = f'''HTTP/1.1 200 OK
Content-Type: text/xml; charset=utf-8
Content-Length: {len(body)}

{body}'''
    return response.encode('utf-8')


# ==================== SOAP -> RMCP 请求构建 ====================

def build_rmcp_frame(xml_content: str, funcid: int = 15) -> bytes:
    """
    构建 RMCP REQUEST 帧

    Args:
        xml_content: SOAP XML 字符串
        funcid: 功能 ID (默认 15 = B_FScan)

    Returns:
        完整的 RMCP 二进制帧
    """
    import struct
    import time

    # SOAP XML 编码为 GB2312
    xml_bytes = xml_content.encode('gb2312')

    # 计算 FILETIME 时间戳
    FILETIME_EPOCH = 116444736000000000  # 100纳秒间隔
    filetime = int(time.time() * 10000000) + FILETIME_EPOCH

    # 计算总长度 = 帧头(18) + XML 长度 + 1 (null)
    xml_length = len(xml_bytes) + 1  # XML + null terminator
    total_length = 18 + xml_length  # header(18) + payload
    # 注意: dwLength 应该包含整个帧 (header + payload)

    # 构建帧头 (18字节)
    header = struct.pack(
        '<IQ',        # dwLength(4) + tmStamp(8)
        total_length,
        filetime
    )
    # nVersion 单独用 big-endian 存储
    header += struct.pack('>H', 7)  # nVersion = 7
    # nMsgType + nFlags (nCheckSum 占位 0，后续替换)
    header += struct.pack('BB', 90, 1)  # nMsgType, nFlags

    # 计算校验和 (协议文档算法) - 在nCheckSum为0时计算
    checksum_frame = header + b'\x00\x00' + xml_bytes + b'\x00'
    checksum = _calculate_rmcp_checksum(checksum_frame)

    # 组合帧: 帧头 + 校验和 + XML + null
    frame = header + struct.pack('<H', checksum) + xml_bytes + b'\x00'

    return frame


def _calculate_rmcp_checksum(frame: bytes) -> int:
    """
    RMCP 帧头校验和算法 (来自协议文档):
    1. length + timestamp (64位)
    2. 第一次折半移位: 高32位 + 低32位
    3. 第二次折半移位: 高16位 + 低16位 (循环直到 <= 0xFFFF)
    4. 取反码 (~result)
    """
    length = struct.unpack('<I', frame[0:4])[0]
    timestamp = struct.unpack('<Q', frame[4:12])[0]

    total = timestamp + length

    # 第一次折半移位
    high = (total >> 32) & 0xFFFFFFFF
    low = total & 0xFFFFFFFF
    result1 = high + low

    # 第二次折半移位 (循环处理溢出)
    result2 = (result1 >> 16) + (result1 & 0xFFFF)
    while result2 > 0xFFFF:
        result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

    # 取反码
    return (~result2) & 0xFFFF


def build_stopmeas_xml() -> str:
    """构建 B_StopMeas 请求 XML"""
    soap_xml = '''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="17">
        <group index="0">
        </group>
    </parameter>
    <other_param />
</action>'''
    return soap_xml


def build_query_device_xml() -> str:
    """构建 B_QueryDeviceInfo 请求 XML"""
    soap_xml = '''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="">
        <group index="0">
        </group>
    </parameter>
    <other_param />
</action>'''
    return soap_xml


def send_to_target(xml_content: str, timeout: float = 5.0) -> Optional[bytes]:
    """
    发送 XML 到目标设备并接收响应

    Args:
        xml_content: SOAP XML 字符串
        timeout: 超时时间(秒)

    Returns:
        响应数据或 None
    """
    try:
        rmcp_frame = build_rmcp_frame(xml_content)
        log(f"RMCP REQUEST 帧: {len(rmcp_frame)} bytes")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((TARGET_HOST, TARGET_PORT))
        log(f"已连接到目标设备 {TARGET_HOST}:{TARGET_PORT}")

        sock.sendall(rmcp_frame)
        log("已发送 RMCP REQUEST")

        # 接收响应
        all_data = b''
        while True:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                all_data += chunk
                if len(all_data) > 1000:
                    break
            except socket.timeout:
                break

        sock.close()

        if all_data:
            log(f"收到 RMCP 响应: {len(all_data)} bytes")
            return all_data

        return None

    except Exception as e:
        log(f"发送 RMCP 请求失败: {e}")
        return None


# ==================== RMCP 客户端 ====================


class TargetDeviceClient:
    """目标设备客户端 - 连接到目标设备"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self) -> bool:
        """连接到目标设备"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10.0)
            self.sock.connect((self.host, self.port))
            local = self.sock.getsockname()
            log(f"已连接到目标设备 {self.host}:{self.port} (本地: {local[0]}:{local[1]})", "RMCP")
            return True
        except Exception as e:
            log(f"连接目标设备失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def is_connected(self) -> bool:
        """检查连接是否有效"""
        if self.sock is None:
            return False
        try:
            # 非阻塞检查 socket 状态
            self.sock.setblocking(False)
            data = self.sock.recv(1, socket.MSG_PEEK)
            self.sock.setblocking(True)
            return True  # 能读到数据说明还连着
        except BlockingIOError:
            self.sock.setblocking(True)
            return True  # 没数据但也没错误，说明还连着
        except Exception:
            self.sock.setblocking(True)
            return False

    def send_and_receive(self, data: bytes) -> Optional[bytes]:
        """发送数据并接收响应"""
        if not self.sock:
            return None

        try:
            self.sock.sendall(data)
            header = self.sock.recv(18)
            if not header or len(header) < 18:
                return None

            dw_length = struct.unpack('<I', header[0:4])[0]
            log(f"RMCPTP 帧头: length={dw_length}")

            remaining = b''
            if dw_length > 0:
                while len(remaining) < dw_length:
                    chunk = self.sock.recv(dw_length - len(remaining))
                    if not chunk:
                        break
                    remaining += chunk

            return header + remaining

        except socket.timeout:
            log("接收响应超时")
            return None
        except Exception as e:
            log(f"接收响应失败: {e}")
            return None


# ==================== 主服务 ====================

class EmulatedAtomService:
    """Emulated Atom 服务"""

    def __init__(self):
        self.session_manager = SessionManager()  # 会话管理器
        self.streamsrc_server = StreamSrcServer(STREAMSRC_PORT, self.session_manager, self)
        self.running = False
        self.threads = []
        self.pending_sessions: Dict[str, StreamSession] = {}  # 待关联的会话（等待客户端连接）

        # RMCP 帧日志记录器
        rmcp_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'rmcp_capture')
        os.makedirs(rmcp_log_dir, exist_ok=True)
        self.rmcp_logger = RMCPFrameLogger(rmcp_log_dir, TARGET_PORT)

    def start(self):
        """启动服务"""
        log("=" * 60)
        log("Emulated Atom Service 启动 (简化版)")
        log(f"  SOAP 端口: {SOAP_PORT}")
        log(f"  streamsrc 端口: {STREAMSRC_PORT}")
        log(f"  目标设备: {TARGET_HOST}:{TARGET_PORT}")
        log(f"  RMCP 日志: {self.rmcp_logger.log_file}")
        log(f"  模拟数据: {USE_MOCK_DATA}")
        log("=" * 60)

        # 启动 streamsrc 服务器
        self.streamsrc_server.start()

        # 启动 SOAP 服务器
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', SOAP_PORT))
        server.listen(5)
        self.running = True

        log(f"SOAP 服务器已启动: 0.0.0.0:{SOAP_PORT}")

        try:
            while self.running:
                server.settimeout(1.0)
                try:
                    client, addr = server.accept()
                    log(f"SOAP 客户端连接: {addr}")
                    # 每个连接使用独立线程处理
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client, addr)
                    )
                    thread.daemon = True
                    thread.start()
                except socket.timeout:
                    # 清理超时的待关联会话（超过30秒未关联则丢弃）
                    self._cleanup_stale_sessions()
                    continue
        except KeyboardInterrupt:
            log("收到中断信号")
        finally:
            self.stop()

    def _handle_client(self, client, addr):
        """处理客户端请求"""
        try:
            client.settimeout(10.0)
            data = b''
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'</soapenv:Envelope>' in data:
                    break
                if len(data) > 10000:  # Safety limit
                    break

            log(f"收到数据: {len(data)} bytes")
            log(f"数据前100字节: {data[:100]}", "SOAP")

            if not data:
                client.close()
                return

            # 解析 SOAP 请求
            request = parse_soap_request(data)
            operation = request.get('operation', '')
            params = request.get('params', {})

            log(f"收到 SOAP 请求: {operation}, 参数: {params}")

            # 处理请求
            if operation == 'B_StopMeas':
                self._handle_stopmeas(client)
            elif operation == 'B_QueryDeviceInfo':
                self._handle_query_device(client, params)
            elif operation in ('B_FScan', 'B_PScan', 'B_FScanDF'):
                self._handle_fscan(client, params)
            elif params and any(k in params for k in ('startfreq', 'stopfreq', 'step')):
                # operation 为空但包含 FSCAN 参数时，也当作 FSCAN 处理
                log(f"operation 为空但检测到 FSCAN 参数，当作 B_FScan 处理")
                self._handle_fscan(client, params)
            else:
                response = build_soap_response(True, taskid='EMULATED-ATOM-001')
                client.sendall(response)
                client.close()

        except Exception as e:
            log(f"处理请求失败: {e}")
            try:
                client.close()
            except:
                pass

    def _handle_fscan(self, client, params):
        """处理 FSCAN 请求"""
        log("_handle_fscan 开始")

        # 解析频率参数 (支持 '137MHz', '25kHz', '137000000' 等格式)
        def parse_freq(val):
            if isinstance(val, int):
                return val
            val = str(val).strip()
            if val.endswith('MHz'):
                return int(float(val[:-3]) * 1000000)
            elif val.endswith('kHz'):
                return int(float(val[:-3]) * 1000)
            elif val.endswith('Hz'):
                return int(val[:-2])
            else:
                return int(val)

        start_freq = parse_freq(params.get('startfreq', params.get('StartFreq', 137000000)))
        end_freq = parse_freq(params.get('stopfreq', params.get('StopFreq', 173000000)))
        step = parse_freq(params.get('step', 25000))

        log(f"FSCAN: {start_freq} - {end_freq}, step={step}")

        # 发送 SOAP 响应
        taskid = generate_taskid()
        import time
        stc = int(time.time())  # session time counter
        outputchannel = {
            'host': '127.0.0.1',
            'port': 18013,
            'stc': stc,
            'mode': 'source',
            'datachannel': 'stream'
        }
        response = build_soap_response(True, taskid=taskid, outputchannel=outputchannel,
                                      equpara={'startfreq': start_freq, 'stopfreq': end_freq, 'step': step})
        client.sendall(response)
        client.close()

        # 创建待关联的会话（等待 streamsrc 客户端连接）
        # 实际关联在 streamsrc 客户端连接时进行
        fscan_params = {
            'start_freq': start_freq,
            'end_freq': end_freq,
            'step': step,
            'taskid': taskid,
            'stc': stc  # 保存 STC 以便在数据帧中使用
        }
        pending_session = StreamSession(streamsrc_client=None, taskid=taskid, fscan_params=fscan_params)
        with self.session_manager.lock:
            self.pending_sessions[taskid] = pending_session
        log(f"创建待关联会话: taskid={taskid}, pending_sessions={list(self.pending_sessions.keys())}", "SESSION")

        # 不在这里获取数据，等待 streamsrc 客户端连接后再推送
        # 这样可以确保客户端已连接，能收到数据

    def _cleanup_stale_sessions(self, timeout: float = 30.0):
        """清理超时的待关联会话"""
        now = time.time()
        stale_taskids = []
        with self.session_manager.lock:
            for taskid, session in self.pending_sessions.items():
                if now - session.last_data_time > timeout:
                    stale_taskids.append(taskid)
            for taskid in stale_taskids:
                session = self.pending_sessions.pop(taskid, None)
                if session:
                    log(f"清理超时会话: taskid={taskid}", "SESSION")

    def _get_fscan_spectrum(self, start_freq: int, end_freq: int, step: int, taskid: str = None) -> Optional[list]:
        """获取 FSCAN 频谱数据（合并三频段）

        Returns:
            合并后的频谱数据 (1441 点) 或 None (模拟模式)
        """
        if USE_MOCK_DATA:
            # 使用模拟数据
            log("使用模拟频谱数据")
            # 生成 512 点模拟数据 (类似真实信号)
            spectrum = []
            base_level = -70  # 基础电平
            for i in range(512):
                # 添加一些随机变化和信号峰值
                noise = random.gauss(0, 5)
                # 在某些频率创建信号峰值
                if 100 < i < 120 or 200 < i < 210 or 350 < i < 370:
                    signal = random.uniform(10, 20)
                else:
                    signal = 0
                value = base_level + noise + signal
                spectrum.append(int(value))
            return spectrum

        # 尝试从真实设备获取数据
        log(f"尝试连接 {TARGET_HOST}:{TARGET_PORT} ...")
        try:
            # 直接连接真实设备获取 FSCAN 数据
            spectrum = self._get_fscan_from_device(start_freq, end_freq, step, taskid)
            if spectrum:
                return spectrum

            log(f"未能从 {TARGET_HOST}:{TARGET_PORT} 获取数据，使用模拟数据")
            return self._get_mock_spectrum()

        except Exception as e:
            log(f"获取真实数据失败: {e}，使用模拟数据")
            return self._get_mock_spectrum()

    def _send_fscan_request(self, start_freq: int, end_freq: int, step: int, taskid: str = None) -> bool:
        """发送 FSCAN RMCP 请求到设备（仅发送，不接收数据）

        用于在 push_loop 开始时建立连接并发送请求

        Returns:
            True 如果成功，False 如果失败
        """
        if USE_MOCK_DATA:
            return False

        session = None
        if taskid:
            with self.session_manager.lock:
                session = self.session_manager.taskid_to_session.get(taskid)

        if session and session._closing:
            log(f"Session 正在关闭，跳过发送请求", "RMCP")
            return False

        try:
            # 导入 SOAP 相关模块
            from data.fscan_real_request import build_fscan_xml, build_rmcp_request_frame
            soap_xml = build_fscan_xml(start_freq, end_freq, step)
            cmd = build_rmcp_request_frame(soap_xml)
            log(f"RMCP REQUEST 帧: {len(cmd)} bytes")

            # 检查 session 是否有可用连接
            target_client = None
            if session and session.target_client and session.target_client.is_connected():
                target_client = session.target_client
                log(f"复用已有连接: {TARGET_HOST}:{TARGET_PORT}", "RMCP")
            else:
                # 创建新连接
                target_client = TargetDeviceClient(TARGET_HOST, TARGET_PORT)
                if not target_client.connect():
                    log(f"连接 {TARGET_HOST}:{TARGET_PORT} 失败")
                    return False
                log(f"创建新连接: {TARGET_HOST}:{TARGET_PORT}", "RMCP")

                # 关联到 session
                if session:
                    session.attach_target(target_client)

            target_client.sock.sendall(cmd)
            log("已发送 RMCP REQUEST")
            return True

        except Exception as e:
            log(f"发送 FSCAN 请求失败: {e}")
            return False

    def _read_fscan_bands(self, start_freq: int, end_freq: int, step: int, taskid: str = None, band_collector: 'BandCollector' = None):
        """从设备读取 FSCAN 数据并放入收集器

        Args:
            band_collector: BandCollector 实例，用于收集频段数据
        """
        if USE_MOCK_DATA:
            return

        if band_collector is None:
            log(f"_read_fscan_bands: band_collector 为 None", "RMCP")
            return

        session = None
        if taskid:
            with self.session_manager.lock:
                session = self.session_manager.taskid_to_session.get(taskid)

        # 检查 session 是否正在关闭
        if session and session._closing:
            log(f"Session 正在关闭，跳过读取 FSCAN", "RMCP")
            return

        try:
            target_client = None
            if session and session.target_client and session.target_client.is_connected():
                target_client = session.target_client
            else:
                log(f"无可用设备连接", "RMCP")
                return

            # 读取数据（非阻塞，短超时）
            recv_buffer = b''
            last_data_time = time.time()
            target_client.sock.settimeout(0.1)  # 100ms 超时，快速返回

            try:
                while True:
                    chunk = target_client.sock.recv(8192)
                    if not chunk:
                        break
                    recv_buffer += chunk
                    last_data_time = time.time()
            except socket.timeout:
                pass
            except Exception as e:
                log(f"recv 错误: {e}", "RMCP")

            if not recv_buffer:
                return

            # 解析数据并放入收集器
            while len(recv_buffer) >= 18:
                dw_length = struct.unpack('<I', recv_buffer[0:4])[0]
                n_msg_type = recv_buffer[14]

                if dw_length < 18 or dw_length > 10000:
                    recv_buffer = recv_buffer[1:]
                    continue

                total_frame_len = 18 + dw_length
                if len(recv_buffer) < total_frame_len:
                    break

                frame_data = recv_buffer[:total_frame_len]
                recv_buffer = recv_buffer[total_frame_len:]

                if n_msg_type in (0, 29):
                    payload = frame_data[18:]
                    result = self._parse_single_fscan_frame(payload)
                    if result is None or result[0] is None:
                        continue

                    spectrum, counters = result
                    if len(spectrum) < 100:
                        continue

                    band_info = {
                        'levels': spectrum,
                        'counters': counters,
                        'n_arrays': len(spectrum)
                    }
                    band_collector.put(band_info)
                    self.rmcp_logger.log_frame('S->C', frame_data, (TARGET_HOST, TARGET_PORT))

        except Exception as e:
            log(f"_read_fscan_bands 错误: {e}")
            import traceback
            traceback.print_exc()

    def _get_fscan_from_capture(self) -> Optional[list]:
        """[调试用] 从 capture 日志读取 FSCAN 数据 (三频段合并)

        警告: 此方法仅用于调试目的，正常业务流程不应使用此方法。
        正常流程应直接连接真实设备获取数据。

        设备返回三个 FSCAN 帧对应不同频段:
        - Band 1: 512点, counters=(512, 0, 0, 0), 起始序号 0, 137.0-149.775MHz
        - Band 2: 512点, counters=(512, 0, 512, 0), 起始序号 512, 149.8-162.575MHz
        - Band 3: 417点, counters=(417, 0, 1024, 0), 起始序号 1024, 162.6-173.0MHz

        Returns:
            合并后的频谱数据 (1441 点) 或 None
        """
        try:
            # 路径: experimental/emulated_atom.py -> 项目根目录/rmcp_proxy/capture/
            # 注: capture 是 rmcp_proxy 的抓包目录，用于调试读取真实设备数据
            project_root = Path(os.path.dirname(os.path.abspath(__file__))).parent
            capture_dir = project_root / 'rmcp_proxy' / 'capture'
            capture_files = sorted(capture_dir.glob("capture_*.json"), key=lambda p: p.stat().st_mtime)

            if not capture_files:
                log("没有找到 capture 文件")
                return None

            latest = capture_files[-1]
            log(f"读取 capture: {latest.name}")

            with open(latest, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 收集三个频段的 counters 信息用于调试
            band_counters = []

            # 找 S->C 的 FSCAN 数据 - 收集所有频段
            all_bands = []
            for entry in data:
                if entry.get('direction') == 'S->C' and entry.get('data_type') == 'SIMPLE_FSCAN':
                    fscan = entry.get('fscan', {})
                    levels = fscan.get('levels', [])
                    counters = fscan.get('counters', [0, 0, 0, 0])

                    if levels:
                        all_bands.append({
                            'levels': [int(l) for l in levels],
                            'counters': counters,
                            'n_arrays': len(levels)
                        })
                        band_counters.append(counters)

            if not all_bands:
                log("capture 中没有 FSCAN 数据")
                return None

            # 按 counters[2] (起始序号) 排序
            all_bands.sort(key=lambda x: x['counters'][2] if x['counters'] else 0)

            # 合并三个频段
            combined_spectrum = []
            for band in all_bands:
                combined_spectrum.extend(band['levels'])

            log(f"从 capture 获取 FSCAN: {len(all_bands)} 频段, 共 {len(combined_spectrum)} 点")
            log(f"Band counters: {band_counters}", "PARSE")

            return combined_spectrum

        except Exception as e:
            log(f"从 capture 获取数据失败: {e}")
            return None

    def _get_fscan_from_device(self, start_freq: int, end_freq: int, step: int, taskid: str = None) -> Optional[list]:
        """直接从真实设备获取 FSCAN 数据（流式推送版本）

        优化：优先复用 session 中已存在的目标设备连接，避免频繁创建/关闭连接
        """
        log(f"_get_fscan_from_device 开始: taskid={taskid}", "RMCP")
        session = None
        if taskid:
            with self.session_manager.lock:
                session = self.session_manager.taskid_to_session.get(taskid)

        try:
            # 使用真实设备接受的格式构建 SOAP XML
            from data.fscan_real_request import build_fscan_xml, build_rmcp_request_frame
            soap_xml = build_fscan_xml(start_freq, end_freq, step)
            cmd = build_rmcp_request_frame(soap_xml)
            log(f"RMCP REQUEST 帧: {len(cmd)} bytes")

            # 优先复用 session 中的连接
            target_client = None
            reuse_connection = False

            if session and session.target_client:
                # 检查现有连接是否有效
                if session.target_client.is_connected():
                    target_client = session.target_client
                    reuse_connection = True
                    log(f"复用已有连接: {TARGET_HOST}:{TARGET_PORT} (本地: {target_client.sock.getsockname()[1]})", "RMCP")
                else:
                    # 连接已断开，关闭并设为None
                    session.target_client.disconnect()
                    session.target_client = None

            # 如果没有可用连接，创建新连接
            if target_client is None:
                target_client = TargetDeviceClient(TARGET_HOST, TARGET_PORT)
                if not target_client.connect():
                    log(f"连接 {TARGET_HOST}:{TARGET_PORT} 失败")
                    return None

            # 关联 RMCP 客户端到会话（成对管理）
            if session and not reuse_connection:
                session.attach_target(target_client)
                log(f"已关联设备客户端: target_client={session.target_client is not None}", "SESSION")

            target_client.sock.sendall(cmd)
            log("已发送 RMCP REQUEST")

            # 收集设备返回的所有 FSCAN 帧
            recv_buffer = b''
            all_bands = []  # 每元素: (spectrum, counters)
            last_data_time = time.time()
            start_time = time.time()

            target_client.sock.settimeout(1.0)  # 1秒超时检测

            while True:
                # 总超时 90 秒
                if time.time() - start_time > 90:
                    log("等待设备响应超时 (90秒)")
                    break

                try:
                    chunk = target_client.sock.recv(8192)
                    if chunk:
                        recv_buffer += chunk
                        last_data_time = time.time()

                        # 尝试从 buffer 中解析 FSCAN 帧
                        while len(recv_buffer) >= 18:
                            # RMCP 帧头: dwLength(I) + tmStamp(Q) + nVersion(H) + nMsgType(B) + nFlags(B) + nCheckSum(H)
                            # offset 0-3: dwLength (little-endian)
                            # offset 14: nMsgType
                            if len(recv_buffer) < 18:
                                break

                            dw_length = struct.unpack('<I', recv_buffer[0:4])[0]
                            n_msg_type = recv_buffer[14]

                            # 检查帧是否完整
                            if dw_length < 18 or dw_length > 10000:
                                # 无效帧头，跳过第一个字节
                                recv_buffer = recv_buffer[1:]
                                continue

                            total_frame_len = 18 + dw_length
                            if len(recv_buffer) < total_frame_len:
                                # 帧不完整，等待更多数据
                                break

                            # 提取完整帧并解析
                            frame_data = recv_buffer[:total_frame_len]
                            recv_buffer = recv_buffer[total_frame_len:]

                            # 只处理 MSG_TYPE_DATA (nMsgType=0 或 29)
                            if n_msg_type in (0, 29):
                                # 解析 FSCAN payload (跳过 RMCP 帧头 18 字节)
                                payload = frame_data[18:]

                                result = self._parse_single_fscan_frame(payload)
                                if result is None or result[0] is None:
                                    continue

                                spectrum, counters = result
                                if len(spectrum) < 100:
                                    continue

                                all_bands.append({
                                    'levels': spectrum,
                                    'counters': counters,
                                    'n_arrays': len(spectrum)
                                })

                                # 使用 RMCPFrameLogger 记录帧
                                self.rmcp_logger.log_frame('S->C', frame_data, (TARGET_HOST, TARGET_PORT))

                except socket.timeout:
                    # 检查是否应该结束
                    if time.time() - last_data_time > 3:
                        if len(all_bands) > 0:
                            log(f"设备数据接收完毕: 共 {len(all_bands)} 帧")
                        else:
                            log("设备数据接收完毕: 未解析到有效帧")
                        break

            # 复用连接时不断开，只在新创建连接时在session结束时断开
            if not reuse_connection:
                target_client.disconnect()

            if len(all_bands) == 0:
                return None

            # 按 counters[2] (起始序号) 排序
            all_bands.sort(key=lambda x: x['counters'][2] if x['counters'] else 0)

            # 合并三个频段
            combined_spectrum = []
            for band in all_bands:
                combined_spectrum.extend(band['levels'])

            log(f"从设备获取 FSCAN: {len(all_bands)} 频段, 共 {len(combined_spectrum)} 点")
            log(f"Band counters: {[b['counters'] for b in all_bands]}", "PARSE")

            return combined_spectrum

        except Exception as e:
            log(f"直接获取失败: {e}")
            # 新建连接失败时清理
            if not reuse_connection and target_client:
                target_client.disconnect()
            import traceback
            traceback.print_exc()
            return None

    def _parse_single_fscan_frame(self, payload: bytes) -> tuple:
        """解析单个 RMCP FSCAN 帧的 payload

        RMCP FSCAN payload 格式 (在 RMCPTP 帧头18字节之后):
        - byte 0: nBdType (1 byte): 数据类型 (15=FSCAN)
        - bytes 1-2: reserved
        - bytes 3-10: counters (4 x int16 little-endian) - counters[0] = nArrays
        - bytes 11+: levels (int16 little-endian, 每帧通常是512点)

        Returns:
            (spectrum, counters) 元组
            - spectrum: dBm值列表 (已除以10)
            - counters: (n_arrays, ?, start_index, ?) 元组
              start_index 用于判断频段: 0=band1, 512=band2, 1024=band3
        """
        if not payload or len(payload) < 25:
            return None

        try:
            offset = 0

            n_bd_type = payload[offset]  # 0x0F = 15 = FSCAN
            offset += 1

            # 检查是否是 FSCAN 类型
            if n_bd_type != 15:
                log(f"非 FSCAN 类型: n_bd_type={n_bd_type}", "PARSE")
                return None

            # counters (4 x int16 little-endian), counters[0] = nArrays
            counters = struct.unpack('<4h', payload[3:11])
            n_arrays = counters[0]

            if n_arrays == 0 or n_arrays > 2000:
                log(f"无效 n_arrays: {n_arrays}", "PARSE")
                return None

            # Spectrum starts at byte 11, little-endian int16
            spectrum_offset = 11
            spectrum = []
            for i in range(min(n_arrays, 512)):
                if spectrum_offset + 2 > len(payload):
                    break
                level_raw = struct.unpack('<h', payload[spectrum_offset:spectrum_offset+2])[0]
                level_dbm = level_raw / 10.0  # 转换 dBm
                spectrum.append(level_dbm)
                spectrum_offset += 2

            if len(spectrum) > 0:
                log(f"FSCAN: n_bd_type={n_bd_type}, n_arrays={n_arrays}, counters={counters}, spectrum_len={len(spectrum)}", "PARSE")

            # 返回 (spectrum, counters) 元组
            return spectrum, counters

        except Exception as e:
            log(f"解析 FSCAN 帧失败: {e}", "PARSE")
            return None, None

    def _parse_rmcp_fscan_response(self, data: bytes) -> Optional[list]:
        """解析 RMCP FSCAN 响应 (SIMPLE_FSCAN 格式)"""
        if not data or len(data) < 50:
            return None

        try:
            # 解析 RMCPTP 帧头
            if len(data) < 18:
                log(f"数据长度 {len(data)} < 18")
                return None

            dw_length = struct.unpack('<I', data[0:4])[0]
            n_msg_type = data[14]
            log(f"RMCPTP: length={dw_length}, msg_type={n_msg_type}")

            # 业务数据起始位置
            payload = data[18:]
            offset = 0

            # 解析 SIMPLE_FSCAN 格式
            # nBdType (1 byte) + nArrays (4 bytes) + counters (16 bytes) + levels
            if len(payload) < 21:
                log(f"Payload 太短: {len(payload)}")
                return None

            n_bd_type = payload[offset]  # 0x0F = 15 = FSCAN
            offset += 1

            n_arrays = struct.unpack('!I', payload[offset:offset+4])[0]
            offset += 4

            # counters (16 bytes = 4 * uint32)
            counters = []
            for i in range(4):
                counters.append(struct.unpack('!I', payload[offset:offset+4])[0])
                offset += 4

            log(f"FSCAN: n_bd_type={n_bd_type}, n_arrays={n_arrays}, counters={counters}")

            # 解析 levels (每个 level 是 2 bytes int16)
            spectrum = []
            for i in range(min(n_arrays, 512)):
                if offset + 2 > len(payload):
                    break
                level = struct.unpack('!h', payload[offset:offset+2])[0]
                spectrum.append(level)
                offset += 2

            log(f"解析到 {len(spectrum)} 点频谱数据")
            return spectrum

        except Exception as e:
            log(f"解析 RMCP FSCAN 响应失败: {e}")
            return None

    def _save_rmcp_raw_log(self, data: bytes):
        """保存收到的目标设备原始数据到日志文件"""
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'rmcp_callback')
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'rmcp_raw_{timestamp}.log')
            hex_file = os.path.join(log_dir, f'rmcp_hex_{timestamp}.log')

            # 写入原始数据日志
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== RMCP Raw Data Log ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
                f.write(f"Size: {len(data)} bytes\n")
                f.write(f"Hex: {data.hex()}\n")

                # 解析并显示关键信息
                if len(data) >= 18:
                    dw_length = struct.unpack('<I', data[0:4])[0]
                    n_version = struct.unpack('>H', data[12:14])[0]
                    n_msg_type = data[14]
                    f.write(f"\nRMCPTP Header:\n")
                    f.write(f"  dwLength: {dw_length}\n")
                    f.write(f"  nVersion: {n_version}\n")
                    f.write(f"  nMsgType: {n_msg_type}\n")

            # 写入 hex 格式日志
            with open(hex_file, 'w', encoding='utf-8') as f:
                f.write(f"=== RMCP Hex Log ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
                f.write(f"Size: {len(data)} bytes\n\n")
                # 每行 16 bytes
                for i in range(0, len(data), 16):
                    chunk = data[i:i+16]
                    hex_str = ' '.join(f'{b:02x}' for b in chunk)
                    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                    f.write(f"{i:08x}  {hex_str:<48}  {ascii_str}\n")

        except Exception as e:
            log(f"保存 rmcp 原始数据失败: {e}")

    def _handle_stopmeas(self, client):
        """处理 B_StopMeas 请求 - 停止当前测量"""
        log("_handle_stopmeas 开始")

        # 关闭所有活跃会话（停止推送线程、断开设备连接）
        with self.session_manager.lock:
            for session in list(self.session_manager.sessions.values()):
                session.close_all()
            self.session_manager.sessions.clear()
            self.session_manager.taskid_to_session.clear()

        # 同步清理 streamsrc_server.clients
        with self.streamsrc_server.lock:
            for c in list(self.streamsrc_server.clients):
                try:
                    c.close()
                except:
                    pass
            self.streamsrc_server.clients.clear()
        log(f"清理 clients 完成", "STREAM")

        # 关闭所有待关联会话
        for taskid in list(self.pending_sessions.keys()):
            session = self.pending_sessions.pop(taskid, None)
            if session:
                session.close_all()

        # 发送 SOAP 响应
        taskid = generate_taskid()
        response = build_soap_response(True, taskid=taskid)
        try:
            client.sendall(response)
        except:
            pass
        try:
            client.close()
        except:
            pass

        # 转发到目标设备
        log("尝试转发 B_StopMeas 到目标设备...")
        try:
            xml_content = build_stopmeas_xml()
            result = send_to_target(xml_content, timeout=3.0)
            if result:
                log("B_StopMeas 设备响应成功")
            else:
                log("B_StopMeas 设备无响应(使用模拟)")
        except Exception as e:
            log(f"B_StopMeas 转发失败: {e}")

    def _handle_query_device(self, client, params):
        """处理 B_QueryDeviceInfo 请求 - 查询设备信息"""
        log("_handle_query_device 开始")

        # 从请求中提取设备信息
        mfid = params.get('mfid', '53090001140012')
        equid = params.get('equid', '51cd8dfe-e543-40c9-bdc3-a292766fee7f')

        # 生成 taskid
        taskid = generate_taskid()

        # 从预设文档读取完整格式（包含 featurelist 等）
        devinfo_file = os.path.join(DEVINFO_DIR, f'{mfid}_{equid}.xml')
        if os.path.exists(devinfo_file):
            try:
                with open(devinfo_file, 'rb') as f:
                    content = f.read()
                text = content.decode('gb2312', errors='replace')
                import re
                # 提取 <srrc:responsebody>...</srrc:responsebody>
                match = re.search(r'(<srrc:responsebody>.*?</srrc:responsebody>)', text, re.DOTALL)
                if match:
                    response_body_xml = match.group(1)
                else:
                    response_body_xml = '<srrc:error>Invalid format</srrc:error>'
                # 注入 appid 和 userid（如果不存在）
                if '<srrc:appid>' not in response_body_xml:
                    response_body_xml = response_body_xml.replace(
                        '<srrc:mfid>',
                        '<srrc:appid>123456</srrc:appid><srrc:userid>RX_admin</srrc:userid><srrc:mfid>'
                    )
                # 注入 taskid
                if '<srrc:taskid>' in response_body_xml:
                    response_body_xml = re.sub(
                        r'<srrc:taskid>[^<]*</srrc:taskid>',
                        f'<srrc:taskid>{taskid}</srrc:taskid>',
                        response_body_xml
                    )
                else:
                    response_body_xml = response_body_xml.replace(
                        '</srrc:result>',
                        f'<srrc:taskid>{taskid}</srrc:taskid></srrc:result>'
                    )
                log(f"从预设文档读取设备信息: {devinfo_file}")
            except Exception as e:
                log(f"读取预设文档失败: {e}")
                response_body_xml = '<srrc:error>Failed to load device info</srrc:error>'
        else:
            log(f"预设文档不存在: {devinfo_file}")
            response_body_xml = '<srrc:error>Device info not found</srrc:error>'

        # 构建完整的 SOAP 响应信封 (包含真实设备的所有命名空间)
        response_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Header><srrc:ProviderResponse><srrc:bizResCd>BIZ-000001</srrc:bizResCd><srrc:bizResText>&#x64CD;&#x7528;&#x6210;&#x529F;</srrc:bizResText></srrc:ProviderResponse></soapenv:Header>
<soapenv:Body>{response_body_xml}</soapenv:Body>
</soapenv:Envelope>'''

        response = f'''HTTP/1.1 200 OK
Server: gSOAP/2.8
Content-Type: text/xml; charset=utf-8
Content-Length: {len(response_body)}
Connection: close

{response_body}'''

        try:
            client.sendall(response.encode('utf-8'))
            log(f"B_QueryDeviceInfo 响应已发送, taskid={taskid}")
        except Exception as e:
            log(f"发送 B_QueryDeviceInfo 响应失败: {e}")
        finally:
            client.close()

    def _get_mock_spectrum(self) -> list:
        """获取模拟频谱数据"""
        spectrum = []
        base_level = -70
        for i in range(512):
            noise = random.gauss(0, 5)
            if 100 < i < 120 or 200 < i < 210 or 350 < i < 370:
                signal = random.uniform(10, 20)
            else:
                signal = 0
            value = base_level + noise + signal
            spectrum.append(int(value))
        return spectrum

    def stop(self):
        """停止服务"""
        log("停止服务...")
        self.running = False
        self.streamsrc_server.stop()


def main():
    """主函数"""
    service = EmulatedAtomService()
    service.start()


if __name__ == '__main__':
    main()
