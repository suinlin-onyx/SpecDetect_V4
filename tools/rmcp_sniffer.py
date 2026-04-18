"""
RMCPTP 协议抓包解析工具
用于监听 atom 与 device (172.18.114.166:9999) 之间的 RMCPTP 流量

用法:
    python rmcp_sniffer.py                    # 抓包模式
    python rmcp_sniffer.py --test            # 本地测试模式（无需设备）
    python rmcp_sniffer.py --host 172.18.114.166 --port 9999
"""

import struct
import time
import socket
import threading
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

# ============================================================================
# 配置
# ============================================================================

TARGET_HOST = "172.18.114.166"
TARGET_PORT = 9999
LISTEN_PORT = 9999  # 本地监听端口（如果用代理模式）

# RMCPTP v2.0 协议配置
RMCPTP_HEADER_SIZE = 18
BUSINESS_HEADER_SIZE = 11

# RMCPTP 数据类型映射
RMCPTP_DATA_TYPE = {
    0x00: '监测业务数据',
    0x01: '音频描述头',
    0x02: '音频数据',
    0x03: '分发请求',
    0x04: '信息数据',
    0x06: '业务数据描述头',
}

# 业务数据类型映射 (RMCPTP v2.0 规范)
BUSINESS_DATA_TYPE = {
    0x10: 'SGLFREQ',       # 单频测量
    0x11: 'IFANALYSIS',    # 中频分析
    0x12: 'DF',            # 单频测向
    0x13: 'IFDF',          # 中频测向
    0x14: 'DFSEARCH',      # 搜索测向
    0x15: 'FSCAN',         # 频段扫描
    0x16: 'DSCAN',         # 数字扫描
    0x17: 'PSCAN',         # 频谱扫描
    0x18: 'SPANALYSIS',    # 频谱分析
    0x19: 'WBMONDF',       # 宽带监测测向
    0x1A: 'TDANALYSIS',    # 时域分析
    0x1C: 'WBFFTMon',      # 宽带FFT观测
    0x1D: 'DIGDEM',        # IQ数字解调
    0x1F: 'EDETN',         # 能量探测
    0x22: 'MODREC',        # 信号识别
    0x24: 'ITUMEAS',       # ITU测量
}

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('RMCPTP')


# ============================================================================
# RMCPTP 解析器
# ============================================================================

