"""RMCPTP协议解析器

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
from typing import Dict, Any, Optional, Tuple
from utils.exceptions import ProtocolParseError, ChecksumError
from utils.logger import get_logger

logger = get_logger('atom.parser')


class RMCPTPParser:
    """RMCPTP协议解析器"""

    # 帧头结构 (18字节):
    # dwLength: 4字节, tmStamp: 8字节, nVersion: 2字节,
    # nDataType: 1字节, nFlags: 1字节, nCheckSum: 2字节
    HEADER_FORMAT = '!IQHBBH'  # 网络字节序
    HEADER_SIZE = 18

    def __init__(self):
        self.header_info: Dict[str, Any] = {}

    def parse_frame(self, data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析RMCPTP帧

        Args:
            data: 原始字节数据

        Returns:
            (解析后的头部信息, 剩余数据)

        Raises:
            ProtocolParseError: 协议解析错误
            ChecksumError: 校验和错误
        """
        if len(data) < self.HEADER_SIZE:
            raise ProtocolParseError(f"数据长度不足: 需要{self.HEADER_SIZE}字节, 实际{len(data)}字节")

        # 解析帧头
        header_data = data[:self.HEADER_SIZE]
        try:
            # 先解析不含校验和的16字节
            dw_length, tm_stamp, n_version, n_data_type, n_flags = \
                struct.unpack('!IQHBB', header_data[:16])
            # 再解析校验和2字节
            n_checksum = struct.unpack('!H', header_data[16:18])[0]
        except struct.error as e:
            raise ProtocolParseError(f"帧头解析失败: {e}")

        # 验证校验和
        calculated_checksum = self._calculate_checksum(header_data[:-2])
        if calculated_checksum != n_checksum:
            raise ChecksumError(
                f"校验和错误: 计算值={hex(calculated_checksum)}, 实际值={hex(n_checksum)}"
            )

        self.header_info = {
            'dw_length': dw_length,
            'tm_stamp': tm_stamp,
            'n_version': n_version,
            'n_data_type': n_data_type,
            'n_flags': n_flags,
            'n_checksum': n_checksum,
            'total_length': dw_length + self.HEADER_SIZE
        }

        logger.debug(
            f"解析帧头: length={dw_length}, type={hex(n_data_type)}, "
            f"version={hex(n_version)}, flags={hex(n_flags)}"
        )

        # 返回剩余数据（业务数据部分）
        remaining = data[self.HEADER_SIZE:]
        return self.header_info, remaining

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

    def get_data_type_name(self, n_data_type: int) -> str:
        """获取数据类型名称"""
        from config.settings import RMCPTP_DATA_TYPE, BUSINESS_DATA_TYPE

        if n_data_type in RMCPTP_DATA_TYPE:
            return RMCPTP_DATA_TYPE[n_data_type]
        elif n_data_type in BUSINESS_DATA_TYPE:
            return BUSINESS_DATA_TYPE[n_data_type]
        else:
            return f"未知类型({hex(n_data_type)})"


