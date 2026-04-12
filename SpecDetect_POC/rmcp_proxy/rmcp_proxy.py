#!/usr/bin/env python3
"""
RMCP TCP 流量监听代理

功能：
1. TCP透明代理 - 监听本地端口，转发到目标设备
2. 流量记录 - 记录原始数据和结构化日志
3. 帧头解析 - 解析RMCP协议帧头
4. 实时输出 - 控制台实时显示请求/响应
"""

import socket
import struct
import threading
import time
import os
import json
import sys
from datetime import datetime
from config import (
    PROXY_HOST, PROXY_PORT, DEVICE_HOST, DEVICE_PORT,
    LOG_DIR, LOG_LEVEL, RMCP_FRAME_HEADER_SIZE,
    MSG_TYPE_REQUEST, MSG_TYPE_RESPONSE, MSG_TYPE_DATA_1, MSG_TYPE_DATA_2
)


class RMCPFrame:
    """RMCP帧解析器"""

    @staticmethod
    def parse_header(data):
        """解析RMCP帧头 (18字节)"""
        if len(data) < RMCP_FRAME_HEADER_SIZE:
            return None

        dwLength = struct.unpack('<I', data[0:4])[0]
        tmStamp = struct.unpack('<Q', data[4:12])[0]
        nVersion = struct.unpack('>H', data[12:14])[0]  # 大端序
        nMsgType = data[14]
        nFlags = data[15]
        nCheckSum = struct.unpack('<H', data[16:18])[0]

        # 验证帧头有效性
        # nVersion 应该是 7
        # dwLength 应该与实际数据长度匹配
        # tmStamp 应该是有效的时间戳 (1601年后)
        if nVersion != 7:
            return None
        if dwLength > 65535:  # 异常大的长度
            return None
        # FILETIME 有效范围检查 (1601-01-01 到现在)
        if tmStamp < 116444736000000000 or tmStamp > 140000000000000000:
            return None

        return {
            'dwLength': dwLength,
            'tmStamp': tmStamp,
            'nVersion': nVersion,
            'nMsgType': nMsgType,
            'nFlags': nFlags,
            'nCheckSum': nCheckSum,
            'total_size': len(data)
        }

    @staticmethod
    def get_msg_type_name(msg_type):
        """获取消息类型名称"""
        names = {
            MSG_TYPE_REQUEST: 'REQUEST',
            MSG_TYPE_RESPONSE: 'RESPONSE',
            MSG_TYPE_DATA_1: 'DATA_29',
            MSG_TYPE_DATA_2: 'DATA_95',
        }
        return names.get(msg_type, f'UNKNOWN({msg_type})')

    @staticmethod
    def format_timestamp(tmStamp):
        """将FILETIME转换为可读时间"""
        try:
            unix_time = (tmStamp - 116444736000000000) / 10000000
            dt = datetime.fromtimestamp(unix_time)
            return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        except:
            return str(tmStamp)

    @staticmethod
    def parse_fscan_data(data):
        """解析 FSCAN 业务数据

        FSCAN 数据帧结构 (RMCPTP帧头18字节之后):
        - LEADER (4 bytes): 0xEEEE1DE6 (-286331154)
        - VER (1 byte): 版本号
        - STC (4 bytes): 时间戳计数器
        - TS (8 bytes): FILETIME 时间戳
        - PL (4 bytes): 负载长度
        - EL (2 bytes): 结束标记
        - DT (1 byte): 数据类型 (12 = FSCAN)
        - DL (4 bytes): 数据长度
        - 频段序号 (4 bytes)
        - 信道总数 (4 bytes)
        - 起始频率 (8 bytes, double)
        - 结束频率 (8 bytes, double)
        - 起始频率序号 (4 bytes)
        - 步长 (8 bytes, double)
        - 帧信道数量 (4 bytes)
        - 电平数据 (2 bytes each, signed short)
        """
        result = {
            'data_type': 'UNKNOWN',
            'raw_size': len(data)
        }

        if len(data) < 60:
            result['error'] = f'Data too short: {len(data)} < 60'
            return result

        try:
            # 解析固定头 (LEADER through EL)
            leader = struct.unpack('<i', data[0:4])[0]
            ver = data[4]
            stc = struct.unpack('<I', data[5:9])[0]
            ts = struct.unpack('<Q', data[9:17])[0]
            pl = struct.unpack('<I', data[17:21])[0]
            el = struct.unpack('<H', data[21:23])[0]

            result['LEADER'] = leader
            result['VER'] = ver
            result['STC'] = stc
            result['TS'] = ts
            result['PL'] = pl
            result['EL'] = el

            # 解析 DT 和 DL
            dt = data[23]
            dl = struct.unpack('<I', data[24:28])[0]
            result['DT'] = dt
            result['DL'] = dl

            # 根据 DT 判断数据类型
            if dt == 12:
                result['data_type'] = 'FSCAN'
            elif dt == 18:
                result['data_type'] = 'SPANALYSIS'
            elif dt == 16:
                result['data_type'] = 'DSCAN'

            # 解析频段信息 (从 offset 28 开始)
            offset = 28
            if len(data) >= offset + 36:
                band_no = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                total_channels = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                start_freq = struct.unpack('<d', data[offset:offset+8])[0]
                offset += 8
                end_freq = struct.unpack('<d', data[offset:offset+8])[0]
                offset += 8
                start_index = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                step = struct.unpack('<d', data[offset:offset+8])[0]
                offset += 8

                result['band_no'] = band_no
                result['total_channels'] = total_channels
                result['start_freq'] = start_freq
                result['end_freq'] = end_freq
                result['start_index'] = start_index
                result['step'] = step

            # 解析帧信道数量
            if len(data) >= offset + 4:
                frame_channels = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                result['frame_channels'] = frame_channels

                # 解析电平数据
                levels = []
                while offset + 2 <= len(data):
                    level = struct.unpack('<h', data[offset:offset+2])[0]
                    levels.append(level)
                    offset += 2

                if levels:
                    result['levels'] = levels
                    result['level_count'] = len(levels)
                    result['level_min'] = min(levels)
                    result['level_max'] = max(levels)

        except struct.error as e:
            result['error'] = str(e)

        return result

    @staticmethod
    def parse_fscan_data_simple(data, startfreq=0, step=0):
        """
        解析简化的 FSCAN 数据帧 (实测格式)

        帧结构 (从RMCP帧的payload开始):
        - Business header: 3 bytes (包含nBdType等信息)
        - Counters: 8 bytes (4 int16 values, 第一值为512)
        - Spectrum data: int16 little-endian

        转换公式: dBm = raw_value / 10
        """
        result = {
            'data_type': 'SIMPLE_FSCAN',
            'raw_size': len(data)
        }

        try:
            if len(data) < 11:
                result['error'] = f'Data too short: {len(data)} < 11'
                return result

            # Business header: bytes 0-2
            # nBdType is typically at byte 0 (0x0F = 15 for FSCAN)
            result['nBdType'] = data[0]

            # Counters at bytes 3-10 (4 int16)
            counters = struct.unpack('<4h', data[3:11])
            result['counters'] = list(counters)
            result['nArrays'] = counters[0]  # 通常是 512

            # Spectrum data starts at byte 11
            spectrum_offset = 11
            if len(data) > spectrum_offset:
                spectrum_bytes = data[spectrum_offset:]
                # 解析所有 int16 值
                num_levels = len(spectrum_bytes) // 2
                levels = struct.unpack(f'<{num_levels}h', spectrum_bytes[:num_levels*2])
                result['levels'] = list(levels)
                result['level_count'] = len(levels)

                if levels:
                    result['level_min'] = min(levels)
                    result['level_max'] = max(levels)
                    # 转换 dBm
                    dbm_values = [v / 10.0 for v in levels]
                    result['dbm_min'] = min(dbm_values)
                    result['dbm_max'] = max(dbm_values)
                    result['dbm_avg'] = sum(dbm_values) / len(dbm_values)

                # 计算频率
                if step > 0:
                    frequencies = [startfreq + i * step for i in range(len(levels))]
                    result['frequencies'] = frequencies[:10]  # 只保存前10个作为样本

        except struct.error as e:
            result['error'] = str(e)

        return result


