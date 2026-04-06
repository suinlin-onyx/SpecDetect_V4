"""数据模拟生成器"""
import numpy as np
import struct
from typing import Dict, Any, Tuple, List, Optional
from utils.logger import get_logger

logger = get_logger('mock.data')


class DataGenerator:
    """数据模拟生成器"""

    # 频谱数据参数
    FREQUENCY_RANGE = (20_000_000, 3_000_000_000)  # 20MHz - 3GHz
    AMPLITUDE_RANGE = (-120, -20)  # dBm
    NOISE_FLOOR = -100  # dBm

    # 测向数据参数
    DIRECTION_RANGE = (0, 360)  # 度

    # 数据更新率
    UPDATE_INTERVAL = 0.1  # 秒

    def __init__(self, scenario: str = 'normal'):
        self.scenario = scenario
        self.scenario_config = self._get_scenario_config()

    def _get_scenario_config(self) -> Dict[str, Any]:
        """获取场景配置"""
        configs = {
            'normal': {
                'name': '常规监测',
                'frequency': 100_000_000,
                'amplitude': -60,
                'noise': -100,
                'bandwidth': 120_000,
                'signals': [{'freq': 100_000_000, 'amp': -60, 'bw': 120000}]
            },
            'interference': {
                'name': '干扰场景',
                'frequency': 100_000_000,
                'amplitude': -50,
                'noise': -90,
                'signals': [
                    {'freq': 100_000_000, 'amp': -50, 'bw': 120000},
                    {'freq': 100_500_000, 'amp': -70, 'bw': 100000},
                    {'freq': 101_000_000, 'amp': -55, 'bw': 150000}
                ]
            },
            'abnormal': {
                'name': '异常场景',
                'frequency': 100_000_000,
                'amplitude': -60,
                'noise': -80,  # 噪声提高
                'signals': []
            },
            'boundary': {
                'name': '边界场景',
                'frequency': 3_000_000_000,
                'amplitude': -120,
                'noise': -100,
                'signals': [{'freq': 3_000_000_000, 'amp': -120, 'bw': 1000000}]
            },
            'stress': {
                'name': '压力测试',
                'frequency': 100_000_000,
                'amplitude': -60,
                'signal_count': 100,
                'noise': -90,
                'signals': []
            }
        }
        return configs.get(self.scenario, configs['normal'])

    def set_scenario(self, scenario: str):
        """设置场景"""
        self.scenario = scenario
        self.scenario_config = self._get_scenario_config()
        logger.info(f"场景切换: {scenario}")

    def generate_spectrum_data(self, start_freq: Optional[int] = None,
                               end_freq: Optional[int] = None,
                               step: Optional[int] = None) -> bytes:
        """
        生成频谱数据

        Args:
            start_freq: 起始频率(Hz)
            end_freq: 终止频率(Hz)
            step: 频率步进(Hz)

        Returns:
            频谱数据字节 (FSCAN格式)
        """
        if start_freq is None:
            start_freq = self.scenario_config.get('frequency', 100_000_000) - 5_000_000
        if end_freq is None:
            end_freq = self.scenario_config.get('frequency', 100_000_000) + 5_000_000
        if step is None:
            step = 100_000  # 100kHz步进

        # 计算点数
        num_points = max(50, min(500, (end_freq - start_freq) // step))

        # 生成频率点和幅度
        frequencies = np.linspace(start_freq, end_freq, num_points)

        signals = self.scenario_config.get('signals', [])
        noise = self.scenario_config.get('noise', self.NOISE_FLOOR)

        amplitudes = np.random.normal(noise, 5, num_points)

        # 添加信号峰值
        for signal in signals:
            sig_freq = signal['freq']
            sig_amp = signal['amp']
            sig_bw = signal.get('bw', 120000)

            # 在信号附近叠加峰值
            for i, freq in enumerate(frequencies):
                if abs(freq - sig_freq) < sig_bw / 2:
                    # 高斯加权
                    distance = abs(freq - sig_freq) / (sig_bw / 2)
                    gain = np.exp(-distance * 2)
                    amplitudes[i] = sig_amp * gain + amplitudes[i] * (1 - gain)

        amplitudes = np.clip(amplitudes, -120, -20)

        # FSCAN数据格式
        n_arrays = len(frequencies)
        header = struct.pack(
            '!B H I I',
            0x15,    # nBdType (FSCAN)
            0x01,    # nFlags (基础业务数据)
            n_arrays,
            0        # nOffset
        )

        dynamic = b''
        for amp in amplitudes:
            dynamic += struct.pack('!h', int(amp * 100))

        return header + dynamic

    def generate_direction_data(self, frequency: Optional[int] = None) -> Tuple[float, float]:
        """
        生成测向数据

        Args:
            frequency: 频率(Hz)，用于查找对应信号

        Returns:
            (方向角度, 幅度)
        """
        if frequency is None:
            frequency = self.scenario_config.get('frequency', 100_000_000)

        signals = self.scenario_config.get('signals', [])

        # 查找对应频率的信号
        matched_signal = None
        for signal in signals:
            if abs(signal['freq'] - frequency) < 100_000:
                matched_signal = signal
                break

        if matched_signal:
            amplitude = matched_signal['amp'] + np.random.normal(0, 1)
        else:
            amplitude = self.scenario_config.get('amplitude', -60) + np.random.normal(0, 3)

        # 生成方向
        direction = np.random.uniform(0, 360)
        return float(direction), float(np.clip(amplitude, -120, -20))

    def generate_single_frequency_data(self, frequency: Optional[int] = None) -> bytes:
        """
        生成单频测量数据

        Args:
            frequency: 频率(Hz)

        Returns:
            单频测量数据字节 (SGLFREQ格式)
        """
        if frequency is None:
            frequency = self.scenario_config.get('frequency', 100_000_000)

        signals = self.scenario_config.get('signals', [])

        # 查找对应频率的信号
        amplitude = self.scenario_config.get('amplitude', -60)
        for signal in signals:
            if abs(signal['freq'] - frequency) < 100_000:
                amplitude = signal['amp']
                break

        amplitude += np.random.normal(0, 1)
        amplitude = np.clip(amplitude, -120, -20)

        # SGLFREQ数据格式
        header = struct.pack(
            '!B H I I',
            0x10,    # nBdType (SGLFREQ)
            0x01,    # nFlags
            1,       # nArrays (1个ITU)
            0        # nOffset
        )

        freq_part = struct.pack('!Q', frequency)

        dynamic = struct.pack(
            '!f h h',
            amplitude,                    # ITU值
            0,                            # 占用度 (occ * 100)
            int(-100 * 100)              # 门限 (thr * 100)
        )

        return header + freq_part + dynamic

    def generate_ifanalysis_data(self, frequency: int, span: int = 1_000_000) -> bytes:
        """
        生成中频分析数据

        Args:
            frequency: 中心频率(Hz)
            span: 跨距(Hz)

        Returns:
            中频分析数据字节 (IFANALYSIS格式)
        """
        num_points = min(500, max(100, span // 10000))
        frequencies = np.linspace(frequency - span // 2, frequency + span // 2, num_points)

        noise = self.scenario_config.get('noise', self.NOISE_FLOOR)
        amplitudes = np.random.normal(noise, 5, num_points)

        # 添加中心频率峰值
        signals = self.scenario_config.get('signals', [])
        for signal in signals:
            if abs(signal['freq'] - frequency) < span:
                for i, freq in enumerate(frequencies):
                    distance = abs(freq - signal['freq']) / (span / 2)
                    gain = np.exp(-distance * 2)
                    amplitudes[i] = signal['amp'] * gain + amplitudes[i] * (1 - gain)

        amplitudes = np.clip(amplitudes, -120, -20)

        header = struct.pack(
            '!B H I I',
            0x11,               # nBdType (IFANALYSIS)
            0x01,              # nFlags
            num_points,         # nArrays
            0                   # nOffset
        )

        fixed = struct.pack('!Q h', frequency, int(np.mean(amplitudes) * 100))

        dynamic = b''
        for amp in amplitudes:
            dynamic += struct.pack('!h', int(amp * 100))

        return header + fixed + dynamic