class BusinessDataParser:
    """业务数据解析器

    业务数据结构 (RMCPBUSINESSDATA):
    - nBdType: 1字节 - 业务数据类型
    - nFlags: 2字节 - 业务数据标志
    - nArrays: 4字节 - 业务数组数目
    - nOffset: 4字节 - 相对首索引偏移
    """

    BUSINESS_DATA_HEADER_SIZE = 11

    # 业务数据标志位
    FLAG_BASE_DATA = 0x01      # 基础业务数据
    FLAG_AUTO_NOISE = 0x02     # 自动背噪数据
    FLAG_OCCUPANCY = 0x04      # 占用度统计数据
    FLAG_MANUAL_NOISE = 0x08   # 手工背噪数据

    def __init__(self):
        self.business_info: Dict[str, Any] = {}

    def parse_business_header(self, data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析业务数据头

        Args:
            data: 业务数据字节

        Returns:
            (业务头信息, 剩余数据)
        """
        if len(data) < self.BUSINESS_DATA_HEADER_SIZE:
            raise ProtocolParseError(
                f"业务数据头长度不足: 需要{self.BUSINESS_DATA_HEADER_SIZE}字节, "
                f"实际{len(data)}字节"
            )

        try:
            # nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4) = 11字节
            n_bd_type, n_flags, n_arrays, n_offset = struct.unpack('!B H I I', data[:11])
        except struct.error as e:
            raise ProtocolParseError(f"业务数据头解析失败: {e}")

        self.business_info = {
            'n_bd_type': n_bd_type,
            'n_flags': n_flags,
            'n_arrays': n_arrays,
            'n_offset': n_offset
        }

        logger.debug(
            f"解析业务头: type={hex(n_bd_type)}({self.get_business_type_name(n_bd_type)}), "
            f"flags={hex(n_flags)}, arrays={n_arrays}"
        )

        return self.business_info, data[self.BUSINESS_DATA_HEADER_SIZE:]

    def get_business_type_name(self, n_bd_type: int) -> str:
        """获取业务类型名称"""
        from config.settings import BUSINESS_DATA_TYPE
        return BUSINESS_DATA_TYPE.get(n_bd_type, f"未知({hex(n_bd_type)})")

    def parse_sglfreq_data(self, data: bytes, n_arrays: int) -> Dict[str, Any]:
        """
        解析单频测量数据 (SGLFREQ 0x10)

        数据格式:
        - freq: 8字节 - 实际工作频率
        - 动态部分: ITU测量结果 (float) + 占用度 (short) + 手工门限 (short)

        Returns:
            解析后的测量数据
        """
        if len(data) < 8:
            raise ProtocolParseError("SGLFREQ数据长度不足")

        freq = struct.unpack('!Q', data[:8])[0]
        result = {'frequency': freq, 'itu_values': []}

        # 解析ITU数据 (n_arrays组)
        offset = 8
        itu_size = 4  # float
        occ_size = 2  # short
        thr_size = 2  # short

        for i in range(n_arrays):
            if len(data) >= offset + itu_size + occ_size + thr_size:
                itu_value = struct.unpack('!f', data[offset:offset + itu_size])[0]
                occ = struct.unpack('!h', data[offset + itu_size:offset + itu_size + occ_size])[0]
                thr = struct.unpack('!h', data[offset + itu_size + occ_size:offset + itu_size + occ_size + thr_size])[0]

                result['itu_values'].append({
                    'value': itu_value,
                    'occupancy': occ / 100.0,  # 占用度 * 100
                    'threshold': thr / 100.0    # 门限 * 100
                })
                offset += itu_size + occ_size + thr_size

        return result

    def parse_fscan_data(self, data: bytes, n_arrays: int, n_flags: int) -> Dict[str, Any]:
        """
        解析频段扫描数据 (FSCAN 0x15)

        数据格式:
        - value: 2字节 - 电平值 (n_arrays组, 实际值*100)
        - 可选: thr (自动背噪), occ (占用度), thr (手工背噪)

        Returns:
            解析后的扫描数据
        """
        if len(data) < n_arrays * 2:
            raise ProtocolParseError("FSCAN数据长度不足")

        result = {
            'values': [],
            'has_auto_noise': bool(n_flags & self.FLAG_AUTO_NOISE),
            'has_occupancy': bool(n_flags & self.FLAG_OCCUPANCY),
            'has_manual_noise': bool(n_flags & self.FLAG_MANUAL_NOISE)
        }

        # 解析电平值
        for i in range(n_arrays):
            level = struct.unpack('!h', data[i * 2:(i + 1) * 2])[0]
            result['values'].append(level / 100.0)  # 实际值 * 100

        return result

    def parse_df_data(self, data: bytes) -> Dict[str, Any]:
        """
        解析测向数据 (DF 0x12 / IFDF 0x13)

        数据格式:
        - Level: 2字节 - 电平
        - DfLevel: 2字节 - 测向电平
        - Qulity: 4字节 - 测向质量
        - Azumith: 4字节 - 方位角
        - Elevation: 4字节 - 俯仰角
        - compass: 4字节 - 罗盘值

        Returns:
            解析后的测向数据
        """
        expected_size = 20  # 2+2+4+4+4+4
        if len(data) < expected_size:
            raise ProtocolParseError("测向数据长度不足")

        level, df_level, quality, azimuth, elevation, compass = struct.unpack(
            '!hhff ff', data[:expected_size]
        )

        return {
            'level': level / 100.0,
            'df_level': df_level / 100.0,
            'quality': quality,
            'azimuth': azimuth,
            'elevation': elevation,
            'compass': compass
        }
