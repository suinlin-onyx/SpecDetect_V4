"""常规监测场景"""
from typing import Dict, Any


class NormalScenario:
    """常规监测场景"""

    def __init__(self):
        self.name = '常规监测'
        self.frequency = 100_000_000  # 100MHz
        self.amplitude = -60  # dBm
        self.bandwidth = 120_000  # 120kHz
        self.noise_floor = -100  # dBm

    def get_signal_params(self) -> Dict[str, Any]:
        """获取信号参数"""
        return {
            'frequency': self.frequency,
            'amplitude': self.amplitude,
            'bandwidth': self.bandwidth,
            'noise_floor': self.noise_floor
        }

    def is_valid_frequency(self, freq: int) -> bool:
        """检查频率是否在有效范围内"""
        return 20_000_000 <= freq <= 3_000_000_000
