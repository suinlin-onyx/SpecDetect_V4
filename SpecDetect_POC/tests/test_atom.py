"""原子服务测试"""
import pytest
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.atom_service.protocol_parser import RMCPTPParser, BusinessDataParser
from app.atom_service.protocol_builder import RMCPTPBuilder, BusinessDataBuilder
from utils.exceptions import ProtocolParseError, ChecksumError


class TestRMCPTPParser:
    """RMCPTP协议解析器测试"""

    def setup_method(self):
        self.parser = RMCPTPParser()
        self.builder = RMCPTPBuilder()

    def test_parse_valid_frame(self):
        """测试解析有效帧"""
        # 构建测试帧
        payload = b'\x10\x00\x00\x00\x01'  # 业务数据
        frame = self.builder.build_frame(data_type=0x00, payload=payload)

        header_info, remaining = self.parser.parse_frame(frame)

        assert header_info['dw_length'] == len(payload)
        assert header_info['n_version'] == 0x0007
        assert header_info['n_data_type'] == 0x00

    def test_parse_frame_insufficient_data(self):
        """测试解析数据不足的帧"""
        with pytest.raises(ProtocolParseError):
            self.parser.parse_frame(b'\x00\x00')

    def test_parse_frame_checksum_error(self):
        """测试校验和错误"""
        # 构建帧但篡改校验和
        # 帧格式: header_without_checksum(16字节) + checksum(2字节) + payload
        # 校验和位于索引16-17，payload紧随其后
        frame = self.builder.build_frame(data_type=0x00, payload=b'\x00')
        frame = bytearray(frame)
        # 校验和是最后2字节（索引16和17），payload只有1字节在索引18
        # 篡改校验和的最后一个字节
        frame[17] ^= 0xFF  # 翻转校验和字节
        frame = bytes(frame)

        with pytest.raises(ChecksumError):
            self.parser.parse_frame(frame)

    def test_checksum_calculation(self):
        """测试校验和计算一致性"""
        payload = b'\x10\x00\x00\x00\x01\x02\x03\x04'
        frame = self.builder.build_frame(data_type=0x00, payload=payload)

        # 再次解析应该成功
        header_info, remaining = self.parser.parse_frame(frame)
        assert header_info['n_data_type'] == 0x00


class TestRMCPTPBuilder:
    """RMCPTP协议构建器测试"""

    def setup_method(self):
        self.builder = RMCPTPBuilder()
        self.parser = RMCPTPParser()

    def test_build_frame(self):
        """测试构建帧"""
        payload = b'\x10\x00\x00\x00'
        frame = self.builder.build_frame(data_type=0x00, payload=payload)

        assert len(frame) == RMCPTPParser.HEADER_SIZE + len(payload)

        # 验证长度字段
        length = struct.unpack('!I', frame[0:4])[0]
        assert length == len(payload)

    def test_build_frame_with_timestamp(self):
        """测试带时间戳的帧构建"""
        payload = b'\x00'
        timestamp = 116444736000000000  # 1970-01-01的FILETIME
        frame = self.builder.build_frame(
            data_type=0x00,
            payload=payload,
            timestamp=timestamp
        )

        # 验证时间戳
        ts = struct.unpack('!Q', frame[4:12])[0]
        assert ts == timestamp

    def test_build_sglfreq_command(self):
        """测试构建单频测量命令"""
        frame = self.builder.build_sglfreq_command(
            frequency=100_000_000,
            antenna="default"
        )

        assert len(frame) > RMCPTPParser.HEADER_SIZE
        # 业务类型在载荷的第一个字节
        assert frame[RMCPTPParser.HEADER_SIZE] == 0x10  # SGLFREQ

    def test_build_fscan_command(self):
        """测试构建频段扫描命令"""
        frame = self.builder.build_fscan_command(
            start_freq=100_000_000,
            end_freq=200_000_000,
            step=1_000_000
        )

        assert len(frame) > RMCPTPParser.HEADER_SIZE
        # 载荷第一个字节是业务类型
        assert frame[RMCPTPParser.HEADER_SIZE] == 0x15  # FSCAN

    def test_frame_roundtrip(self):
        """测试帧构建和解析的往返"""
        original_payload = b'\x10\x00\x00\x00\x01\x02\x03\x04'
        frame = self.builder.build_frame(data_type=0x11, payload=original_payload)

        header, remaining = self.parser.parse_frame(frame)

        assert header['n_data_type'] == 0x11
        assert remaining == original_payload


class TestBusinessDataParser:
    """业务数据解析器测试"""

    def setup_method(self):
        self.parser = BusinessDataParser()
        self.builder = BusinessDataBuilder()

    def test_parse_sglfreq_data(self):
        """测试解析单频测量数据"""
        # 构建测试数据
        data = self.builder.build_sglfreq_data(
            frequency=100_000_000,
            itu_values=[-60.5, -61.0],
            occupancy=0.15,
            threshold=-100.0
        )

        business_info, remaining = self.parser.parse_business_header(data)
        assert business_info['n_bd_type'] == 0x10

    def test_parse_fscan_data(self):
        """测试解析频段扫描数据"""
        levels = [-60.0, -61.0, -62.0, -63.0, -64.0]
        data = self.builder.build_fscan_data(levels=levels)

        business_info, remaining = self.parser.parse_business_header(data)
        assert business_info['n_bd_type'] == 0x15
        assert business_info['n_arrays'] == 5


class TestBusinessDataBuilder:
    """业务数据构建器测试"""

    def setup_method(self):
        self.builder = BusinessDataBuilder()

    def test_build_sglfreq_data(self):
        """测试构建单频测量数据"""
        data = self.builder.build_sglfreq_data(
            frequency=100_000_000,
            itu_values=[-60.5],
            occupancy=0.1,
            threshold=-100.0
        )

        # 验证格式
        assert data[0] == 0x10  # nBdType
        n_arrays = struct.unpack('!I', data[3:7])[0]
        assert n_arrays == 1

    def test_build_fscan_data(self):
        """测试构建频段扫描数据"""
        levels = [-60.0, -61.0, -62.0]
        data = self.builder.build_fscan_data(levels=levels)

        assert data[0] == 0x15  # nBdType
        n_arrays = struct.unpack('!I', data[3:7])[0]
        assert n_arrays == 3

    def test_build_df_data(self):
        """测试构建测向数据"""
        data = self.builder.build_df_data(
            frequency=100_000_000,
            level=-60.0,
            df_level=-55.0,
            quality=0.95,
            azimuth=127.5
        )

        assert data[0] == 0x12  # nBdType
