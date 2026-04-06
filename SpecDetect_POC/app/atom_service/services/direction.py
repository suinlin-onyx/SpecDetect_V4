"""测向服务

实现单频测向、中频测向等测向业务
"""
import struct
from typing import Dict, Any
from ..device_client import DeviceClient
from ..protocol_builder import RMCPTPBuilder
from utils.logger import get_logger

logger = get_logger('atom.direction')


class DirectionService:
    """测向服务"""

    def __init__(self, device_client: DeviceClient):
        self.device_client = device_client
        self.builder = RMCPTPBuilder()

    async def start_df(self, frequency: int, bandwidth: int = 120000) -> Dict[str, Any]:
        """
        开始单频测向 (DF 0x12)

        Args:
            frequency: 频率(Hz)
            bandwidth: 带宽(Hz)

        Returns:
            测向结果
        """
        logger.info(f"开始单频测向: frequency={frequency}Hz, bandwidth={bandwidth}Hz")

        # 构建测向命令 DF (0x12)
        # 业务数据格式: nBdType(1) + freq(8)
        business_data = struct.pack('!B Q', 0x12, frequency)
        frame = self.builder.build_command_frame(business_type=0x12, params=business_data)

        header_info, payload, raw_frame = await self.device_client.send_and_receive(frame)

        # 解析测向结果
        result = self._parse_df_response(payload)
        result.update({
            'success': True,
            'frequency': frequency,
            'bandwidth': bandwidth,
            'data_type': header_info['n_data_type']
        })

        return result

    async def start_ifdf(self, frequency: int, span: int = 1_000_000,
                        ifbw: int = 100000) -> Dict[str, Any]:
        """
        开始中频测向 (IFDF 0x13)

        Args:
            frequency: 中心频率(Hz)
            span: 跨距(Hz)
            ifbw: 中频带宽(Hz)

        Returns:
            测向结果
        """
        logger.info(f"开始中频测向: frequency={frequency}Hz, span={span}Hz, ifbw={ifbw}Hz")

        # 构建中频测向命令 IFDF (0x13)
        frame = self.builder.build_ifdf_command(frequency, span, ifbw)

        header_info, payload, raw_frame = await self.device_client.send_and_receive(frame)

        # 解析测向结果
        result = self._parse_ifdf_response(payload)
        result.update({
            'success': True,
            'frequency': frequency,
            'span': span,
            'ifbw': ifbw,
            'data_type': header_info['n_data_type']
        })

        return result

    async def start_wbfft(self, start_freq: int, end_freq: int) -> Dict[str, Any]:
        """
        开始宽带FFT

        Args:
            start_freq: 起始频率(Hz)
            end_freq: 终止频率(Hz)

        Returns:
            FFT结果
        """
        logger.info(f"开始宽带FFT: {start_freq}Hz - {end_freq}Hz")

        # WBFFT 命令格式: nBdType(1) + startFreq(8) + endFreq(8)
        business_data = struct.pack('!B Q Q', 0x1C, start_freq, end_freq)
        frame = self.builder.build_command_frame(business_type=0x1C, params=business_data)

        header_info, payload, raw_frame = await self.device_client.send_and_receive(frame)

        return {
            'success': True,
            'start_freq': start_freq,
            'end_freq': end_freq,
            'data_type': header_info['n_data_type']
        }

    def _parse_df_response(self, payload: bytes) -> Dict[str, Any]:
        """解析单频测向响应"""
        result = {
            'level': None,
            'df_level': None,
            'quality': None,
            'azimuth': None,
            'elevation': None,
            'compass': None
        }

        if not payload or len(payload) < 11:
            return result

        try:
            # DF响应数据格式:
            # nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4) + Level(2) + DfLevel(2) +
            # Qulity(4) + Azumith(4) + Elevation(4) + compass(4) = 27字节
            if len(payload) >= 27:
                n_arrays = struct.unpack('!I', payload[1:5])[0]

                if n_arrays > 0:
                    # 固定部分从偏移11开始
                    fixed_data = payload[11:31]
                    if len(fixed_data) >= 20:
                        level, df_level, quality, azimuth, elevation, compass = struct.unpack(
                            '!h h f f f f', fixed_data
                        )
                        result['level'] = level / 100.0
                        result['df_level'] = df_level / 100.0
                        result['quality'] = quality
                        result['azimuth'] = azimuth
                        result['elevation'] = elevation
                        result['compass'] = compass

        except Exception as e:
            logger.warning(f"解析DF响应失败: {e}")

        return result

    def _parse_ifdf_response(self, payload: bytes) -> Dict[str, Any]:
        """解析中频测向响应"""
        result = {
            'level': None,
            'df_level': None,
            'quality': None,
            'azimuth': None,
            'elevation': None,
            'compass': None,
            'spectrum': []
        }

        if not payload or len(payload) < 11:
            return result

        try:
            if len(payload) >= 11:
                n_arrays = struct.unpack('!I', payload[1:5])[0]

                # 固定部分
                if len(payload) >= 31:
                    fixed_data = payload[11:31]
                    if len(fixed_data) >= 20:
                        level, df_level, quality, azimuth, elevation, compass = struct.unpack(
                            '!h h f f f f', fixed_data
                        )
                        result['level'] = level / 100.0
                        result['df_level'] = df_level / 100.0
                        result['quality'] = quality
                        result['azimuth'] = azimuth
                        result['elevation'] = elevation
                        result['compass'] = compass

                # 频谱数据 (如果有)
                offset = 31
                for i in range(min(n_arrays, 500)):
                    if offset + 2 <= len(payload):
                        level = struct.unpack('!h', payload[offset:offset+2])[0]
                        result['spectrum'].append(level / 100.0)
                        offset += 2

        except Exception as e:
            logger.warning(f"解析IFDF响应失败: {e}")

        return result
