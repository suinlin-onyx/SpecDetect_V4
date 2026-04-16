"""
streamsrc 18012 频谱数据解析器

根据pcap抓包分析和GWJ004-2015文档:

帧类型:
- 65 bytes:   注册帧 (会话/通道建立，对应GWJ004 STC通道标识)
- 1086 bytes: 频谱帧 (512点dBm数据，对应GWJ004数据传输)

GWJ004-2015 5.2节定义:
- STC (Synchronous Transfer Code): 4字节UINT32，唯一标识一路数据传输通路
- streamsrc的0xEEEEEEEE同步头对应GWJ004的STC概念

转换公式:
- streamsrc_dBm = raw_value (直接使用)
- rmcp_dBm = raw_value / 10.0
"""

import struct
from typing import List, Optional, Tuple


class StreamsrcParser:
    """streamsrc 18012 频谱数据解析器"""

    # 帧类型
    FRAME_TYPE_SPECTRUM = 1086  # 频谱帧
    FRAME_TYPE_REGISTRATION = 65  # 注册帧(包含UUID，无频谱数据)

    # 频谱帧偏移量
    SPECTRUM_OFFSET = 48  # 频谱数据起始偏移
    METADATA_COUNT = 7    # 元数据int16数量
    SPECTRUM_COUNT = 512  # 频谱点数

    def __init__(self):
        self.frame_count = 0

    def is_spectrum_frame(self, data: bytes) -> bool:
        """判断是否为频谱帧"""
        return len(data) == self.FRAME_TYPE_SPECTRUM

    def is_registration_frame(self, data: bytes) -> bool:
        """判断是否为注册帧 (会话建立)"""
        return len(data) == self.FRAME_TYPE_REGISTRATION

    def parse_registration_frame(self, data: bytes) -> Optional[dict]:
        """
        解析注册帧 (65字节)

        GWJ004-2015 5.2: STC (Synchronous Transfer Code) 唯一标识通道
        streamsrc注册帧建立会话，Atom收到后才会发送频谱数据

        返回:
            dict: {
                'sync': int,      # 0xEEEEEEEE
                'header': bytes,  # 24字节头部
                'metadata': list, # 5个int16元数据 [256, 1441, 0, 0, -32768]
                'spectrum_sample': list  # 13个int16频谱样本
            }
        """
        if not self.is_registration_frame(data):
            return None

        sync = struct.unpack('<I', data[0:4])[0]
        header = data[4:28]
        vals = struct.unpack('<18h', data[28:64])

        return {
            'sync': sync,
            'header': header,
            'metadata': list(vals[0:5]),
            'spectrum_sample': list(vals[5:18])
        }

    def get_frame_type_name(self, data: bytes) -> str:
        """获取帧类型名称"""
        if self.is_registration_frame(data):
            return "REGISTRATION (65B)"
        elif self.is_spectrum_frame(data):
            return "SPECTRUM (1086B)"
        else:
            return f"UNKNOWN ({len(data)}B)"

    def parse_metadata(self, data: bytes) -> Optional[List[int]]:
        """
        解析元数据

        返回:
            List[int]: 7个元数据值，或None(非频谱帧)
        """
        if not self.is_spectrum_frame(data):
            return None

        count = (len(data) - 48) // 2
        vals = struct.unpack('<' + 'h' * count, data[48:])
        return list(vals[:7])

    def parse_spectrum(self, data: bytes) -> Optional[List[int]]:
        """
        从 streamsrc 1086字节帧提取512点频谱数据

        参数:
            data: 原始字节数据 (1086 bytes)

        返回:
            List[int]: 512个dBm值，或None(非频谱帧)
        """
        if not self.is_spectrum_frame(data):
            return None

        count = (len(data) - 48) // 2
        vals = struct.unpack('<' + 'h' * count, data[48:])
        spectrum = list(vals[7:7+512])

        self.frame_count += 1
        return spectrum

    def parse_frame_hex(self, frame_hex: str) -> Optional[List[int]]:
        """
        从十六进制字符串解析频谱数据

        参数:
            frame_hex: 十六进制字符串

        返回:
            List[int]: 512个dBm值，或None(非频谱帧)
        """
        data = bytes.fromhex(frame_hex)
        return self.parse_spectrum(data)


def parse_streamsrc_spectrum(data: bytes) -> List[int]:
    """
    从 streamsrc 1086字节帧提取512点频谱数据

    参数:
        data: 原始字节数据 (1086 bytes)

    返回:
        List[int]: 512个dBm值

    示例:
        >>> data = bytes.fromhex("eeeeeeee01001568...")
        >>> spectrum = parse_streamsrc_spectrum(data)
        >>> print(f"512 points, range {min(spectrum)} to {max(spectrum)} dBm")
    """
    if len(data) < 52:
        return []

    count = (len(data) - 48) // 2
    vals = struct.unpack('<' + 'h' * count, data[48:])
    return list(vals[7:7+512])


def streamsrc_to_dbm(raw_value: int) -> float:
    """
    streamsrc原始值转换为dBm

    streamsrc直接存储dBm整数，无需转换

    参数:
        raw_value: streamsrc原始值

    返回:
        float: dBm值
    """
    return float(raw_value)


def rmcp_to_dbm(raw_value: int) -> float:
    """
    rmcp原始值转换为dBm

    rmcp存储的是dBm×10，需要除以10

    参数:
        raw_value: rmcp原始值

    返回:
        float: dBm值
    """
    return raw_value / 10.0


# 便捷函数
def parse_spectrum_from_hex(frame_hex: str) -> Optional[List[int]]:
    """
    从十六进制字符串解析streamsrc频谱数据

    参数:
        frame_hex: 帧的十六进制字符串

    返回:
        List[int]: 512个dBm值，或None
    """
    parser = StreamsrcParser()
    return parser.parse_frame_hex(frame_hex)


if __name__ == "__main__":
    # 示例: 解析已知的streamsrc帧
    example_hex = (
        "eeeeeeee01001568e069ea0704100c2734b70026040000000c2104000001a105"
        "00000000000080e854a04100000030c5daa141000000000050c34600020000"
        "cbffbcffbaffaaffc7ffabffb9ffc5ffccffafffbbffb4ff9bffcdffc4ffc1"
        "ffd2ffbcffb8ffb9ffb0ffbeffd6ffcaffbbffbaffc5ffa5ffbcffc2ffc2"
        "ffd9ffbfffccffc4ffc7ffb2ffb2ffc1ffbeffc5ffcdffc6ffc4ffbaffbcfc"
        "..."
    )

    # 注意: 完整帧见 streamsrc_rmcp_conversion.md
    print("streamsrc 18012 频谱解析器")
    print("=" * 40)
    print("使用说明:")
    print("  from streamsrc_parser import StreamsrcParser")
    print("  parser = StreamsrcParser()")
    print("  spectrum = parser.parse_spectrum(frame_data)")
    print()
    print("转换公式:")
    print("  streamsrc_dBm = raw_value (直接使用)")
    print("  rmcp_dBm = raw_value / 10.0")
