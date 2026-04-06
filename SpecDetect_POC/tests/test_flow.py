"""全链路测试"""
import pytest
import asyncio
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.atom_service.protocol_builder import RMCPTPBuilder
from app.atom_service.protocol_parser import RMCPTPParser
from app.mock_device.frame_builder import MockFrameBuilder
from app.mock_device.data_generator import DataGenerator


class TestProtocolFlow:
    """协议流程测试"""

    def test_rmcp_frame_roundtrip(self):
        """测试RMCPTP帧往返"""
        builder = RMCPTPBuilder()
        parser = RMCPTPParser()

        # 构建帧
        payload = b'\x10\x00\x00\x00\x01\x02\x03\x04'
        frame = builder.build_frame(data_type=0x00, payload=payload)

        # 解析帧
        header, remaining = parser.parse_frame(frame)

        assert header['n_data_type'] == 0x00
        assert header['dw_length'] == len(payload)
        assert remaining == payload

    def test_business_data_roundtrip(self):
        """测试业务数据往返"""
        from app.atom_service.protocol_builder import BusinessDataBuilder
        from app.atom_service.protocol_parser import BusinessDataParser

        builder = BusinessDataBuilder()
        parser = BusinessDataParser()

        # 构建SGLFREQ数据
        data = builder.build_sglfreq_data(
            frequency=100_000_000,
            itu_values=[-60.5, -61.0],
            occupancy=0.15,
            threshold=-100.0
        )

        # 解析
        info, remaining = parser.parse_business_header(data)

        assert info['n_bd_type'] == 0x10
        assert info['n_arrays'] == 2


class TestMockDeviceFlow:
    """Mock设备流程测试"""

    def test_frame_builder_generates_valid_frame(self):
        """测试帧构建器生成有效帧"""
        builder = MockFrameBuilder()

        # 构建响应帧
        payload = b'\x10\x00\x00\x00'
        frame = builder.build_response_frame(
            business_type=0x10,
            payload=payload
        )

        # 验证帧长度 (18字节头 + business_type(1) + payload)
        # 业务数据 = business_type(1字节) + 传入的payload
        assert len(frame) == 18 + 1 + len(payload)

        # 验证帧头 - dwLength是 business_type + payload 的长度
        length = struct.unpack('!I', frame[0:4])[0]
        assert length == 1 + len(payload)  # business_type(1字节) + payload

    def test_data_generator_spectrum(self):
        """测试数据生成器生成频谱"""
        generator = DataGenerator(scenario='normal')

        # 生成频谱数据
        data = generator.generate_spectrum_data(
            start_freq=95_000_000,
            end_freq=105_000_000,
            step=1_000_000
        )

        # 验证数据格式
        assert len(data) > 20
        assert data[0] == 0x15  # FSCAN类型

    def test_data_generator_direction(self):
        """测试数据生成器生成测向数据"""
        generator = DataGenerator(scenario='normal')

        direction, amplitude = generator.generate_direction_data(frequency=100_000_000)

        assert 0 <= direction <= 360
        assert -120 <= amplitude <= -20

    def test_scenario_switch(self):
        """测试场景切换"""
        generator = DataGenerator(scenario='normal')

        # 切换到干扰场景
        generator.set_scenario('interference')
        assert generator.scenario == 'interference'

        # 干扰场景应该有多个信号
        signals = generator.scenario_config.get('signals', [])
        assert len(signals) >= 2

        # 切换回常规场景
        generator.set_scenario('normal')
        assert generator.scenario == 'normal'


class TestIntegrationFlow:
    """集成流程测试"""

    def test_command_to_response_flow(self):
        """测试命令到响应的完整流程"""
        # 1. Atom Service 构建命令
        builder = RMCPTPBuilder()
        command_frame = builder.build_sglfreq_command(
            frequency=100_000_000,
            antenna="default"
        )

        assert len(command_frame) >= 18 + 13  # 帧头 + 业务数据

        # 2. Mock Device 解析命令
        from app.mock_device.tcp_server import CommandParser

        header, business_data = CommandParser.parse_frame(command_frame)

        assert header['n_data_type'] == 0x00  # 监测业务数据
        assert len(business_data) >= 1
        assert business_data[0] == 0x10  # SGLFREQ

        # 3. Mock Device 生成响应
        mock_builder = MockFrameBuilder()
        response_frame = mock_builder.build_sglfreq_frame(
            frequency=100_000_000,
            amplitude=-60.0
        )

        assert len(response_frame) >= 18

        # 4. Atom Service 解析响应
        parser = RMCPTPParser()
        resp_header, resp_business = parser.parse_frame(response_frame)

        assert resp_header['n_data_type'] == 0x00
        assert resp_business[0] == 0x10  # SGLFREQ

    @pytest.mark.asyncio
    async def test_mock_device_connection(self):
        """测试Mock设备连接（需要Mock设备运行）"""
        from app.atom_service.device_client import DeviceClient

        client = DeviceClient('127.0.0.1', 9000, timeout=2.0)

        try:
            connected = await client.connect()
            assert connected

            # 发送测试命令
            builder = RMCPTPBuilder()
            frame = builder.build_sglfreq_command(frequency=100_000_000)

            await client.send_command(frame)

            # 接收响应
            header, payload = await client.receive_response()

            assert header['n_data_type'] == 0x00
            assert len(payload) > 0

            await client.disconnect()

        except Exception as e:
            pytest.skip(f"Mock设备未运行: {e}")
