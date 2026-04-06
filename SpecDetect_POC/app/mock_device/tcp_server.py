"""虚拟设备TCP服务器

实现RMCPTP v2.0协议，支持命令解析和响应生成
"""
import asyncio
import struct
import time
from typing import Optional, Dict, Any, Tuple
from .frame_builder import MockFrameBuilder
from .data_generator import DataGenerator
from utils.logger import get_logger
from utils.exceptions import ProtocolParseError, ChecksumError

logger = get_logger('mock.tcp')


# 错误码定义
class ErrorCode:
    SUCCESS = 0
    ERR_DEVICE_NOT_SUPPORTED = 0x3004
    ERR_DEVICE_PARAM_ERROR = 0x3006
    ERR_FREQ_OUT_OF_RANGE = 0x4004


class DeviceCapabilities:
    """设备能力配置"""

    # 设备类型及其能力
    DEVICES = {
        'MD1000': {
            'name': 'MD1000 监测/测向设备',
            'freq_range': (20_000_000, 8_000_000_000),  # 20MHz - 8GHz
            'supports': [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16],  # SGLFREQ, IFANALYSIS, DF, IFDF, FSCAN等
            'has_direction': True,
            'has_ifanalysis': True
        },
        'MS845': {
            'name': 'MS845 监测设备',
            'freq_range': (20_000_000, 8_000_000_000),  # 20MHz - 8GHz
            'supports': [0x10, 0x11, 0x15],
            'has_direction': False,
            'has_ifanalysis': True
        },
        'MS950': {
            'name': 'MS950 监测设备',
            'freq_range': (20_000_000, 18_000_000_000),  # 20MHz - 18GHz
            'supports': [0x10, 0x11, 0x15],
            'has_direction': False,
            'has_ifanalysis': True
        },
        'MS970': {
            'name': 'MS970 监测设备',
            'freq_range': (20_000_000, 3_000_000_000),  # 20MHz - 3GHz
            'supports': [0x10, 0x11, 0x12, 0x13, 0x15],
            'has_direction': True,
            'has_ifanalysis': True
        }
    }

    @classmethod
    def get_capabilities(cls, device_type: str) -> Dict[str, Any]:
        """获取设备能力"""
        return cls.DEVICES.get(device_type, cls.DEVICES['MS950'])

    @classmethod
    def validate_frequency(cls, device_type: str, frequency: int) -> Tuple[bool, str]:
        """验证频率是否在设备支持范围内"""
        caps = cls.get_capabilities(device_type)
        freq_min, freq_max = caps['freq_range']

        if frequency < freq_min or frequency > freq_max:
            return False, f"频率 {frequency} Hz 超出设备支持范围 ({freq_min/1e6:.0f}-{freq_max/1e6:.0f} MHz)"

        return True, ""

    @classmethod
    def validate_business_type(cls, device_type: str, business_type: int) -> Tuple[bool, str]:
        """验证业务类型是否被设备支持"""
        caps = cls.get_capabilities(device_type)

        if business_type not in caps['supports']:
            type_names = {
                0x10: 'SGLFREQ', 0x11: 'IFANALYSIS', 0x12: 'DF',
                0x13: 'IFDF', 0x14: 'MSCAN', 0x15: 'FSCAN', 0x16: 'DSCAN'
            }
            type_name = type_names.get(business_type, hex(business_type))
            return False, f"设备 {device_type} 不支持业务类型 {type_name} ({hex(business_type)})"

        return True, ""


