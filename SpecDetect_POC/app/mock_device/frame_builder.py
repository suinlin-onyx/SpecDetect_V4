"""Mock设备RMCPTP帧构建器

使用RMCPTP v2.0协议规范
"""
import struct
import time
from utils.logger import get_logger

logger = get_logger('mock.frame')


class MockFrameBuilder:
    """Mock设备帧构建器"""

    # 帧头结构 (18字节)
    HEADER_FORMAT = '!IQHBBH'
    HEADER_SIZE = 18

    def __init__(self, version: int = 0x0007):
        self.version = version

    def build_response_frame(self, business_type: int, payload: bytes,
                             data_type: int = 0x00) -> bytes:
        """
        构建响应帧

        Args:
            business_type: 业务数据类型 (如0x10=SGLFREQ)
            payload: 业务数据载荷
            data_type: 数据类型 (默认0x00=监测业务数据)

        Returns:
            完整的响应帧
        """
        timestamp = self._get_current_filetime()
        # payload_length 需要 +1 以包含 business_type 字节
        payload_length = len(payload) + 1

        # 先构建不含校验和的帧头（16字节）
        header_without_checksum = struct.pack(
            '!IQHBB',  # dwLength(4) + tmStamp(8) + nVersion(2) + nDataType(1) + nFlags(1)
            payload_length,      # dwLength
            timestamp,           # tmStamp
            self.version,        # nVersion
            data_type,           # nDataType
            0x00                 # nFlags
        )

        # 计算校验和
        checksum = self._calculate_checksum(header_without_checksum)

        # 添加校验和，构建完整18字节帧头
        header = header_without_checksum + struct.pack('!H', checksum)

        # 业务数据：业务类型 + 载荷
        business_data = struct.pack('!B', business_type) + payload

        return header + business_data

    def _calculate_checksum(self, data: bytes) -> int:
        """
        计算校验和

        RMCPTP v2.0 规范:
        1. 以无符号短整型形式读出时间、长度累加
        2. 对结果作两次折半移位相加处理
        3. 取反码得到校验和
        """
        if len(data) < 16:
            return 0

        # 提取需要校验的字段
        # dwLength (4字节) + tmStamp (8字节) + nVersion (2字节) + nDataType (1字节) + nFlags (1字节) = 16字节
        length_val = struct.unpack('!I', data[0:4])[0]
        time_val = struct.unpack('!Q', data[4:12])[0]
        version_type_flags = struct.unpack('!HBB', data[12:16])[0]

        # 累加
        total = (length_val & 0xFFFF) + (length_val >> 16)
        total += (time_val & 0xFFFF) + (time_val >> 16)
        total += (version_type_flags & 0xFFFF) + (version_type_flags >> 16)

        # 两次折半移位相加
        for _ in range(2):
            total = (total >> 1) + (total & 0x7FFF)

        # 取反码
        checksum = (~total) & 0xFFFF
        return checksum

    def _get_current_filetime(self) -> int:
        """获取当前FILETIME时间戳"""
        unix_timestamp = time.time()
        FILETIME_EPOCH = 116444736000000000
        filetime = int(unix_timestamp * 10000000) + FILETIME_EPOCH
        return filetime

    def build_spectrum_frame(self, frequencies: list, amplitudes: list) -> bytes:
        """
        构建频谱数据帧

        Args:
            frequencies: 频率列表(Hz)
            amplitudes: 幅度列表(dBm)

        Returns:
            频谱数据帧
        """
        spectrum_data = self._pack_spectrum_data(frequencies, amplitudes)
        return self.build_response_frame(
            business_type=0x15,  # FSCAN
            payload=spectrum_data
        )

    def _pack_spectrum_data(self, frequencies: list, amplitudes: list) -> bytes:
        """打包频谱数据"""
        # FSCAN数据格式
        n_arrays = len(frequencies)

        header = struct.pack(
            '!B H H I',
            0x15,               # nBdType (FSCAN)
            0x01,               # nFlags (基础业务数据)
            n_arrays,           # nArrays
            0                   # nOffset
        )

        dynamic = b''
        for freq, amp in zip(frequencies, amplitudes):
            # 电平值 * 100
            level_scaled = int(amp * 100)
            dynamic += struct.pack('!h', level_scaled)

        return header + dynamic

    def build_direction_frame(self, direction: float, amplitude: float,
                              quality: float = 0.95) -> bytes:
        """
        构建测向数据帧

        Args:
            direction: 方向角度(度)
            amplitude: 幅度(dBm)
            quality: 测向质量

        Returns:
            测向数据帧
        """
        # DF数据格式
        header = struct.pack(
            '!B H H I',
            0x12,               # nBdType (DF)
            0x01,               # nFlags
            1,                  # nArrays
            0                   # nOffset
        )

        fixed = struct.pack(
            '!h h f f f f',
            int(amplitude * 100),  # Level
            int(amplitude * 100),  # DfLevel
            quality,               # Qulity
            direction,              # Azumith
            0.0,                   # Elevation
            0.0                    # compass
        )

        return self.build_response_frame(
            business_type=0x12,  # DF
            payload=header + fixed
        )

    def build_sglfreq_frame(self, frequency: int, amplitude: float,
                           itu_value: float = None) -> bytes:
        """
        构建单频测量数据帧

        Args:
            frequency: 频率(Hz)
            amplitude: 幅度(dBm)
            itu_value: ITU测量值

        Returns:
            单频测量数据帧
        """
        if itu_value is None:
            itu_value = amplitude

        header = struct.pack(
            '!B H I I',
            0x10,               # nBdType (SGLFREQ)
            0x01,               # nFlags
            1,                  # nArrays (4字节)
            0                   # nOffset
        )

        freq_part = struct.pack('!Q', frequency)

        dynamic = struct.pack(
            '!f h h',
            itu_value,                    # value
            0,                            # occ
            int(-100 * 100)              # thr (门限)
        )

        return self.build_response_frame(
            business_type=0x10,  # SGLFREQ
            payload=header + freq_part + dynamic
        )
