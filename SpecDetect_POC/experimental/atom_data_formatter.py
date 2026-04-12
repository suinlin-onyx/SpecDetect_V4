# -*- coding: utf-8 -*-
"""
Atom 数据整理器

功能:
模拟 Atom 对设备原始数据的整理，将简化格式转换为标准 FSCAN 格式。

设备原始数据 (简化格式):
- LEADER=271 (0x10F)
- 无频段信息
- 电平数据需要 ÷10 转换 (dBm×10 → dBm)

用户期望的标准格式:
- LEADER=0xEEEE1DE6
- 完整频段信息 (起始频率、结束频率、步长、信道总数等)
- 电平为直接 dBm 值

支持的接口:
- B_FScan (funcid=15): DT=12, 频谱观测 (512信道/帧)
- B_MScan (funcid=14): DT=13, 频率表扫描 (单频点)
- B_PScan (funcid=13): DT=12, 频谱观测 (512信道/帧)
- B_SglFreqMeas (funcid=12): DT=7/101/8, 多种数据类型
"""

import struct
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta


# ============================================
# 常量
# ============================================

# 标准 FSCAN 格式 LEADER
# 0xEEEE1DE6 as signed 32-bit int = -286331154
FSCAN_LEADER_STANDARD = -286331154

# 简化格式 LEADER
FSCAN_LEADER_SIMPLE = 0x10F  # 271

