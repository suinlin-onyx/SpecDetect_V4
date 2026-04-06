"""虚拟设备测试"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mock_device.data_generator import DataGenerator
from app.mock_device.frame_builder import MockFrameBuilder


class TestDataGenerator:
    """数据生成器测试"""

    def setup_method(self):
        self.generator = DataGenerator(scenario='normal')

    def test_normal_scenario(self):
        """测试常规场景"""
        self.generator.set_scenario('normal')
        assert self.generator.scenario == 'normal'

    def test_interference_scenario(self):
        """测试干扰场景"""
        self.generator.set_scenario('interference')
        assert self.generator.scenario == 'interference'

    def test_generate_spectrum_data(self):
        """测试生成频谱数据"""
        data = self.generator.generate_spectrum_data()
        assert data is not None
        assert len(data) > 0

    def test_generate_direction_data(self):
        """测试生成测向数据"""
        direction, amplitude = self.generator.generate_direction_data()
        assert 0 <= direction <= 360
        assert -120 <= amplitude <= -20

    def test_generate_single_frequency_data(self):
        """测试生成单频数据"""
        data = self.generator.generate_single_frequency_data()
        assert data is not None
        assert len(data) > 0


class TestMockFrameBuilder:
    """Mock帧构建器测试"""

    def setup_method(self):
        self.builder = MockFrameBuilder()

    def test_build_response_frame(self):
        """测试构建响应帧"""
        payload = b'\x10\x00\x00\x00'
        frame = self.builder.build_response_frame(
            business_type=0x10,
            payload=payload
        )

        # 验证帧长度
        assert len(frame) > 18

        # 验证帧头 - dwLength = business_type(1字节) + payload
        import struct
        length = struct.unpack('!I', frame[0:4])[0]
        assert length == 1 + len(payload)

    def test_build_direction_frame(self):
        """测试构建测向帧"""
        frame = self.builder.build_direction_frame(
            direction=127.5,
            amplitude=-65.0
        )

        assert len(frame) > 18