class CaptureLogger:
    """流量记录器"""

    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_id = timestamp
        self.raw_file = os.path.join(log_dir, f'capture_{timestamp}.raw')
        self.log_file = os.path.join(log_dir, f'capture_{timestamp}.log')
        self.json_file = os.path.join(log_dir, f'capture_{timestamp}.json')
        self.conn_file = os.path.join(log_dir, f'connections_{timestamp}.csv')

        self.frames = []
        self.connections = []
        self.lock = threading.Lock()

        # 初始化流量日志文件头
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RMCP Traffic Capture Log\n")
            f.write(f"Session: {timestamp}\n")
            f.write(f"Started: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
            f.write("=" * 80 + "\n\n")

        # 初始化连接日志 CSV
        with open(self.conn_file, 'w', encoding='utf-8') as f:
            f.write("timestamp,event,client_ip,client_port,server_ip,server_port,duration_ms,bytes_sent,bytes_recv\n")

    def log_connection(self, event, client_addr, server_addr, duration_ms=0, bytes_sent=0, bytes_recv=0):
        """记录连接事件"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        conn_info = {
            'timestamp': timestamp,
            'event': event,
            'client_ip': client_addr[0] if client_addr else '',
            'client_port': client_addr[1] if client_addr else 0,
            'server_ip': server_addr[0] if server_addr else '',
            'server_port': server_addr[1] if server_addr else 0,
            'duration_ms': duration_ms,
            'bytes_sent': bytes_sent,
            'bytes_recv': bytes_recv
        }
        with self.lock:
            self.connections.append(conn_info)
            # 实时保存连接 CSV
            with open(self.conn_file, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp},{event},{conn_info['client_ip']},{conn_info['client_port']},"
                       f"{conn_info['server_ip']},{conn_info['server_port']},"
                       f"{duration_ms},{bytes_sent},{bytes_recv}\n")
        return conn_info

    def log_frame(self, direction, data, addr):
        """记录帧"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        frame_info = {
            'timestamp': timestamp,
            'direction': direction,
            'src': addr[0],
            'src_port': addr[1],
            'size': len(data),
            'hex': data.hex()
        }

        header = RMCPFrame.parse_header(data)
        if header:
            frame_info['header'] = {
                'dwLength': header['dwLength'],
                'nVersion': header['nVersion'],
                'nMsgType': header['nMsgType'],
                'nMsgTypeName': RMCPFrame.get_msg_type_name(header['nMsgType']),
                'nFlags': header['nFlags'],
                'nCheckSum': header['nCheckSum'],
                'timestamp': RMCPFrame.format_timestamp(header['tmStamp'])
            }

            if header['nMsgType'] == MSG_TYPE_REQUEST:
                frame_info['data_type'] = 'XML_REQUEST'
                try:
                    xml_data = data[RMCP_FRAME_HEADER_SIZE:]
                    xml_start_idx = xml_data.find(b'<?xml')
                    if xml_start_idx >= 0:
                        frame_info['xml_content'] = xml_data[xml_start_idx:].decode('gb2312', errors='ignore')[:500]
                except:
                    pass

            # 解析 DATA 帧 (nMsgType=0) 的 FSCAN 业务数据
            if header['nMsgType'] == 0 and len(data) > RMCP_FRAME_HEADER_SIZE + 60:
                payload = data[RMCP_FRAME_HEADER_SIZE:]
                fscan = RMCPFrame.parse_fscan_data(payload)
                if fscan.get('data_type') == 'FSCAN':
                    frame_info['data_type'] = 'FSCAN'
                    frame_info['fscan'] = fscan
                else:
                    # 尝试简化的 FSCAN 解析
                    # payload = RMCP payload (after 18-byte header)
                    # simple parser expects: business header (3) + counters (8) + spectrum
                    simple = RMCPFrame.parse_fscan_data_simple(payload)
                    if simple.get('level_count', 0) > 0:
                        frame_info['data_type'] = 'SIMPLE_FSCAN'
                        frame_info['fscan'] = simple

        with self.lock:
            self.frames.append(frame_info)

        self._print_to_console(timestamp, direction, header, len(data), addr, frame_info)

        # 写入原始文件
        with open(self.raw_file, 'ab') as f:
            f.write(data)

        # 实时保存
        self._save_json_line()
        self._save_log_line(frame_info)

    def _print_to_console(self, timestamp, direction, header, size, addr, frame_info=None):
        """打印到控制台"""
        if header:
            msg_type = RMCPFrame.get_msg_type_name(header['nMsgType'])
            extra = ""
            if header['nMsgType'] == MSG_TYPE_REQUEST:
                extra = " -> REQUEST"
            elif header['nMsgType'] == 0 and frame_info and 'fscan' in frame_info:
                fs = frame_info['fscan']
                if 'level_count' in fs:
                    extra = f" | {fs['level_count']} points"
                    if 'dbm_min' in fs:
                        extra += f" | dBm: {fs['dbm_min']:.1f}~{fs['dbm_max']:.1f}"
            print(f"[{timestamp}] {direction:4s} {msg_type:12s} "
                  f"len={size:5d} from={addr[0]}:{addr[1]}{extra}")
        else:
            # 非RMCP帧，显示为 RAW_DATA
            print(f"[{timestamp}] {direction:4s} RAW_DATA      "
                  f"len={size:5d} from={addr[0]}:{addr[1]}")
        sys.stdout.flush()

    def _save_json_line(self):
        """实时保存JSON"""
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.frames, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _save_log_line(self, frame_info):
        """实时保存文本日志"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"Time: {frame_info['timestamp']}\n")
                f.write(f"Direction: {frame_info['direction']}\n")
                f.write(f"Source: {frame_info['src']}:{frame_info['src_port']}\n")
                f.write(f"Size: {frame_info['size']} bytes\n")

                if 'header' in frame_info:
                    h = frame_info['header']
                    f.write(f"Frame Header:\n")
                    f.write(f"  dwLength: {h['dwLength']}\n")
                    f.write(f"  nVersion: {h['nVersion']}\n")
                    f.write(f"  nMsgType: {h['nMsgType']} ({h['nMsgTypeName']})\n")
                    f.write(f"  nFlags: 0x{h['nFlags']:02x}\n")
                    f.write(f"  nCheckSum: {h['nCheckSum']}\n")
                    f.write(f"  FrameTime: {h['timestamp']}\n")

                if 'xml_content' in frame_info:
                    f.write(f"\nXML Content:\n{frame_info['xml_content']}\n")

                # FSCAN 数据输出
                if 'fscan' in frame_info:
                    fs = frame_info['fscan']
                    f.write(f"\nFSCAN Data:\n")
                    if 'LEADER' in fs:
                        f.write(f"  LEADER: {fs['LEADER']}\n")
                    if 'VER' in fs:
                        f.write(f"  VER: {fs['VER']}\n")
                    if 'band_no' in fs:
                        f.write(f"  频段序号: {fs['band_no']}\n")
                    if 'total_channels' in fs:
                        f.write(f"  信道总数: {fs['total_channels']}\n")
                    if 'start_freq' in fs:
                        f.write(f"  起始频率: {fs['start_freq']/1e6:.4f} MHz\n")
                    if 'end_freq' in fs:
                        f.write(f"  结束频率: {fs['end_freq']/1e6:.4f} MHz\n")
                    if 'start_index' in fs:
                        f.write(f"  起始频率序号: {fs['start_index']}\n")
                    if 'step' in fs:
                        f.write(f"  步长: {fs['step']/1e3:.1f} kHz\n")
                    if 'frame_channels' in fs:
                        f.write(f"  帧信道数量: {fs['frame_channels']}\n")
                    if 'level_count' in fs:
                        f.write(f"  电平数量: {fs['level_count']}\n")
                    if 'level_min' in fs and 'level_max' in fs:
                        if 'dbm_min' in fs:
                            f.write(f"  dBm范围: {fs['dbm_min']:.1f} ~ {fs['dbm_max']:.1f} (avg: {fs['dbm_avg']:.1f})\n")
                        else:
                            f.write(f"  电平范围: {fs['level_min']} ~ {fs['level_max']}\n")
                    if 'counters' in fs:
                        f.write(f"  Counters: {fs['counters']}\n")
                    if 'levels' in fs and len(fs['levels']) > 0:
                        if 'dbm_min' in fs:
                            # 显示 dBm 值 (raw / 10)
                            dbm_sample = [f"{v / 10.0:.1f}" for v in fs['levels'][:10]]
                            f.write(f"  dBm样本: [{', '.join(dbm_sample)}, ...]\n")
                        else:
                            levels_str = ', '.join(str(l) for l in fs['levels'][:16])
                            if len(fs['levels']) > 16:
                                levels_str += ', ...'
                            f.write(f"  电平样本(raw): [{levels_str}]\n")

                f.write("\n" + "-" * 80 + "\n\n")
        except:
            pass


class ProxyConnection:
    """代理连接处理"""

    def __init__(self, client_socket, client_addr, logger):
        self.client_socket = client_socket
        self.client_addr = client_addr
        self.logger = logger
        self.device_socket = None
        self.running = True
        self.close_lock = threading.Lock()
        self.start_time = None
        self.bytes_sent = 0
        self.bytes_recv = 0

    def run(self):
        """运行代理"""
        self.start_time = time.time()
        connection_start = self.logger.log_connection(
            'CONNECT', self.client_addr, (DEVICE_HOST, DEVICE_PORT)
        )
        print(f"[PROXY] New connection from {self.client_addr}")

        try:
            self.device_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.device_socket.connect((DEVICE_HOST, DEVICE_PORT))
            self.logger.log_connection(
                'DEVICE_CONNECT', (DEVICE_HOST, DEVICE_PORT), (DEVICE_HOST, DEVICE_PORT)
            )
            print(f"[PROXY] Connected to device {DEVICE_HOST}:{DEVICE_PORT}")

            thread1 = threading.Thread(target=self._forward_client_to_device)
            thread2 = threading.Thread(target=self._forward_device_to_client)

            thread1.daemon = True
            thread2.daemon = True

            thread1.start()
            thread2.start()

            while self.running:
                thread1.join(timeout=0.5)
                thread2.join(timeout=0.5)
                if not thread1.is_alive() and not thread2.is_alive():
                    break

        except Exception as e:
            print(f"[ERROR] Proxy error: {e}")
            self.logger.log_connection('ERROR', self.client_addr, (DEVICE_HOST, DEVICE_PORT))
        finally:
            self._log_connection_close()
            self.close()

    def _forward_client_to_device(self):
        """客户端 -> 设备"""
        try:
            self.client_socket.settimeout(2.0)
            while self.running:
                try:
                    data = self.client_socket.recv(8192)
                    if not data:
                        print("[PROXY] Client disconnected")
                        self.logger.log_connection('CLIENT_DISCONNECT', self.client_addr, (DEVICE_HOST, DEVICE_PORT))
                        break
                    self.bytes_sent += len(data)
                    if self.device_socket:
                        try:
                            self.device_socket.sendall(data)
                        except:
                            break
                    try:
                        self.logger.log_frame('C->S', data, self.client_addr)
                    except Exception as e:
                        print(f"[ERROR] Logger error: {e}")
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError):
                    print("[PROXY] Client disconnected")
                    self.logger.log_connection('CLIENT_DISCONNECT', self.client_addr, (DEVICE_HOST, DEVICE_PORT))
                    break
                except Exception as e:
                    print(f"[PROXY] Client recv error: {e}")
                    break
        except:
            import traceback
            traceback.print_exc()
        finally:
            self.running = False

    def _forward_device_to_client(self):
        """设备 -> 客户端"""
        try:
            if self.device_socket:
                self.device_socket.settimeout(2.0)
            while self.running:
                try:
                    data = self.device_socket.recv(8192)
                    if not data:
                        print("[PROXY] Device disconnected")
                        self.logger.log_connection('DEVICE_DISCONNECT', self.client_addr, (DEVICE_HOST, DEVICE_PORT))
                        break
                    self.bytes_recv += len(data)
                    try:
                        self.client_socket.sendall(data)
                    except:
                        break
                    try:
                        self.logger.log_frame('S->C', data, (DEVICE_HOST, DEVICE_PORT))
                    except Exception as e:
                        print(f"[ERROR] Logger error: {e}")
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError):
                    print("[PROXY] Device disconnected")
                    self.logger.log_connection('DEVICE_DISCONNECT', self.client_addr, (DEVICE_HOST, DEVICE_PORT))
                    break
                except Exception as e:
                    print(f"[PROXY] Device recv error: {e}")
                    break
        except:
            import traceback
            traceback.print_exc()
        finally:
            self.running = False

    def _log_connection_close(self):
        """记录连接关闭"""
        if self.start_time:
            duration_ms = int((time.time() - self.start_time) * 1000)
            self.logger.log_connection(
                'CLOSE', self.client_addr, (DEVICE_HOST, DEVICE_PORT),
                duration_ms=duration_ms,
                bytes_sent=self.bytes_sent,
                bytes_recv=self.bytes_recv
            )

    def close(self):
        """关闭连接"""
        with self.close_lock:
            if not self.running:
                return
            self.running = False

            # 关闭客户端 socket
            if self.client_socket:
                try:
                    self.client_socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.client_socket.close()
                except:
                    pass
                self.client_socket = None

            # 关闭设备 socket
            if self.device_socket:
                try:
                    self.device_socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.device_socket.close()
                except:
                    pass
                self.device_socket = None

            print("[PROXY] Connection closed")


def start_proxy():
    """启动代理服务器"""
    print("=" * 60)
    print("RMCP TCP Proxy - Traffic Capture Tool")
    print("=" * 60)
    print(f"Proxy listening: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Forwarding to: {DEVICE_HOST}:{DEVICE_PORT}")
    print(f"Log directory: {LOG_DIR}")
    print("=" * 60)
    print("\nWaiting for connections...\n")

    logger = CaptureLogger(LOG_DIR)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(5)
    server.settimeout(1.0)  # 设置超时以便响应 Ctrl+C

    try:
        while True:
            try:
                client_socket, client_addr = server.accept()
                print(f"\n[PROXY] New connection from {client_addr}")
                handler = ProxyConnection(client_socket, client_addr, logger)
                thread = threading.Thread(target=handler.run)
                thread.daemon = True
                thread.start()
            except TimeoutError:
                continue  # 超时后继续等待
    except KeyboardInterrupt:
        print("\n[PROXY] Shutting down...")
    finally:
        server.close()
        print(f"[PROXY] Logs saved to {logger.log_file}")


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("""
RMCP TCP Proxy - Traffic Capture Tool

