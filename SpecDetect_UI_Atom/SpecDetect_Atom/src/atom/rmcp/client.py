# -*- coding: utf-8 -*-
"""
RMCP 客户端模块

负责与设备建立连接、发送请求、接收响应
"""

import socket
import struct
import threading
import time
from typing import Optional, Callable, List
from log.logger import LogTag
from .frame import (
    build_rmcp_frame,
    validate_rmcp_frame,
    parse_rmcp_callback_frame,
    MSG_TYPE_REQUEST,
    VERSION,
    FILETIME_MIN,
    FILETIME_MAX,
)


class RMCPClient:
    """RMCP 客户端"""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: int = 10,
        connect_timeout: int = 10
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.connect_timeout = connect_timeout

        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._recv_buffer: bytes = b''

    def connect(self) -> bool:
        """连接到设备"""
        with self._lock:
            if self._sock:
                return True

            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(self.connect_timeout)
                self._sock.connect((self.host, self.port))
                self._sock.settimeout(self.timeout)
                return True
            except Exception as e:
                self._sock = None
                return False

    def disconnect(self):
        """断开连接"""
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
            self._recv_buffer = b''

    def is_connected(self) -> bool:
        """检查连接状态"""
        if self._sock is None:
            return False

        try:
            self._sock.getpeername()
            return True
        except Exception:
            return False

    def send_request(
        self,
        xml_content: str,
        func_id: int = 15
    ) -> bool:
        """发送 RMCP 请求"""
        if not self._sock:
            if not self.connect():
                return False

        try:
            xml_bytes = xml_content.encode('gb2312')
            frame = build_rmcp_frame(xml_bytes, MSG_TYPE_REQUEST, func_id)
            self._sock.sendall(frame)
            return True
        except Exception as e:
            self.disconnect()
            return False

    def send_raw_frame(self, frame: bytes) -> bool:
        """直接发送原始 RMCP 帧（用于日志记录后直接发送）"""
        if not self._sock:
            return False
        try:
            self._sock.sendall(frame)
            return True
        except Exception:
            return False

    def _find_valid_frame_header(self, max_search: int = 100000) -> int:
        """在recv_buffer中搜索有效的RMCP帧头

        RMCP帧头结构:
        - offset 0-3: dwLength (little endian)
        - offset 4-11: tmStamp (little endian)
        - offset 12-13: nVersion (big endian, must be 7)

        Returns:
            找到的有效帧头位置，如果未找到返回-1
        """
        VERSION_OFFSET = 12

        buffer = self._recv_buffer
        search_end = min(len(buffer) - 18, max_search)

        # 收集所有nVersion=7的候选位置
        candidates = []
        for i in range(search_end):
            if buffer[i + VERSION_OFFSET] == 0 and buffer[i + VERSION_OFFSET + 1] == VERSION:
                dw_length = struct.unpack('<I', buffer[i:i + 4])[0]
                tm_stamp = struct.unpack('<Q', buffer[i + 4:i + 12])[0]

                # 宽松验证：dwLength合理(18-10000) + tmStamp在有效范围内
                # DSCAN帧可能达到8000+字节
                if 18 <= dw_length <= 10000 and FILETIME_MIN <= tm_stamp <= FILETIME_MAX:
                    candidates.append((i, dw_length, tm_stamp))

        if candidates:
            # 返回第一个候选位置
            pos, dw_len, ts = candidates[0]
            return pos

        return -1

    def receive_responses(self, buffer_size: int = 8192) -> List[bytes]:
        """接收 RMCP 响应（处理 TCP 流边界）

        循环 recv 直到至少解析出一帧或超时，避免分 chunk 到达时丢失帧。
        """
        # 获取 socket 引用（检查和获取需要原子化，防止 disconnect() 刚好在中间执行）
        with self._lock:
            if not self._sock:
                return []
            sock = self._sock
            old_timeout = sock.gettimeout()
            sock.settimeout(0.5)

        recv_count = 0

        while recv_count < 10:  # 最多 recv 10 次防止死循环
            recv_count += 1
            try:
                chunk = sock.recv(buffer_size)
                if chunk:
                    with self._lock:
                        self._recv_buffer += chunk
                else:
                    with self._lock:
                        self._recv_buffer = b''
                    sock.settimeout(old_timeout)
                    return []
            except socket.timeout:
                break
            except Exception as e:
                with self._lock:
                    self._recv_buffer = b''
                sock.settimeout(old_timeout)
                return []

            # 检查是否有完整帧可解析（header 18B + dw_length）
            with self._lock:
                if len(self._recv_buffer) >= 18:
                    dw_length = struct.unpack('<I', self._recv_buffer[0:4])[0]
                    if len(self._recv_buffer) >= 18 + dw_length:
                        break  # 有完整帧，去解析

        sock.settimeout(old_timeout)

        frames = []
        loop_count = 0

        while True:
            with self._lock:
                if len(self._recv_buffer) < 18:
                    break
                loop_count += 1
                if loop_count > 50:
                    break

                # 先验证帧头，再信任dw_length（防止残余数据导致buffer错位）
                if not validate_rmcp_frame(self._recv_buffer[:18]):
                    found_pos = self._find_valid_frame_header()
                    if found_pos > 0:
                        self._recv_buffer = self._recv_buffer[found_pos:]
                        continue
                    else:
                        break

                dw_length = struct.unpack('<I', self._recv_buffer[0:4])[0]
                total_frame_len = 18 + dw_length

                if len(self._recv_buffer) < total_frame_len:
                    break

                frame = self._recv_buffer[:total_frame_len]
                self._recv_buffer = self._recv_buffer[total_frame_len:]

            frames.append(frame)

        return frames

    def receive_response(self, buffer_size: int = 4096) -> Optional[bytes]:
        """接收单个 RMCP 响应"""
        frames = self.receive_responses(buffer_size)
        return frames[0] if frames else None

    def get_callback_datas(self, buffer_size: int = 8192) -> List[dict]:
        """接收并解析RMCP回调帧，返回业务数据列表

        返回统一的业务数据结构:
        {
            'tm_stamp': int,       # 时间戳
            'n_msg_type': int,     # 消息类型
            'n_bd_type': int,      # 业务数据类型 (如16=DSCAN, 15=FSCAN)
            'counters': list,      # 计数器
            'levels': list,        # 频谱数据
            'n_arrays': int,       # 数据点数
        }

        与receive_responses()区别:
        - 返回原始bytes列表
        - 本方法返回解析后的业务数据dict列表
        - service模块应该使用本方法，屏蔽RMCP协议细节
        """
        frames = self.receive_responses(buffer_size)
        result = []

        for frame in frames:
            callback_data = parse_rmcp_callback_frame(frame)
            if callback_data:
                result.append(callback_data)

        return result

    def receive_pscan_raw(
        self,
        callback: Callable[[dict], None],
        stop_event: threading.Event,
        buffer_size: int = 8192
    ):
        """接收 PScan 原始 DSCAN 数据流

        PScan 设备行为：
        1. 先发 1 个 RMCP 控制帧 (69B, msg_type=6, n_bd_type=16)
        2. 后续全部是原始 DSCAN payload（无 RMCP 帧头）
           每帧以 n_bd_type(1B) + reserved(2B) 开头

        与 receive_responses() 完全解耦，不影响 FScan。
        """
        control_frame_extracted = False

        while not stop_event.is_set():
            if not self._sock:
                if not self.connect():
                    time.sleep(0.5)
                    continue

            try:
                chunk = self._sock.recv(buffer_size)
                if not chunk:
                    break
                self._recv_buffer += chunk
            except socket.timeout:
                continue
            except Exception as e:
                break

            # 第一步：提取并跳过 RMCP 控制帧 (一次性)
            if not control_frame_extracted:
                if len(self._recv_buffer) < 18:
                    continue

                if validate_rmcp_frame(self._recv_buffer[:18]):
                    dw_length = struct.unpack('<I', self._recv_buffer[0:4])[0]
                    total_len = 18 + dw_length

                    if len(self._recv_buffer) < total_len:
                        continue

                    control_frame = self._recv_buffer[:total_len]
                    self._recv_buffer = self._recv_buffer[total_len:]
                    control_frame_extracted = True
                else:
                    # 无有效 RMCP 帧头，整段当作 raw DSCAN
                    control_frame_extracted = True

            # 第二步：从 buffer 中提取完整的 DSCAN payload
            while len(self._recv_buffer) >= 11:
                # 校验 n_bd_type 必须为 16 (DSCAN)
                if self._recv_buffer[0] != 16:
                    # 非 DSCAN 数据，跳过一个字节继续搜索
                    self._recv_buffer = self._recv_buffer[1:]
                    continue

                # 读取 reserved 字段 (bytes 1-2)
                reserved = struct.unpack('<H', self._recv_buffer[1:3])[0]

                if reserved == 1:
                    # 长帧：spectrum_length 在 bytes 3-4
                    if len(self._recv_buffer) < 5:
                        break
                    spectrum_length = struct.unpack('<H', self._recv_buffer[3:5])[0]
                    frame_size = 11 + spectrum_length * 2
                elif reserved == 0:
                    # 短帧：counters@3-10, spectrum 长度由 payload 大小决定
                    # 但需要更多数据才能确定帧大小，先等 buffer 积累
                    # 按 1211B 兜底 (600点)
                    frame_size = 1211
                else:
                    # reserved 既非 0 也非 1，说明帧边界错位，跳过此字节
                    self._recv_buffer = self._recv_buffer[1:]
                    continue

                if len(self._recv_buffer) < frame_size:
                    break

                dscan_payload = self._recv_buffer[:frame_size]
                self._recv_buffer = self._recv_buffer[frame_size:]

                result = self._parse_raw_dscan(dscan_payload)
                if result:
                    callback(result)

        self.disconnect()

    def _parse_raw_dscan(self, payload: bytes) -> Optional[dict]:
        """解析单个原始 DSCAN payload (无 RMCP 帧头)

        DSCAN payload 结构:
        - offset 0: n_bd_type (0x10)
        - offset 1-2: reserved (0=短帧, 1=长帧)
        - offset 3-10: counters / spectrum_length
        - offset 11+: spectrum (int16[])

        短帧 (reserved=0): counters@3-10, spectrum 长度由 payload 大小决定
        长帧 (reserved=1): spectrum_length@3-4 (int16), spectrum@11+
        """
        if len(payload) < 11:
            return None

        try:
            n_bd_type = payload[0]
            if n_bd_type != 16:
                return None

            reserved = struct.unpack('<H', payload[1:3])[0]

            if reserved == 1:
                # 长帧：spectrum_length 在 bytes 3-4
                spectrum_length = struct.unpack('<H', payload[3:5])[0]
                n_arrays = spectrum_length
                counters = [spectrum_length, 0, 0, 0]  # spectrum_length 作为 counters[0]
            else:
                # 短帧：counters 在 bytes 3-10, spectrum 长度由 payload 大小决定
                counters = struct.unpack('<4h', payload[3:11])
                n_arrays = (len(payload) - 11) // 2

            spectrum_offset = 11

            if n_arrays <= 0 or spectrum_offset + n_arrays * 2 > len(payload):
                return None

            levels = []
            for i in range(n_arrays):
                level_raw = struct.unpack('<h', payload[spectrum_offset:spectrum_offset+2])[0]
                levels.append(level_raw)
                spectrum_offset += 2

            # 数据校验：正常 RMCP DSCAN 值范围 -1025~+1025 (即 -102.5~+102.5 dBm)
            # 超出范围说明帧边界对齐错误或非频谱数据帧
            if n_arrays > 0:
                sample = levels[:min(10, n_arrays)]
                if any(v < -1025 or v > 1025 for v in sample):
                    return None

            return {
                'tm_stamp': 0,
                'n_msg_type': 29,
                'n_bd_type': n_bd_type,
                'counters': list(counters),
                'n_arrays': n_arrays,
                'levels': levels,
            }
        except Exception:
            return None

