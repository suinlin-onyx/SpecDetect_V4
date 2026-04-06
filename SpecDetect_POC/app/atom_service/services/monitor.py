"""监测服务

实现单频测量、频段扫描等监测业务
"""
import struct
from typing import Dict, Any, Optional
from ..device_client import DeviceClient
from ..protocol_builder import RMCPTPBuilder
from utils.logger import get_logger

logger = get_logger('atom.monitor')


class MonitorService:
    """监测服务"""

    def __init__(self, device_client: DeviceClient):
        self.device_client = device_client
        self.builder = RMCPTPBuilder()

    async def start_sglfreq(self, frequency: int, bandwidth: int = 120000,
                          antenna: str = "default") -> Dict[str, Any]:
        """
        开始单频测量

        Args:
            frequency: 频率(Hz)
            bandwidth: 带宽(Hz)
            antenna: 天线名称

        Returns:
            测量结果
        """
        logger.info(f"开始单频测量: frequency={frequency}Hz, bandwidth={bandwidth}Hz")

        # 构建命令帧
        frame = self.builder.build_sglfreq_command(frequency, antenna)

        # 发送并接收响应
        header_info, payload, raw_frame = await self.device_client.send_and_receive(frame)

        # 解析响应数据
        result = self._parse_sglfreq_response(payload)
        result.update({
            'success': True,
            'frequency': frequency,
            'bandwidth': bandwidth,
            'data_type': header_info['n_data_type'],
            'timestamp': header_info['tm_stamp']
        })

        return result

    async def start_fscan(self, start_freq: int, end_freq: int,
                         step: int = 1000000) -> Dict[str, Any]:
        """
        开始频段扫描

        Args:
            start_freq: 起始频率(Hz)
            end_freq: 终止频率(Hz)
            step: 频率步进(Hz)

        Returns:
            扫描结果
        """
        logger.info(f"开始频段扫描: {start_freq}Hz - {end_freq}Hz, step={step}Hz")

        # 构建频段扫描命令
        frame = self.builder.build_fscan_command(start_freq, end_freq, step)

        # 发送并接收响应
        header_info, payload, raw_frame = await self.device_client.send_and_receive(frame)

        # 解析响应数据
        result = self._parse_fscan_response(payload)
        result.update({
            'success': True,
            'start_freq': start_freq,
            'end_freq': end_freq,
            'step': step,
            'data_type': header_info['n_data_type']
        })

        return result

    async def start_ifanalysis(self, frequency: int, span: int = 1_000_000,
                               ifbw: int = 100000) -> Dict[str, Any]:
        """
        开始中频分析

        Args:
            frequency: 中心频率(Hz)
            span: 跨距(Hz)
            ifbw: 中频带宽(Hz)

        Returns:
            分析结果
        """
        logger.info(f"开始中频分析: frequency={frequency}Hz, span={span}Hz")

        # 构建中频分析命令
        frame = self.builder.build_ifanalysis_command(frequency, span, ifbw)

        # 发送并接收响应
        header_info, payload, raw_frame = await self.device_client.send_and_receive(frame)

        result = self._parse_ifanalysis_response(payload)
        result.update({
            'success': True,
            'frequency': frequency,
            'span': span,
            'ifbw': ifbw
        })

        return result

    def _parse_sglfreq_response(self, payload: bytes) -> Dict[str, Any]:
        """解析单频测量响应"""
        result = {
            'frequency': 0,
            'amplitude': None,
            'itu_values': []
        }

        if not payload or len(payload) < 12:
            return result

        try:
            # 响应数据格式: business_type(1) + business_header(11) + freq(8) + dynamic(8) = 28字节
            # 跳过 business_type (1字节)
            data_offset = 1

            # 提取频率 (business_header之后是freq)
            # business_header: nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4) = 11字节
            if len(payload) >= data_offset + 19:
                freq = struct.unpack('!Q', payload[data_offset + 11:data_offset + 19])[0]
                result['frequency'] = freq

            # 解析ITU数据
            # business_header之后: freq(8) + itu_value(4) + occ(2) + thr(2) = 16字节
            if len(payload) >= data_offset + 27:
                itu_offset = data_offset + 19  # after header(11) + freq(8)
                n_arrays = 1  # 默认1个ITU测量

                itu_size = 8  # value(4) + occ(2) + thr(2)
                for i in range(min(n_arrays, 10)):
                    if itu_offset + itu_size <= len(payload):
                        value, occ, thr = struct.unpack('!f hh', payload[itu_offset:itu_offset + itu_size])
                        result['itu_values'].append({
                            'value': value,
                            'occupancy': occ / 100.0,
                            'threshold': thr / 100.0
                        })
                        itu_offset += itu_size

                # 如果没有解析到ITU值，尝试直接获取幅度
                if not result['itu_values'] and len(payload) >= data_offset + 23:
                    amplitude = struct.unpack('!f', payload[data_offset + 19:data_offset + 23])[0]
                    result['amplitude'] = amplitude

        except Exception as e:
            logger.warning(f"解析SGLFREQ响应失败: {e}")

        return result

    def _parse_fscan_response(self, payload: bytes) -> Dict[str, Any]:
        """解析频段扫描响应"""
        result = {
            'levels': [],
            'point_count': 0
        }

        if not payload or len(payload) < 12:
            return result

        try:
            # 跳过 business_type 字节
            data_offset = 1

            # 业务数据头: nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4) = 11字节
            if len(payload) >= data_offset + 11:
                n_bd_type = payload[data_offset]
                n_arrays = struct.unpack('!I', payload[data_offset + 3:data_offset + 7])[0]
                result['point_count'] = n_arrays

                # 动态数据是short数组 (电平值 * 100)
                dynamic_offset = data_offset + 11
                for i in range(min(n_arrays, 500)):  # 最多500个点
                    if dynamic_offset + 2 <= len(payload):
                        level = struct.unpack('!h', payload[dynamic_offset:dynamic_offset+2])[0]
                        result['levels'].append(level / 100.0)
                        dynamic_offset += 2

        except Exception as e:
            logger.warning(f"解析FSCAN响应失败: {e}")

        return result

    def _parse_ifanalysis_response(self, payload: bytes) -> Dict[str, Any]:
        """解析中频分析响应"""
        result = {
            'frequency': 0,
            'center_level': None,
            'spectrum': []
        }

        if not payload or len(payload) < 16:
            return result

        try:
            # 跳过 business_type 字节
            data_offset = 1

            if len(payload) >= data_offset + 15:
                n_arrays = struct.unpack('!I', payload[data_offset + 3:data_offset + 7])[0]

                # 固定部分后是freq(8) + level(2)
                if len(payload) >= data_offset + 21:
                    freq, center_level = struct.unpack('!Q h', payload[data_offset + 11:data_offset + 21])
                    result['frequency'] = freq
                    result['center_level'] = center_level / 100.0

                # 频谱数据
                dynamic_offset = data_offset + 21
                for i in range(min(n_arrays, 500)):
                    if dynamic_offset + 2 <= len(payload):
                        level = struct.unpack('!h', payload[dynamic_offset:dynamic_offset+2])[0]
                        result['spectrum'].append(level / 100.0)
                        dynamic_offset += 2

        except Exception as e:
            logger.warning(f"解析IFANALYSIS响应失败: {e}")

        return result