Usage:
    python rmcp_proxy.py              Start proxy server
    python rmcp_proxy.py --test      Run test/demo

Configuration (edit config.py):
    PROXY_HOST/PROXY_PORT - Local proxy listen address
    DEVICE_HOST/DEVICE_PORT - Target device address
        """)
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        print("[TEST] Running frame parser test...")

        test_frame = bytes.fromhex(
            "bb0200001006b0cb11c9dc0100075a019660"
            "3c3f786d6c2076657273696f6e3d22312e302220656e636f64696e673d2267623233313222203f3e0a3c616374696f6e2069643d2231223e0a202020203c706172616d657465722067726f7570733d2231222073746174696f6e69643d223533303930303031222064657669636569643d22303031303622206465766963656e616d653d224d53383435222066756e6369643d223135223e0a20202020202020203c67726f757020696e6465783d2230223e0a2020202020202020202020203c6974656d206e616d653d22737461727466726571222076616c75653d223133374d487a22202f3e"
        )

        header = RMCPFrame.parse_header(test_frame)
        if header:
            print(f"[TEST] Frame parsed successfully:")
            print(f"  dwLength: {header['dwLength']}")
            print(f"  nVersion: {header['nVersion']}")
            print(f"  nMsgType: {header['nMsgType']} ({RMCPFrame.get_msg_type_name(header['nMsgType'])})")
            print(f"  nFlags: 0x{header['nFlags']:02x}")
        return

    start_proxy()


if __name__ == '__main__':
    main()