class CommandParser:
    """命令解析器"""

    # 帧头解析
    HEADER_SIZE = 18
    HEADER_FORMAT = '!IQHBBH'

    # 业务数据头解析
    BUSINESS_HEADER_SIZE = 11
    BUSINESS_HEADER_FORMAT = '!B H I I'  # nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4)

    @classmethod
    def parse_frame(cls, data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析RMCPTP帧

        Args:
            data: 原始字节数据

        Returns:
            (帧头信息, 业务数据)

        Raises:
            ProtocolParseError: 协议解析错误
            ChecksumError: 校验和错误
        """
        if len(data) < cls.HEADER_SIZE:
            raise ProtocolParseError(f"数据长度不足: 需要{cls.HEADER_SIZE}字节, 实际{len(data)}字节")

        # 解析帧头
        header_data = data[:cls.HEADER_SIZE]
        try:
            dw_length, tm_stamp, n_version, n_data_type, n_flags = \
                struct.unpack('!IQHBB', header_data[:16])
            n_checksum = struct.unpack('!H', header_data[16:18])[0]
        except struct.error as e:
            raise ProtocolParseError(f"帧头解析失败: {e}")

        # 验证校验和
        calculated_checksum = cls._calculate_checksum(header_data[:-2])
        if calculated_checksum != n_checksum:
            raise ChecksumError(
                f"校验和错误: 计算值={hex(calculated_checksum)}, 实际值={hex(n_checksum)}"
            )

        header_info = {
            'dw_length': dw_length,
            'tm_stamp': tm_stamp,
            'n_version': n_version,
            'n_data_type': n_data_type,
            'n_flags': n_flags,
            'n_checksum': n_checksum
        }

        # 业务数据
        business_data = data[cls.HEADER_SIZE:cls.HEADER_SIZE + dw_length]

        return header_info, business_data

    @classmethod
    def _calculate_checksum(cls, data: bytes) -> int:
        """计算校验和"""
        if len(data) < 16:
            return 0

        length_val = struct.unpack('!I', data[0:4])[0]
        time_val = struct.unpack('!Q', data[4:12])[0]
        version_type_flags = struct.unpack('!HBB', data[12:16])[0]

        total = (length_val & 0xFFFF) + (length_val >> 16)
        total += (time_val & 0xFFFF) + (time_val >> 16)
        total += (version_type_flags & 0xFFFF) + (version_type_flags >> 16)

        for _ in range(2):
            total = (total >> 1) + (total & 0x7FFF)

        return (~total) & 0xFFFF

    @classmethod
    def parse_business_header(cls, data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析业务数据头

        Args:
            data: 业务数据字节

        Returns:
            (业务头信息, 剩余数据)
        """
        if len(data) < cls.BUSINESS_HEADER_SIZE:
            raise ProtocolParseError(
                f"业务数据头长度不足: 需要{cls.BUSINESS_HEADER_SIZE}字节, 实际{len(data)}字节"
            )

        n_bd_type, n_flags, n_arrays, n_offset = struct.unpack(
            cls.BUSINESS_HEADER_FORMAT, data[:cls.BUSINESS_HEADER_SIZE]
        )

        business_info = {
            'n_bd_type': n_bd_type,
            'n_flags': n_flags,
            'n_arrays': n_arrays,
            'n_offset': n_offset
        }

        return business_info, data[cls.BUSINESS_HEADER_SIZE:]


class MockDeviceServer:
    """虚拟设备TCP服务器"""

    def __init__(self, host: str = '127.0.0.1', port: int = 9000, scenario: str = 'normal', device_type: str = 'MS950'):
        self.host = host
        self.port = port
        self.scenario = scenario
        self.device_type = device_type
        self.server: Optional[asyncio.Server] = None
        self.running = False
        self.frame_builder = MockFrameBuilder()
        self.data_generator = DataGenerator(scenario=scenario)
        self.clients: set = set()
        self.command_parser = CommandParser()
        self.device_caps = DeviceCapabilities.get_capabilities(device_type)

    async def start(self):
        """启动TCP服务器"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        self.running = True
        logger.info(f"虚拟设备启动: {self.host}:{self.port}, 场景={self.scenario}, 设备={self.device_type} ({self.device_caps['name']})")

        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """停止TCP服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.running = False
        logger.info("虚拟设备已停止")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        addr = writer.get_extra_info('peername')
        logger.info(f"客户端连接: {addr}")
        self.clients.add(writer)

        try:
            while self.running:
                try:
                    # 读取18字节帧头
                    header_data = await asyncio.wait_for(
                        reader.read(18),
                        timeout=30.0
                    )

                    if not header_data:
                        break

                    # 解析帧头获取数据长度
                    try:
                        dw_length = struct.unpack('!I', header_data[:4])[0]
                    except:
                        continue

                    # 读取业务数据
                    payload = b''
                    if dw_length > 0 and dw_length < 10000:  # 安全限制
                        payload = await asyncio.wait_for(
                            reader.read(dw_length),
                            timeout=5.0
                        )

                    full_frame = header_data + payload
                    logger.debug(f"收到命令帧: {len(full_frame)} 字节")

                    # 解析命令
                    try:
                        header_info, business_data = self.command_parser.parse_frame(full_frame)
                        business_type = self._extract_business_type(business_data)

                        logger.info(
                            f"命令: type={hex(business_type)}, "
                            f"length={dw_length}, version={hex(header_info['n_version'])}"
                        )

                        # 生成响应
                        response_frame = await self.generate_response(
                            business_type, business_data
                        )

                        if response_frame:
                            writer.write(response_frame)
                            await writer.drain()
                            logger.debug(f"发送响应帧: {len(response_frame)} 字节")

                    except ChecksumError as e:
                        logger.warning(f"校验和错误: {e}")
                    except ProtocolParseError as e:
                        logger.warning(f"协议解析错误: {e}")

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"处理客户端数据异常: {e}")
                    break

        except Exception as e:
            logger.error(f"客户端异常: {e}")
        finally:
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            logger.info(f"客户端断开: {addr}")

    def _extract_business_type(self, business_data: bytes) -> int:
        """从业务数据中提取业务类型"""
        if len(business_data) >= 1:
            return business_data[0]
        return 0x10  # 默认SGLFREQ

    def _extract_frequency_from_command(self, business_data: bytes) -> int:
        """从命令数据中提取频率参数"""
        if len(business_data) < 12:
            return self.data_generator.scenario_config.get('frequency', 100_000_000)

        # 业务数据头后是频率字段
        # SGLFREQ: nBdType(1) + nArrays(4) + freq(8) = 13字节 (无nFlags/nOffset)
        try:
            freq = struct.unpack('!Q', business_data[5:13])[0]
            return freq
        except:
            return self.data_generator.scenario_config.get('frequency', 100_000_000)

    def _extract_span_from_command(self, business_data: bytes) -> int:
        """从命令数据中提取跨距参数 (IFANALYSIS, IFDF)"""
        if len(business_data) < 20:
            return 1_000_000
        try:
            # SGLFREQ: nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4) + freq(8) = 19字节后是span
            span = struct.unpack('!Q', business_data[17:25])[0]
            return span
        except:
            return 1_000_000

    def _validate_request(self, business_type: int, business_data: bytes) -> Tuple[bool, str, int]:
        """
        验证请求是否有效

        Returns:
            (是否有效, 错误信息, 错误码)
        """
        # 验证业务类型是否被设备支持
        valid, msg = DeviceCapabilities.validate_business_type(self.device_type, business_type)
        if not valid:
            return False, msg, ErrorCode.ERR_DEVICE_NOT_SUPPORTED

        # 提取频率并验证
        frequency = self._extract_frequency_from_command(business_data)
        valid, msg = DeviceCapabilities.validate_frequency(self.device_type, frequency)
        if not valid:
            return False, msg, ErrorCode.ERR_FREQ_OUT_OF_RANGE

        return True, "", ErrorCode.SUCCESS

    def _build_error_response(self, error_code: int, error_msg: str) -> bytes:
        """构建错误响应帧"""
        # 错误信息格式化
        error_data = f"ERR_{error_code:04X}: {error_msg}".encode('utf-8')

        # 业务数据头
        business_header = struct.pack(
            '!B H I I',
            0xFF,  # 错误标记
            0x0001,  # nFlags
            1,  # nArrays
            0  # nOffset
        )

        # 错误码 (4字节) + 错误信息
        error_payload = struct.pack('!I', error_code) + error_data

        return self.frame_builder.build_response_frame(
            business_type=0xFF,
            payload=business_header + error_payload
        )

    async def generate_response(self, business_type: int, business_data: bytes) -> bytes:
        """
        根据命令类型生成响应帧

        Args:
            business_type: 业务数据类型
            business_data: 业务数据

        Returns:
            响应帧
        """
        # 验证请求
        valid, error_msg, error_code = self._validate_request(business_type, business_data)
        if not valid:
            logger.warning(f"请求验证失败 [{self.device_type}]: {error_msg}")
            return self._build_error_response(error_code, error_msg)

        config = self.data_generator.scenario_config

        try:
            if business_type == 0x10:  # SGLFREQ - 单频测量
                frequency = self._extract_frequency_from_command(business_data)
                amplitude = config.get('amplitude', -60) + np.random.normal(0, 1)
                itu_value = amplitude
                return self.frame_builder.build_sglfreq_frame(
                    frequency, amplitude, itu_value
                )

            elif business_type == 0x12:  # DF - 单频测向
                frequency = self._extract_frequency_from_command(business_data)
                direction, amplitude = self.data_generator.generate_direction_data()
                return self.frame_builder.build_direction_frame(
                    direction=direction,
                    amplitude=amplitude,
                    quality=0.95
                )

            elif business_type == 0x13:  # IFDF - 中频测向
                frequency = self._extract_frequency_from_command(business_data)
                direction, amplitude = self.data_generator.generate_direction_data()
                return self.frame_builder.build_direction_frame(
                    direction=direction,
                    amplitude=amplitude
                )

            elif business_type == 0x15:  # FSCAN - 频段扫描
                spectrum_data = self.data_generator.generate_spectrum_data()
                return self.frame_builder.build_response_frame(
                    business_type=0x15,
                    payload=spectrum_data
                )

            elif business_type == 0x11:  # IFANALYSIS - 中频分析
                frequency = self._extract_frequency_from_command(business_data)
                amplitude = config.get('amplitude', -60) + np.random.normal(0, 2)
                return self.frame_builder.build_response_frame(
                    business_type=0x11,
                    payload=self._build_ifanalysis_data(frequency, amplitude)
                )

            else:
                logger.warning(f"未知的业务类型: {hex(business_type)}")
                return self._build_error_response(
                    ErrorCode.ERR_DEVICE_NOT_SUPPORTED,
                    f"不支持的业务类型 {hex(business_type)}"
                )
        except Exception as e:
            logger.error(f"生成响应失败: {e}")
            return self._build_error_response(
                ErrorCode.ERR_DEVICE_PARAM_ERROR,
                f"处理失败: {str(e)}"
            )

    def _build_ifanalysis_data(self, frequency: int, amplitude: float) -> bytes:
        """构建中频分析响应数据"""
        import struct
        # IFANALYSIS: nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4) + freq(8) + level(2)
        header = struct.pack(
            '!B H I I',
            0x11,  # nBdType
            0x01,  # nFlags
            100,   # nArrays (频谱点数)
            0      # nOffset
        )
        fixed = struct.pack('!Q h', frequency, int(amplitude * 100))

        # 频谱数据 (100个点)
        dynamic = b''
        for i in range(100):
            level = amplitude + np.random.normal(0, 3)
            dynamic += struct.pack('!h', int(level * 100))

        return header + fixed + dynamic

    def set_scenario(self, scenario: str):
        """切换场景"""
        self.scenario = scenario
        self.data_generator.set_scenario(scenario)
        logger.info(f"场景切换: {scenario}")

    def get_status(self) -> Dict[str, Any]:
        """获取设备状态"""
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'scenario': self.scenario,
            'clients': len(self.clients)
        }


# 导入numpy用于随机数
import numpy as np
