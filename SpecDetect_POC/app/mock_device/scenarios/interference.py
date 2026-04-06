"""干扰场景"""
from typing import List, Dict, Any


class InterferenceScenario:
    """干扰场景"""

    def __init__(self):
        self.name = '干扰场景'
        self.signals = [
            {'freq': 100_000_000, 'amp': -50, 'type': 'main'},
            {'freq': 100_500_000, 'amp': -70, 'type': 'interference'},
            {'freq': 101_000_000, 'amp': -55, 'type': 'interference'}
        ]
        self.noise_floor = -90  # dBm

    def get_signals(self) -> List[Dict[str, Any]]:
        """获取所有信号"""
        return self.signals

    def has_interference(self) -> bool:
        """是否有干扰信号"""
        return len(self.signals) > 1