# 数据类型常量
DT_SPECTRUM_OBSERVATION = 12  # 扫频频谱观测数据
DT_FREQ_TABLE_SCAN = 13       # 频率表扫描数据
DT_SPECTRUM = 7              # 频谱数据
DT_LEVEL = 101               # 电平数据
DT_ITU = 8                   # ITU测量数据


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
        """解析频率参数

        支持两种模式:
        1. startfreq/stopfreq/step 模式 (B_FScan, B_MScan)
        2. frequency 模式 (B_PScan, B_SglFreqMeas)
        """
        params = self.request_params

        # 检查是否有 frequency 参数 (单频点模式)
        frequency = params.get('frequency')
        if frequency:
            # 单频点模式
            if isinstance(frequency, str):
                self.start_freq = self._parse_freq(frequency)
            else:
                self.start_freq = int(frequency)
            self.stop_freq = self.start_freq
            self.step = params.get('step', '25kHz')
            if isinstance(self.step, str):
                self.step = self._parse_freq(self.step)
            else:
                self.step = int(self.step)
            self.total_channels = 1
            self.frame_channels = params.get('frame_channels', 256)
        else:
            # 范围模式 (startfreq/stopfreq/step)
            startfreq = params.get('startfreq', '137MHz')
            if isinstance(startfreq, str):
                self.start_freq = self._parse_freq(startfreq)
            else:
                self.start_freq = int(startfreq)

            stopfreq = params.get('stopfreq', '173MHz')
            if isinstance(stopfreq, str):
                self.stop_freq = self._parse_freq(stopfreq)
            else:
                self.stop_freq = int(stopfreq)

            step = params.get('step', '25kHz')
            if isinstance(step, str):
                self.step = self._parse_freq(step)
            else:
                self.step = int(step)

            self.total_channels = params.get('total_channels')
            if self.total_channels is None:
                self.total_channels = int((self.stop_freq - self.start_freq) / self.step) + 1

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

            # 电平数据 (已经过 ÷10 转换)
            'levels': simple_data['levels'],
            'level_count': len(simple_data['levels']),

            # 原始信息
            'raw_format': 'simple',
            'raw_nArrays': simple_data['nArrays'],
        }

        return result

    def format_mscan_data(self, raw_payload: bytes, tmstamp: int = 0) -> Dict[str, Any]:
        """
        将设备原始 payload 转换为标准 MSCAN 格式 (DT=13)

        B_MScan: 频率表扫描，单频点电平数据

        Args:
            raw_payload: 设备原始 payload 数据
            tmstamp: RMCP 帧时间戳 (FILETIME 格式)

        Returns:
            包含完整元数据的 MSCAN 数据字典
        """
        # 解析简化格式
        simple_data = self._parse_simple_fscan(raw_payload)

        if simple_data is None:
            return {'error': 'Failed to parse simple MSCAN format'}

        # B_MScan 只有单频率点，电平值在原始数据中
        # 简化格式: offset=11 开始，每2字节为一个电平值
        levels = simple_data['levels']
        freq_count = len(levels) // 2  # 频率数和电平数交替

        # 构建标准格式
        result = {
            # 标准格式固定字段
            'LEADER': FSCAN_LEADER_STANDARD,
            'version': 1,
            'stc': tmstamp,
            'ts': self._filetime_to_datetime(tmstamp),
            'pl': len(raw_payload),
            'el': 0,

            # 数据类型 - DT=13 表示频率表扫描
            'dt': DT_FREQ_TABLE_SCAN,
            'dl': simple_data['raw_size'] - 11,

            # 频段信息
            'band_no': 1,
            'total_channels': freq_count,
            'start_freq': self.start_freq,
            'end_freq': self.stop_freq,
            'start_index': 0,
            'step': self.step,

            # 帧信息 - MSCAN 单帧包含所有频率点
            'frame_channels': freq_count,

            # 电平数据
            'levels': levels,
            'level_count': len(levels),

            # MSCAN 特有字段
            'freq_count': freq_count,
            'frequencies': self._calc_frequencies(freq_count),

            # 原始信息
            'raw_format': 'simple',
        }

        return result

    def format_pscan_data(self, raw_payload: bytes, tmstamp: int = 0) -> Dict[str, Any]:
        """
        将设备原始 payload 转换为标准 PSCAN 格式 (DT=12)

        B_PScan: 频谱观测，与 FSCAN 类似但参数不同

        Args:
            raw_payload: 设备原始 payload 数据
            tmstamp: RMCP 帧时间戳 (FILETIME 格式)

        Returns:
            包含完整元数据的 PSCAN 数据字典
        """
        # 解析简化格式
        simple_data = self._parse_simple_fscan(raw_payload)

        if simple_data is None:
            return {'error': 'Failed to parse simple PSCAN format'}

        # 构建标准格式
        result = {
            # 标准格式固定字段
            'LEADER': FSCAN_LEADER_STANDARD,
            'version': 1,
            'stc': tmstamp,
            'ts': self._filetime_to_datetime(tmstamp),
            'pl': len(raw_payload),
            'el': 0,

            # 数据类型 - DT=12 表示扫频频谱观测
            'dt': DT_SPECTRUM_OBSERVATION,
            'dl': simple_data['raw_size'] - 11,

            # 频段信息
            'band_no': 1,
            'total_channels': self.total_channels,
            'start_freq': self.start_freq,
            'end_freq': self.stop_freq,
            'start_index': 0,
            'step': self.step,

            # 帧信息 - PSCAN 每帧512信道
            'frame_channels': simple_data['nArrays'],

            # 电平数据
            'levels': simple_data['levels'],
            'level_count': len(simple_data['levels']),

            # 原始信息
            'raw_format': 'simple',
            'raw_nArrays': simple_data['nArrays'],
        }

        return result

    def format_sglfreq_data(self, raw_payload: bytes, tmstamp: int = 0) -> Dict[str, Any]:
        """
        将设备原始 payload 转换为标准 SGLFREQ 格式

        B_SglFreqMeas: 单频点测量，可能包含多种 DT 类型
        - DT=7: 频谱数据 (256信道/帧)
        - DT=101: 电平数据
        - DT=8: ITU测量数据

        Args:
            raw_payload: 设备原始 payload 数据
            tmstamp: RMCP 帧时间戳 (FILETIME 格式)

        Returns:
            包含完整元数据的 SGLFREQ 数据字典
        """
        # 解析简化格式
        simple_data = self._parse_simple_fscan(raw_payload)

        if simple_data is None:
            return {'error': 'Failed to parse simple SGLFREQ format'}

        # 检测 DT 类型
        dt = self._detect_dt_type(simple_data)

        # 构建标准格式
        result = {
            # 标准格式固定字段
            'LEADER': FSCAN_LEADER_STANDARD,
            'version': 1,
            'stc': tmstamp,
            'ts': self._filetime_to_datetime(tmstamp),
            'pl': len(raw_payload),
            'el': 0,

            # 数据类型
            'dt': dt,
            'dl': simple_data['raw_size'] - 11,

            # 频段信息 - SGLFREQ 使用不同的频率范围
            'band_no': 1,
            'total_channels': self.total_channels,
            'start_freq': self.start_freq,
            'end_freq': self.stop_freq,
            'start_index': 0,
            'step': self.step,

            # 帧信息 - SGLFREQ 每帧256信道
            'frame_channels': simple_data['nArrays'],

            # 电平数据
            'levels': simple_data['levels'],
            'level_count': len(simple_data['levels']),

            # SGLFREQ 特有字段
            'center_frequency': self.start_freq,  # 单频点测量

            # 原始信息
            'raw_format': 'simple',
            'raw_nArrays': simple_data['nArrays'],
        }

        return result

    def _detect_dt_type(self, simple_data: Dict[str, Any]) -> int:
        """
        根据 payload 特征检测 DT 类型

        Args:
            simple_data: 解析后的简化格式数据

        Returns:
            DT 类型值
        """
        nArrays = simple_data.get('nArrays', 0)
        raw_size = simple_data.get('raw_size', 0)

        # DT=7: 频谱数据，通常每帧256信道
        if nArrays == 256:
            return DT_SPECTRUM

        # DT=101: 电平数据，通常 payload 很小
        if raw_size < 100:
            return DT_LEVEL

        # DT=8: ITU测量数据
        # 需要更多特征来区分

        # 默认返回 DT=7
        return DT_SPECTRUM

    def _calc_frequencies(self, freq_count: int) -> List[float]:
        """
        计算频率列表

        Args:
            freq_count: 频率数量

        Returns:
            频率列表 (MHz)
        """
        frequencies = []
        for i in range(freq_count):
            freq = self.start_freq + i * self.step
            frequencies.append(freq / 1e6)  # 转换为 MHz
        return frequencies

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

    根据请求参数中的 funcid 或 action 参数决定使用哪种格式化器。

    Args:
        frame_data: 完整 RMCP DATA 帧 (包含 18 字节头)
        tmstamp: 时间戳
        request_params: 请求参数，包含:
            - funcid: 功能ID (12=B_SglFreqMeas, 13=B_PScan, 14=B_MScan, 15=B_FScan)
            - action: SOAPAction 名称 (如 "B_FScan")
            - startfreq/stopfreq/step: 频率参数

    Returns:
        格式化后的数据
    """
    formatter = AtomDataFormatter(request_params)
    payload = frame_data[18:]  # 去掉 RMCP 帧头

    # 根据 funcid 或 action 决定格式化器类型
    funcid = request_params.get('funcid', 0)
    action = request_params.get('action', '')

    # 如果 action 包含接口名称，使用对应的格式化器
    if 'B_MScan' in action and 'DF' not in action:
        return formatter.format_mscan_data(payload, tmstamp)
    elif 'B_PScan' in action:
        return formatter.format_pscan_data(payload, tmstamp)
    elif 'B_SglFreqMeas' in action:
        return formatter.format_sglfreq_data(payload, tmstamp)
    elif 'B_FScan' in action or funcid == 15:
        return formatter.format_fscan_data(payload, tmstamp)

    # 默认使用 FSCAN 格式化器
    return formatter.format_fscan_data(payload, tmstamp)


def get_funcid_from_action(action: str) -> int:
    """
    从 SOAPAction 获取 funcid

    Args:
        action: SOAPAction 名称

    Returns:
        funcid 值
    """
    funcid_map = {
        'B_FScan': 15,
        'B_FScanDF': 21,
        'B_MScan': 14,
        'B_MScanDF': 16,
        'B_PScan': 13,
        'B_SglFreqDF': 11,
        'B_SglFreqMeas': 12,
        'B_StopMeas': 32,
        'B_WBDF': 25,
        'B_QueryDeviceInfo': 10,
    }
    return funcid_map.get(action.strip('"'), 15)


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
