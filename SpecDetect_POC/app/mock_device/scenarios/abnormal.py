"""异常场景"""
from typing import Dict, Any, Optional


class AbnormalScenario:
    """异常场景"""

    def __init__(self):
        self.name = '异常场景'
        self.failure_type = 'data_error'  # 数据错误
        self.noise_floor = -80  # dBm (异常：噪声提高)

    def get_failure_info(self) -> Dict[str, Any]:
        """获取故障信息"""
        return {
            'type': self.failure_type,
            'description': '模拟数据异常'
        }

    def should_inject_error(self) -> bool:
        """是否注入错误"""
        return True

    def get_corrupted_data(self, data: bytes) -> bytes:
        """获取损坏的数据"""
        if not data:
            return data
        # 将随机位置的1个字节翻转
        import random
        byte_list = bytearray(data)
        idx = random.randint(0, len(byte_list) - 1)
        byte_list[idx] ^= 0xFF
        return bytes(byte_list)
