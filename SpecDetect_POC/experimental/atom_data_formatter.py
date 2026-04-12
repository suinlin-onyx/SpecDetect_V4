# -*- coding: utf-8 -*-
"""
Atom 数据整理器

功能:
模拟 Atom 对设备原始数据的整理，将简化格式转换为标准 FSCAN 格式。

设备原始数据 (简化格式):
- LEADER=271 (0x10F)
- 无频段信息
- 电平数据需要 ÷256 转换

用户期望的标准格式:
- LEADER=0xEEEE1DE6
- 完整频段信息 (起始频率、结束频率、步长、信道总数等)
- 电平为直接 dBm 值
"""

import struct
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================
# 常量
# ============================================

# 标准 FSCAN 格式 LEADER
# 0xEEEE1DE6 as signed 32-bit int = -286331154
FSCAN_LEADER_STANDARD = -286331154

# 简化格式 LEADER
FSCAN_LEADER_SIMPLE = 0x10F  # 271


class AtomDataFormatter:
    """模拟 Atom 对设备原始数据的整理"""

    def __init__(self, request_params: Dict[str, Any]):
        """
        初始化时传入请求参数（用于填充频率信息）

        Args:
            request_params: 请求参数字典，包含:
                - startfreq: 起始频率 (Hz 或 "137MHz" 格式)
                - stopfreq: 结束频率 (Hz 或 "173MHz" 格式)
                - step: 步进 (Hz 或 "25kHz" 格式)
                - frame_channels: 每帧信道数 (默认 512)
                - mfid: 设备标识 (可选)
        """
        self.request_params = request_params
        self._parse_freq_params()

    def _parse_freq_params(self):
        """解析频率参数"""
        params = self.request_params

        # 解析起始频率
        startfreq = params.get('startfreq', '137MHz')
        if isinstance(startfreq, str):
            self.start_freq = self._parse_freq(startfreq)
        else:
            self.start_freq = int(startfreq)

        # 解析结束频率
        stopfreq = params.get('stopfreq', '173MHz')
        if isinstance(stopfreq, str):
            self.stop_freq = self._parse_freq(stopfreq)
        else:
            self.stop_freq = int(stopfreq)

        # 解析步长
        step = params.get('step', '25kHz')
        if isinstance(step, str):
            self.step = self._parse_freq(step)
        else:
            self.step = int(step)

        # 计算总信道数
        self.total_channels = params.get('total_channels')
        if self.total_channels is None:
            self.total_channels = int((self.stop_freq - self.start_freq) / self.step) + 1

        # 每帧信道数
        self.frame_channels = params.get('frame_channels', 512)

    def _parse_freq(self, freq_str: str) -> int:
        """解析频率字符串为 Hz

        Args:
            freq_str: 如 "137MHz", "25kHz", 137000000

        Returns:
            频率值 (Hz)
        """
        freq_str = str(freq_str).strip().lower()

        if freq_str.endswith('mhz'):
            return int(float(freq_str[:-3]) * 1_000_000)
        elif freq_str.endswith('khz'):
            return int(float(freq_str[:-3]) * 1_000)
        elif freq_str.endswith('hz'):
            return int(freq_str[:-2])
        else:
            # 尝试直接转为数字
            return int(float(freq_str))

    def format_fscan_data(self, raw_payload: bytes, tmstamp: int = 0) -> Dict[str, Any]:
        """
        将设备原始 payload 转换为标准 FSCAN 格式

        Args:
            raw_payload: 设备原始 payload 数据
            tmstamp: RMCP 帧时间戳 (FILETIME 格式)

        Returns:
            包含完整元数据的 FSCAN 数据字典
        """
        # 解析简化格式
        simple_data = self._parse_simple_fscan(raw_payload)

        if simple_data is None:
            return {'error': 'Failed to parse simple FSCAN format'}

        # 构建标准格式
        result = {
            # 标准格式固定字段
            'LEADER': FSCAN_LEADER_STANDARD,
            'version': 1,
            'stc': tmstamp,  # 使用 RMCP 帧时间戳
            'ts': self._filetime_to_datetime(tmstamp),
            'pl': len(raw_payload),
            'el': 0,

            # 数据类型
            'dt': 12,  # DT:12 表示频谱观测数据
            'dl': simple_data['raw_size'] - 11,  # 数据长度

            # 频段信息
            'band_no': 1,  # 频段序号
            'total_channels': self.total_channels,
            'start_freq': self.start_freq,
            'end_freq': self.stop_freq,
            'start_index': 0,
            'step': self.step,

            # 帧信息
            'frame_channels': simple_data['nArrays'],

            # 电平数据 (已经过 ÷256 转换)
            'levels': simple_data['levels'],
            'level_count': len(simple_data['levels']),

            # 原始信息
            'raw_format': 'simple',
            'raw_nArrays': simple_data['nArrays'],
        }

        return result

    def _parse_simple_fscan(self, payload: bytes) -> Optional[Dict[str, Any]]:
        """
        解析简化格式 FSCAN payload

        简化格式结构 (1035 字节):
        - Byte 0-3: LEADER = 0x10F (271)
        - Byte 4: VER = 2
        - Byte 5-10: 保留 (0)
        - Byte 11-end: 电平数据 ((payload长度-11)/2 水平 × 2 字节)

        Returns:
            解析结果字典，或 None
        """
        if len(payload) < 12:
            return None

        try:
            # 提取 LEADER
            leader = struct.unpack('<I', payload[0:4])[0]

            # 计算 nArrays (帧信道数) = (payload长度 - 11) / 2
            nArrays = (len(payload) - 11) // 2

            # 提取电平数据 (从 offset 11 开始)
            levels = []
            offset = 11
            while offset + 1 < len(payload):
                val = struct.unpack('<h', payload[offset:offset+2])[0]
                # 转换为 dBm: 原值 ÷ 10 (原始数据是 dBm×10)
                dbm = round(val / 10.0, 1)
                levels.append(dbm)
                offset += 2

            # 注意：不进行过滤，所有电平都是有效数据
            # 信号范围通常在 -110 ~ -30 dBm

            return {
                'leader': leader,
                'ver': payload[4],
                'nArrays': nArrays,
                'raw_size': len(payload),
                'levels': levels,
            }

        except Exception as e:
            return None

    def _filetime_to_datetime(self, filetime: int) -> str:
        """
        将 Windows FILETIME 转换为 ISO 格式时间字符串

        Args:
            filetime: Windows FILETIME (100 纳秒间隔，从 1601-01-01 开始)

        Returns:
            ISO 格式时间字符串
        """
        if filetime == 0:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]

        try:
            # FILETIME epoch: 1601-01-01
            epoch = datetime(1601, 1, 1)
            # 转换为微秒
            microseconds = filetime // 10
            dt = epoch + timedelta(microseconds=microseconds)
            return dt.strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]


