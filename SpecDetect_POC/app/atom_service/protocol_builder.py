"""RMCPTP协议构建器

RMCPTP v2.0 协议规范
帧头结构（18字节）：
- dwLength: 4字节 unsigned int - 报文长度
- tmStamp: 8字节 FILETIME - 报文产生时间
- nVersion: 2字节 unsigned short - 版本号 (0x0007)
- nDataType: 1字节 unsigned char - 数据类型
- nFlags: 1字节 unsigned char - 标志位
- nCheckSum: 2字节 unsigned short - 头校验和
"""
import struct
import time
from typing import Optional
from utils.exceptions import ProtocolBuildError
from utils.logger import get_logger

logger = get_logger('atom.builder')


class RMCPTPBuilder:
    """RMCPTP协议构建器"""

    # 帧头结构 (18字节):
    # dwLength: 4字节, tmStamp: 8字节, nVersion: 2字节,
    # nDataType: 1字节, nFlags: 1字节, nCheckSum: 2字节
    HEADER_FORMAT = '!IQHBBH'  # 网络字节序
    HEADER_SIZE = 18

    def __init__(self, version: int = 0x0007):
        self.version = version

    def build_frame(self, data_type: int, payload: bytes,
                    flags: int = 0, timestamp: Optional[int] = None) -> bytes:
        """
        构建RMCPTP帧

        Args:
            data_type: 数据类型
            payload: 业务数据载荷
            flags: 标志位
            timestamp: 时间戳（默认当前时间）

        Returns:
            完整的帧字节数据
        """
        if timestamp is None:
            timestamp = self._get_current_filetime()

        payload_length = len(payload)

        # 先构建不含校验和的帧头（16字节）
        header_without_checksum = struct.pack(
            '!IQHBB',  # dwLength(4) + tmStamp(8) + nVersion(2) + nDataType(1) + nFlags(1)
            payload_length,      # dwLength
            timestamp,           # tmStamp
            self.version,        # nVersion
            data_type,           # nDataType
            flags                # nFlags
        )

        # 计算校验和
        checksum = self._calculate_checksum(header_without_checksum)

        # 添加校验和，构建完整18字节帧头
        frame = header_without_checksum + struct.pack('!H', checksum)

        # 组装完整帧
        frame = frame + payload

        logger.debug(
            f"构建帧: type={hex(data_type)}, length={payload_length}, "
            f"total={len(frame)}, flags={hex(flags)}"
        )
        return frame

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
        """
        获取当前FILETIME时间戳

        FILETIME是Windows文件时间格式，从1601-01-01开始计算
        返回值是100纳秒间隔数
        """
        # 获取Unix时间戳（秒）
        unix_timestamp = time.time()

        # FILETIME从1601-01-01开始，需要计算差值
        # 1601-01-01到1970-01-01的秒数
        FILETIME_EPOCH = 116444736000000000  # 100纳秒间隔

        # Unix时间戳转FILETIME
        filetime = int(unix_timestamp * 10000000) + FILETIME_EPOCH

        return filetime

    def build_command_frame(self, business_type: int, params: bytes) -> bytes:
        """
        构建命令帧

        Args:
            business_type: 业务数据类型 (如0x10=SGLFREQ)
            params: 命令参数字节

        Returns:
            命令帧字节数据
        """
        return self.build_frame(data_type=0x00, payload=params)

    def build_sglfreq_command(self, frequency: int, antenna: str = "default") -> bytes:
        """
        构建单频测量命令 SGLFREQ (0x10)

        命令头格式:
        - nBdType: 1字节 - 业务类型 = 0x10
        - nArrays: 4字节 - ITU测量数据个数
        - freq: 8字节 - 固定频率
        - szAntenna: 64字节 - 天线名

        Args:
            frequency: 频率(Hz)
            antenna: 天线名称

        Returns:
            命令帧字节数据
        """
        # 构建业务数据头
        n_arrays = 1  # 默认1个ITU测量
        antenna_bytes = antenna.encode('utf-8')[:63] + b'\x00'  # 截断并补零

        header = struct.pack(
            '!B I Q',
            0x10,        # nBdType
            n_arrays,    # nArrays
            frequency    # freq
        )

        # 填充天线名到64字节
        antenna_padded = antenna_bytes.ljust(64, b'\x00')

        payload = header + antenna_padded
        return self.build_command_frame(business_type=0x10, params=payload)

    def build_fscan_command(self, start_freq: int, end_freq: int, step: int) -> bytes:
        """
        构建频段扫描命令 FSCAN (0x15)

        命令格式:
        - nBdType: 1字节 - 0x15
        - nArrays: 4字节 - 扫描段数
        动态部分:
        - startfreq: 8字节 - 开始频率
        - endfreq: 8字节 - 结束频率
        - step: 8字节 - 步长频率
        - nPoints: 4字节 - 本段点数

        Args:
            start_freq: 起始频率(Hz)
            end_freq: 终止频率(Hz)
            step: 步进(Hz)

        Returns:
            命令帧字节数据
        """
        n_arrays = 1
        n_points = max(100, (end_freq - start_freq) // step)

        header = struct.pack('!B I', 0x15, n_arrays)

        segment = struct.pack(
            '! Q Q Q I',
            start_freq,  # startfreq
            end_freq,    # endfreq
            step,        # step
            n_points     # nPoints
        )

        payload = header + segment
        return self.build_command_frame(business_type=0x15, params=payload)

    def build_ifdf_command(self, frequency: int, span: int, ifbw: int) -> bytes:
        """
        构建中频测向命令 IFDF (0x13)

        Args:
            frequency: 中心频率(Hz)
            span: 跨距(Hz)
            ifbw: 中频带宽(Hz)

        Returns:
            命令帧字节数据
        """
        header = struct.pack(
            '!B I Q Q Q',
            0x13,        # nBdType
            0,           # nArrays (动态数组数目)
            frequency,   # freq
            span,        # span
            ifbw         # Ifbw
        )

        return self.build_command_frame(business_type=0x13, params=header)

    def build_ifanalysis_command(self, frequency: int, span: int, ifbw: int) -> bytes:
        """
        构建中频分析命令 IFANALYSIS (0x11)

        命令格式:
        - nBdType: 1字节 - 0x11
        - nArrays: 4字节 - 动态数组数目
        - freq: 8字节 - 中频分析设定频率
        - span: 8字节 - 测量跨距
        - Ifbw: 8字节 - 中频带宽

        Args:
            frequency: 中心频率(Hz)
            span: 跨距(Hz)
            ifbw: 中频带宽(Hz)

        Returns:
            命令帧字节数据
        """
        header = struct.pack(
            '!B I Q Q Q',
            0x11,        # nBdType (IFANALYSIS)
            0,           # nArrays
            frequency,   # freq
            span,        # span
            ifbw         # Ifbw
        )

        return self.build_command_frame(business_type=0x11, params=header)

    def build_mscan_command(self, frequency: int, ifbw: int = 120000) -> bytes:
        """
        构建多信道扫描命令 MSCAN (0x14)

        命令格式:
        - nBdType: 1字节 - 0x14
        - nArrays: 4字节 - 扫描段数
        动态部分:
        - startfreq: 8字节 - 开始频率
        - endfreq: 8字节 - 结束频率
        - step: 8字节 - 步长频率
        - nPoints: 4字节 - 本段点数

        Args:
            frequency: 中心频率(Hz)
            ifbw: 中频带宽(Hz)

        Returns:
            命令帧字节数据
        """
        n_arrays = 1
        # 使用frequency作为中心点，计算起止频率
        start_freq = frequency - ifbw // 2
        end_freq = frequency + ifbw // 2
        step = max(10000, ifbw // 100)
        n_points = max(100, (end_freq - start_freq) // step)

        header = struct.pack('!B I', 0x14, n_arrays)

        segment = struct.pack(
            '! Q Q Q I',
            start_freq,  # startfreq
            end_freq,    # endfreq
            step,        # step
            n_points     # nPoints
        )

        payload = header + segment
        return self.build_command_frame(business_type=0x14, params=payload)

    def build_pscan_command(self, start_freq: int, end_freq: int, step: int) -> bytes:
        """
        构建频谱扫描命令 PSCAN (0x17)

        命令格式:
        - nBdType: 1字节 - 0x17
        - nArrays: 4字节 - 扫描段数
        动态部分:
        - startfreq: 8字节 - 开始频率
        - endfreq: 8字节 - 结束频率
        - step: 8字节 - 步长频率
        - nPoints: 4字节 - 本段点数

        Args:
            start_freq: 起始频率(Hz)
            end_freq: 终止频率(Hz)
            step: 步进(Hz)

        Returns:
            命令帧字节数据
        """
        n_arrays = 1
        n_points = max(100, (end_freq - start_freq) // step)

        header = struct.pack('!B I', 0x17, n_arrays)

        segment = struct.pack(
            '! Q Q Q I',
            start_freq,  # startfreq
            end_freq,    # endfreq
            step,        # step
            n_points     # nPoints
        )

        payload = header + segment
        return self.build_command_frame(business_type=0x17, params=payload)

    def build_wbdf_command(self, frequency: int, ifbw: int = 40000000) -> bytes:
        """
        构建宽带测向命令 WBDF (0x19)

        命令格式:
        - nBdType: 1字节 - 0x19
        - nArrays: 4字节 - 动态数组数目
        - freq: 8字节 - 频率
        - ifbw: 8字节 - 中频带宽

        Args:
            frequency: 频率(Hz)
            ifbw: 中频带宽(Hz)

        Returns:
            命令帧字节数据
        """
        header = struct.pack(
            '!B I Q Q',
            0x19,        # nBdType (WBDF)
            0,           # nArrays
            frequency,   # freq
            ifbw         # ifbw
        )

        return self.build_command_frame(business_type=0x19, params=header)

    def build_stop_command(self, task_id: str) -> bytes:
        """
        构建停止测量命令

        Args:
            task_id: 任务ID

        Returns:
            命令帧字节数据
        """
        # 停止命令不发送到设备，由本地处理
        return b''


class BusinessDataBuilder:
    """业务数据构建器"""

    # 业务数据标志位
    FLAG_BASE_DATA = 0x01      # 基础业务数据
    FLAG_AUTO_NOISE = 0x02     # 自动背噪数据
    FLAG_OCCUPANCY = 0x04      # 占用度统计数据
    FLAG_MANUAL_NOISE = 0x08   # 手工背噪数据

    def __init__(self):
        pass

    def build_sglfreq_data(self, frequency: int, itu_values: list,
                           occupancy: float = 0.0, threshold: float = -100.0) -> bytes:
        """
        构建单频测量响应数据 SGLFREQ (0x10)

        数据格式:
        - nBdType: 1字节 - 0x10
        - nFlags: 2字节 - 业务数据标志
        - nArrays: 4字节 - ITU测量结果数目
        - nOffset: 4字节 - 相对首索引偏移
        - freq: 8字节 - 实际工作频率
        动态部分:
        - value: 4字节 - 测量项结果
        - occ: 2字节 - 占用度 (*100)
        - thr: 2字节 - 手工门限 (*100)

        Args:
            frequency: 频率(Hz)
            itu_values: ITU测量值列表
            occupancy: 占用度
            threshold: 门限

        Returns:
            业务数据字节
        """
        n_arrays = len(itu_values)

        # 固定部分
        header = struct.pack(
            '!B H I I',
            0x10,                    # nBdType
            self.FLAG_BASE_DATA,     # nFlags
            n_arrays,                # nArrays (4字节long)
            0                        # nOffset
        )

        # 频率
        freq_part = struct.pack('!Q', frequency)

        # 动态部分
        dynamic = b''
        occ_scaled = int(occupancy * 100)
        thr_scaled = int(threshold * 100)

        for value in itu_values:
            dynamic += struct.pack('!f', value)  # value
            dynamic += struct.pack('!h', occ_scaled)  # occ
            dynamic += struct.pack('!h', thr_scaled)  # thr

        return header + freq_part + dynamic

    def build_fscan_data(self, levels: list, n_flags: int = FLAG_BASE_DATA) -> bytes:
        """
        构建频段扫描响应数据 FSCAN (0x15)

        数据格式:
        - nBdType: 1字节 - 0x15
        - nFlags: 2字节 - 业务数据标志
        - nArrays: 4字节 - 频段扫描点数目
        - nOffset: 4字节 - 相对首索引偏移
        动态部分:
        - value: 2字节 - 电平值 (*100)

        Args:
            levels: 电平值列表(dBm)
            n_flags: 业务数据标志

        Returns:
            业务数据字节
        """
        n_arrays = len(levels)

        header = struct.pack(
            '!B H I I',
            0x15,        # nBdType
            n_flags,     # nFlags
            n_arrays,    # nArrays (4字节long)
            0            # nOffset
        )

        dynamic = b''
        for level in levels:
            level_scaled = int(level * 100)
            dynamic += struct.pack('!h', level_scaled)

        return header + dynamic

    def build_df_data(self, frequency: int, level: float, df_level: float,
                      quality: float, azimuth: float, elevation: float = 0.0,
                      compass: float = 0.0) -> bytes:
        """
        构建测向响应数据 DF (0x12)

        数据格式:
        - nBdType: 1字节 - 0x12
        - nFlags: 2字节 - 业务数据标志
        - nArrays: 4字节 - 动态数组数目
        - nOffset: 4字节 - 相对首索引偏移
        - Level: 2字节 - 电平 (*100)
        - DfLevel: 2字节 - 测向电平 (*100)
        - Qulity: 4字节 - 测向质量
        - Azumith: 4字节 - 方位角
        - Elevation: 4字节 - 俯仰角
        - compass: 4字节 - 罗盘值

        Args:
            frequency: 频率(Hz)
            level: 电平(dBm)
            df_level: 测向电平
            quality: 测向质量
            azimuth: 方位角
            elevation: 俯仰角
            compass: 罗盘值

        Returns:
            业务数据字节
        """
        header = struct.pack(
            '!B H I I',
            0x12,                    # nBdType
            self.FLAG_BASE_DATA,     # nFlags
            1,                       # nArrays (4字节long)
            0                        # nOffset
        )

        fixed = struct.pack(
            '!h h f f f f',
            int(level * 100),       # Level
            int(df_level * 100),    # DfLevel
            quality,                # Qulity
            azimuth,                # Azumith
            elevation,              # Elevation
            compass                  # compass
        )

        # 频率(测向通常不带频率，这里预留)
        freq_part = struct.pack('!Q', frequency)

        return header + fixed + freq_part