class RMCPTPParser:
    """RMCPTP v2.0 协议解析器"""

    @staticmethod
    def parse_frame_header(data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析 RMCPTP 帧头（18字节）

        帧头结构:
        - dwLength: 4字节 unsigned int - 报文长度
        - tmStamp: 8字节 FILETIME - 报文产生时间
        - nVersion: 2字节 unsigned short - 版本号 (0x0007)
        - nDataType: 1字节 unsigned char - 数据类型
        - nFlags: 1字节 unsigned char - 标志位
        - nCheckSum: 2字节 unsigned short - 头校验和

        Returns:
            (头部信息字典, 剩余业务数据)
        """
        if len(data) < RMCPTP_HEADER_SIZE:
            raise ValueError(f"数据长度不足: 需要{RMCPTP_HEADER_SIZE}字节, 实际{len(data)}字节")

        header_data = data[:RMCPTP_HEADER_SIZE]

        # 解析帧头 (网络字节序/大端序)
        dw_length, tm_stamp, n_version, n_data_type, n_flags, n_checksum = \
            struct.unpack('!IQHBBH', header_data)

        header_info = {
            'dw_length': dw_length,
            'tm_stamp': tm_stamp,
            'n_version': n_version,
            'n_data_type': n_data_type,
            'n_data_type_name': RMCPTP_DATA_TYPE.get(n_data_type, f"0x{n_data_type:02X}"),
            'n_flags': n_flags,
            'n_checksum': n_checksum,
            'total_length': dw_length + RMCPTP_HEADER_SIZE
        }

        # 验证校验和
        calculated = RMCPTPParser._calculate_checksum(header_data[:-2])
        header_info['checksum_ok'] = (calculated == n_checksum)

        return header_info, data[RMCPTP_HEADER_SIZE:]

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
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

    @staticmethod
    def parse_business_header(data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析业务数据头（11字节）

        业务数据头结构 (RMCPBUSINESSDATA):
        - nBdType: 1字节 - 业务数据类型
        - nFlags: 2字节 - 业务数据标志
        - nArrays: 4字节 - 业务数组数目
        - nOffset: 4字节 - 相对首索引偏移

        Returns:
            (业务头信息字典, 剩余数据)
        """
        if len(data) < BUSINESS_HEADER_SIZE:
            raise ValueError(f"业务数据头长度不足: 需要{BUSINESS_HEADER_SIZE}字节, 实际{len(data)}字节")

        n_bd_type, n_flags, n_arrays, n_offset = struct.unpack('!B H I I', data[:BUSINESS_HEADER_SIZE])

        business_info = {
            'n_bd_type': n_bd_type,
            'n_bd_type_name': RMCPTP_DATA_TYPE.get(n_bd_type, f"0x{n_bd_type:02X}"),
            'n_flags': n_flags,
            'n_arrays': n_arrays,
            'n_offset': n_offset
        }

        return business_info, data[BUSINESS_HEADER_SIZE:]

    @staticmethod
    def parse_sglfreq_data(data: bytes, n_arrays: int) -> Dict[str, Any]:
        """
        解析单频测量数据 (SGLFREQ 0x10)

        数据格式:
        - freq: 8字节 - 实际工作频率
        - 动态部分: ITU测量结果 (float) + 占用度 (short) + 手工门限 (short)

        Returns:
            解析后的测量数据
        """
        result = {'frequency': 0, 'itu_values': []}

        if len(data) < 8:
            return result

        freq = struct.unpack('!Q', data[:8])[0]
        result['frequency'] = freq

        # 解析ITU数据 (n_arrays组)
        offset = 8
        itu_size = 4  # float
        occ_size = 2   # short
        thr_size = 2   # short

        for i in range(min(n_arrays, 10)):  # 限制最多10组，避免过多输出
            if len(data) >= offset + itu_size + occ_size + thr_size:
                itu_value = struct.unpack('!f', data[offset:offset + itu_size])[0]
                occ = struct.unpack('!h', data[offset + itu_size:offset + itu_size + occ_size])[0]
                thr = struct.unpack('!h', data[offset + itu_size + occ_size:offset + itu_size + occ_size + thr_size])[0]

                result['itu_values'].append({
                    'value': itu_value,
                    'occupancy': occ / 100.0,
                    'threshold': thr / 100.0
                })
                offset += itu_size + occ_size + thr_size

        return result

    @staticmethod
    def parse_fscan_data(data: bytes, n_arrays: int, n_flags: int) -> Dict[str, Any]:
        """
        解析频段扫描数据 (FSCAN 0x15)

        数据格式:
        - value: 2字节 - 电平值 (n_arrays组, 实际值*100)

        Returns:
            解析后的扫描数据
        """
        result = {
            'values': [],
            'has_auto_noise': bool(n_flags & 0x02),
            'has_occupancy': bool(n_flags & 0x04),
            'has_manual_noise': bool(n_flags & 0x08)
        }

        # 解析电平值
        for i in range(min(n_arrays, 100)):  # 限制最多100个点
            if len(data) >= (i + 1) * 2:
                level = struct.unpack('!h', data[i * 2:(i + 1) * 2])[0]
                result['values'].append(level / 100.0)

        if n_arrays > 100:
            result['values'].append(f'... 还有 {n_arrays - 100} 个点')

        return result

    @staticmethod
    def parse_df_data(data: bytes) -> Dict[str, Any]:
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
            return {'error': '数据长度不足'}

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

    @staticmethod
    def parse_business_data(data: bytes, bd_type: int, n_arrays: int, n_flags: int) -> Dict[str, Any]:
        """根据业务类型解析业务数据"""
        try:
            if bd_type == 0x10:  # SGLFREQ
                return RMCPTPParser.parse_sglfreq_data(data, n_arrays)
            elif bd_type == 0x15:  # FSCAN
                return RMCPTPParser.parse_fscan_data(data, n_arrays, n_flags)
            elif bd_type in (0x12, 0x13):  # DF, IFDF
                return RMCPTPParser.parse_df_data(data)
            else:
                return {'raw_data': data.hex()[:64]}
        except Exception as e:
            return {'parse_error': str(e), 'raw_data': data.hex()[:64]}


# ============================================================================
# RMCPTP 帧构建器（用于测试）
# ============================================================================

class RMCPTPBuilder:
    """RMCPTP v2.0 帧构建器"""

    VERSION = 0x0007

    @staticmethod
    def build_frame(business_type: int, business_data: bytes) -> bytes:
        """
        构建 RMCPTP 帧

        Args:
            business_type: 业务数据类型 (如 0x10 = SGLFREQ)
            business_data: 业务数据字节

        Returns:
            完整的 RMCPTP 帧字节
        """
        # 构建帧头
        tm_stamp = int(time.time() * 10000000) + 116444736000000000  # Windows FILETIME

        # 构建不含校验和的帧头前16字节
        header_without_checksum = struct.pack(
            '!IQHBB',
            len(business_data),  # dwLength
            tm_stamp,            # tmStamp
            RMCPTPBuilder.VERSION,  # nVersion
            0x00,                # nDataType
            0x00                 # nFlags
        )

        # 计算校验和
        checksum = RMCPTPParser._calculate_checksum(header_without_checksum)

        # 完整的18字节帧头
        header = header_without_checksum + struct.pack('!H', checksum)

        # 业务数据 = 业务类型(1字节) + 业务头(11字节) + 业务内容
        business = struct.pack('!B', business_type) + business_data

        return header + business

    @staticmethod
    def build_sglfreq_command(frequency: int, n_arrays: int = 1) -> bytes:
        """构建 SGLFREQ 单频测量命令帧"""
        # 业务数据头: nFlags=0, nArrays=1, nOffset=0
        business_header = struct.pack('!H I I', 0x00, n_arrays, 0)

        # 业务内容: freq(8字节) + ITU数据(8字节 * n_arrays)
        business_content = struct.pack('!Q', frequency)
        for i in range(n_arrays):
            business_content += struct.pack('!f h h',
                -65.5,   # ITU值
                50,      # 占用度 * 100
                -80      # 门限 * 100
            )

        business_data = business_header + business_content
        return RMCPTPBuilder.build_frame(0x10, business_data)

    @staticmethod
    def build_fscan_command(start_freq: int, stop_freq: int, step: int) -> bytes:
        """构建 FSCAN 频段扫描命令帧"""
        n_arrays = max(1, (stop_freq - start_freq) // step)

        # 业务数据头
        business_header = struct.pack('!H I I', 0x00, n_arrays, 0)

        # 业务内容: 频点数据
        business_content = b''
        freq = start_freq
        while freq <= stop_freq:
            business_content += struct.pack('!h', -65)  # 电平值 * 100
            freq += step

        business_data = business_header + business_content
        return RMCPTPBuilder.build_frame(0x15, business_data)


# ============================================================================
# TCP 流重组器
# ============================================================================

class TCPStreamAssembler:
    """TCP 流重组器，用于将离散 TCP 包重组为完整数据"""

    def __init__(self):
        self.streams: Dict[Tuple[str, int, str, int], List[bytes]] = {}

    def add_packet(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int,
                   seq: int, data: bytes, direction: str) -> Optional[bytes]:
        """
        添加 TCP 包数据

        Returns:
            如果形成完整帧，返回重组后的完整数据
        """
        key = (src_ip, src_port, dst_ip, dst_port)

        if direction == 'request':
            key = (src_ip, src_port, dst_ip, dst_port)
        else:
            key = (dst_ip, dst_port, src_ip, src_port)

        if key not in self.streams:
            self.streams[key] = []

        self.streams[key].append((seq, data))
        self.streams[key].sort(key=lambda x: x[0])

        # 尝试重组
        assembled = b''
        for _, pkt_data in self.streams[key]:
            assembled += pkt_data

        return assembled if len(assembled) > 0 else None

    def clear(self):
        """清空所有流"""
        self.streams.clear()


# ============================================================================
# 抓包解析器 (使用原始 socket)
# ============================================================================

class RMCPTPSniffer:
    """
    RMCPTP 抓包解析器

    工作原理:
    1. 监听本地端口 LISTEN_PORT
    2. 等待目标连接（atom 连接本地代理，代理转发到目标）
    3. 解析 RMCPTP 帧并打印结构体
    """

    def __init__(self, listen_port: int = LISTEN_PORT,
                 target_host: str = TARGET_HOST,
                 target_port: int = TARGET_PORT):
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.running = False
        self.assembler = TCPStreamAssembler()

    def start(self):
        """启动抓包"""
        logger.info(f"启动 RMCPTP 监听器...")
        logger.info(f"  监听端口: {self.listen_port}")
        logger.info(f"  目标地址: {self.target_host}:{self.target_port}")

        self.running = True

        # 创建监听 socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', self.listen_port))
        server.listen(5)
        logger.info(f"等待连接...")

        while self.running:
            try:
                client_sock, client_addr = server.accept()
                logger.info(f"收到连接: {client_addr}")

                # 连接到目标 device
                target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    target_sock.connect((self.target_host, self.target_port))
                    logger.info(f"已连接到目标: {self.target_host}:{self.target_port}")
                except Exception as e:
                    logger.error(f"连接目标失败: {e}")
                    client_sock.close()
                    continue

                # 启动双向转发线程
                threading.Thread(
                    target=self._forward,
                    args=(client_sock, target_sock, 'client->target'),
                    daemon=True
                ).start()
                threading.Thread(
                    target=self._forward,
                    args=(target_sock, client_sock, 'target->client'),
                    daemon=True
                ).start()

            except Exception as e:
                if self.running:
                    logger.error(f"接收连接错误: {e}")

    def _forward(self, src: socket.socket, dst: socket.socket, direction: str):
        """转发数据并解析"""
        try:
            while self.running:
                data = src.recv(4096)
                if not data:
                    break

                # 发送到目标
                dst.sendall(data)

                # 尝试解析 RMCPTP 帧
                self._try_parse(direction, data)

        except Exception as e:
            pass
        finally:
            try:
                src.close()
            except:
                pass

    def _try_parse(self, direction: str, data: bytes):
        """尝试解析 RMCPTP 帧"""
        try:
            if len(data) < RMCPTP_HEADER_SIZE:
                return

            header_info, business_data = RMCPTPParser.parse_frame_header(data)

            arrow = "→" if "client->target" in direction else "←"
            logger.info(f"{arrow} {direction}")
            logger.info(f"  帧头: dwLength={header_info['dw_length']}, "
                       f"nDataType={header_info['n_data_type_name']}, "
                       f"nFlags=0x{header_info['n_flags']:02X}, "
                       f"checksum={'OK' if header_info['checksum_ok'] else 'FAIL'}")

            # 解析业务数据
            if len(business_data) >= BUSINESS_HEADER_SIZE:
                biz_info, biz_content = RMCPTPParser.parse_business_header(business_data)
                logger.info(f"  业务: nBdType={biz_info['n_bd_type_name']}, "
                           f"nArrays={biz_info['n_arrays']}, nFlags=0x{biz_info['n_flags']:04X}")

                # 解析业务内容
                if len(biz_content) > 0:
                    biz_result = RMCPTPParser.parse_business_data(
                        biz_content,
                        biz_info['n_bd_type'],
                        biz_info['n_arrays'],
                        biz_info['n_flags']
                    )
                    logger.info(f"  内容: {biz_result}")

        except Exception as e:
            # 不是完整的 RMCPTP 帧，忽略
            pass

    def stop(self):
        """停止抓包"""
        self.running = False
        logger.info("停止监听")


# ============================================================================
# 测试模式
# ============================================================================

def run_test():
    """本地测试模式，无需设备"""
    print("\n" + "="*60)
    print("RMCPTP 协议解析测试模式")
    print("="*60 + "\n")

    print("【测试1】构建并解析 SGLFREQ 单频测量帧")
    print("-" * 40)

    # 构建 SGLFREQ 命令
    sglfreq_frame = RMCPTPBuilder.build_sglfreq_command(frequency=100_000_000, n_arrays=1)
    print(f"原始帧 (hex): {sglfreq_frame.hex(' ')}")

    # 解析帧头
    try:
        header_info, business_data = RMCPTPParser.parse_frame_header(sglfreq_frame)
        print(f"\n帧头解析结果:")
        print(f"  dwLength: {header_info['dw_length']}")
        print(f"  nVersion: 0x{header_info['n_version']:04X}")
        print(f"  nDataType: {header_info['n_data_type_name']}")
        print(f"  nFlags: 0x{header_info['n_flags']:02X}")
        print(f"  nCheckSum: 0x{header_info['n_checksum']:04X} (验证: {'OK' if header_info['checksum_ok'] else 'FAIL'})")

        # 解析业务数据头
        biz_info, biz_content = RMCPTPParser.parse_business_header(business_data)
        print(f"\n业务数据头解析结果:")
        print(f"  nBdType: {biz_info['n_bd_type_name']}")
        print(f"  nFlags: 0x{biz_info['n_flags']:04X}")
        print(f"  nArrays: {biz_info['n_arrays']}")
        print(f"  nOffset: {biz_info['n_offset']}")

        # 解析业务内容
        biz_result = RMCPTPParser.parse_business_data(
            biz_content,
            biz_info['n_bd_type'],
            biz_info['n_arrays'],
            biz_info['n_flags']
        )
        print(f"\n业务数据解析结果:")
        for k, v in biz_result.items():
            print(f"  {k}: {v}")

    except Exception as e:
        print(f"解析错误: {e}")

    print("\n" + "="*60)
    print("【测试2】构建并解析 FSCAN 频段扫描帧")
    print("-" * 40)

    # 构建 FSCAN 命令
    fscan_frame = RMCPTPBuilder.build_fscan_command(
        start_freq=100_000_000,
        stop_freq=101_000_000,
        step=1_000_000
    )
    print(f"原始帧 (hex): {fscan_frame.hex(' ')}")

    try:
        header_info, business_data = RMCPTPParser.parse_frame_header(fscan_frame)
        print(f"\n帧头解析结果:")
        print(f"  dwLength: {header_info['dw_length']}")
        print(f"  nDataType: {header_info['n_data_type_name']}")

        biz_info, biz_content = RMCPTPParser.parse_business_header(business_data)
        print(f"\n业务数据头解析结果:")
        print(f"  nBdType: {biz_info['n_bd_type_name']}")
        print(f"  nArrays: {biz_info['n_arrays']}")

        biz_result = RMCPTPParser.parse_business_data(
            biz_content,
            biz_info['n_bd_type'],
            biz_info['n_arrays'],
            biz_info['n_flags']
        )
        print(f"\n业务数据解析结果:")
        print(f"  频点数量: {len(biz_result.get('values', []))}")
        print(f"  前5个电平值: {biz_result.get('values', [])[:5]}")

    except Exception as e:
        print(f"解析错误: {e}")

    print("\n" + "="*60)
    print("【测试3】校验和计算验证")
    print("-" * 40)

    # 验证校验和计算
    test_data = bytes.fromhex('00 00 00 20 00 00 00 00 00 00 00 00 00 07 00 00')
    calc_sum = RMCPTPParser._calculate_checksum(test_data)
    print(f"测试数据: {test_data.hex(' ')}")
    print(f"计算校验和: 0x{calc_sum:04X}")

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60 + "\n")

    # 测试 socket 监听
    print("\n【测试4】启动本地 TCP 代理监听测试")
    print("-" * 40)
    print("提示: 这将在本地 9999 端口启动监听，等待连接...")
    print("     可以用以下命令测试:")
    print("     telnet localhost 9999")
    print("     或: python -c \"import socket; s=socket.socket(); s.connect(('localhost', 9999)); s.send(b'\\x00\\x00\\x00\\x10')\"")
    print()

    # 注意：不实际启动监听，避免冲突
    print("如需启动抓包模式，请确保:")
    print("1. atom 已配置连接 localhost:9999")
    print("2. 本脚本已启动并转发到 172.18.114.166:9999")


# ============================================================================
# 主入口
# ============================================================================

if __name__ == '__main__':
    import sys

    if '--test' in sys.argv:
        run_test()
    else:
        sniffer = RMCPTPSniffer()
        try:
            sniffer.start()
        except KeyboardInterrupt:
            sniffer.stop()
            print("\n已退出")