def format_streaming_frame(frame_data: bytes, tmstamp: int, request_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    便捷函数：将单个 streaming DATA 帧格式化为标准格式

    Args:
        frame_data: 完整 RMCP DATA 帧 (包含 18 字节头)
        tmstamp: 时间戳
        request_params: 请求参数

    Returns:
        格式化后的数据
    """
    formatter = AtomDataFormatter(request_params)
    payload = frame_data[18:]  # 去掉 RMCP 帧头
    return formatter.format_fscan_data(payload, tmstamp)


# ============================================
# 测试
# ============================================

if __name__ == '__main__':
    # 测试数据 (从 capture_20260412_173848.json 提取)
    import json

    with open('rmcp_proxy/capture/capture_20260412_173848.json', 'r', encoding='utf-8') as f:
        capture = json.load(f)

    # 找到第一个 DATA 帧
    for item in capture:
        if item.get('data_type') == 'SIMPLE_FSCAN':
            hex_str = item['hex']
            frame_data = bytes.fromhex(hex_str)

            # RMCP 帧头解析
            tmstamp = struct.unpack('<Q', frame_data[4:12])[0]

            # 请求参数 (从之前的 B_FScan 请求)
            request_params = {
                'startfreq': '137MHz',
                'stopfreq': '173MHz',
                'step': '25kHz',
                'frame_channels': 512,
            }

            # 格式化
            formatter = AtomDataFormatter(request_params)
            result = formatter.format_fscan_data(frame_data[18:], tmstamp)

            print('=== 标准 FSCAN 格式 ===')
            print('LEADER:', result['LEADER'])
            print('version:', result['version'])
            print('stc:', result['stc'])
            print('ts:', result['ts'])
            print('pl:', result['pl'])
            print('el:', result['el'])
            print('dt:', result['dt'])
            print('dl:', result['dl'])
            print('band_no:', result['band_no'])
            print('total_channels:', result['total_channels'])
            print('start_freq:', result['start_freq'])
            print('end_freq:', result['end_freq'])
            print('step:', result['step'])
            print('frame_channels:', result['frame_channels'])
            print('level_count:', result['level_count'])
            print('levels:', result['levels'])
            print('levels:', result['levels'])
            break
