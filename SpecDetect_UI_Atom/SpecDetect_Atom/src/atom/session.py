# -*- coding: utf-8 -*-
"""
Session 数据结构

包含 StreamSession 类、BandCollector 类
完全按照 emulated_atom.py 实现
"""

import queue
import socket
import threading
import time
from typing import Optional, List, Any
from enum import Enum
from log.logger import log, LogTag


class SessionState(Enum):
    """Session 状态"""
    PENDING = "pending"     # 待匹配
    ACTIVE = "active"       # 已匹配，正在推送
    CLOSING = "closing"    # 关闭中
    CLOSED = "closed"       # 已关闭


class BandCollector:
    """三频段收集器

    接收线程 put(band_info) 单个频段，缓冲凑齐 3 个后一次性 get() 返回 [B1, B2, B3]
    与 emulated_atom BandCollector 行为完全一致
    """

    def __init__(self, timeout=5.0):
        import queue
        self._input_queue = queue.Queue(maxsize=200)
        self._output_queue = queue.Queue(maxsize=10)
        self._timeout = timeout
        self._band_buffer = {0: None, 512: None, 1024: None}  # 缓冲当前轮的 3 个 band
        self._round_start_time = None

    def put(self, band_info):
        """接收单个频段数据（与 emulated_atom 一致）

        Args:
            band_info: 单个频段的 band_info 字典
        """
        self._input_queue.put(band_info)
        self._process_input()

    def _process_input(self):
        """处理输入队列，缓冲并凑齐 3 个 band"""
        while True:
            try:
                band_info = self._input_queue.get_nowait()
            except:
                break

            start_idx = band_info.get('counters', [0, 0, 0, 0])[2]
            tm_stamp = band_info.get('_tm_stamp', 0)
            band_name = 'B1' if start_idx == 0 else 'B2' if start_idx == 512 else 'B3'

            # 重传检测：同一频段新帧到达，输出上一轮
            if self._band_buffer.get(start_idx) is not None:
                prev_tm = self._band_buffer[start_idx].get('_tm_stamp', 0)
                log(f"[BandCollector] {band_name} retransmit, 输出上一轮", LogTag.SESSION)
                self._do_output()

            self._band_buffer[start_idx] = band_info
            if self._round_start_time is None:
                self._round_start_time = time.time()

            # 凑齐 3 个 band 时输出
            if all(v is not None for v in self._band_buffer.values()):
                self._do_output()

    def _do_output(self):
        """输出当前轮的完整 bands"""
        complete = []
        for idx in [0, 512, 1024]:
            if self._band_buffer[idx] is not None:
                complete.append(self._band_buffer[idx])

        if complete:
            self._output_queue.put(complete)
            log(f"[BandCollector] 输出: {len(complete)}/3 频段", LogTag.SESSION)

        self._band_buffer = {0: None, 512: None, 1024: None}
        self._round_start_time = None

    def get(self):
        """获取已排序的 [B1, B2, B3] 数组（与 emulated_atom 一致）"""
        self._process_input()
        # 超时兜底输出
        if self._round_start_time is not None:
            if time.time() - self._round_start_time > self._timeout:
                self._do_output()
        try:
            return self._output_queue.get(timeout=0.1)
        except:
            return None

    def clear(self):
        self._band_buffer = {0: None, 512: None, 1024: None}
        self._round_start_time = None
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except:
                break
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except:
                break

    def get_status(self):
        pending_keys = [k for k, v in self._band_buffer.items() if v is not None]
        return {
            'input_size': self._input_queue.qsize(),
            'output_size': self._output_queue.qsize(),
            'pending_keys': pending_keys,
        }


class StreamSession:
    """配对的 streamsrc/RMCP 会话"""

    def __init__(
        self,
        streamsrc_client: socket.socket,
        taskid: str,
        fscan_params: dict = None
    ):
        # 基本属性
        self.streamsrc_client: Optional[socket.socket] = streamsrc_client
        self.taskid: str = taskid
        self.fscan_params: dict = fscan_params or {}

        # 状态
        self.state: SessionState = SessionState.PENDING

        # 同步原语
        self.lock: threading.Lock = threading.Lock()
        self._stop_event: threading.Event = threading.Event()

        # RMCP 客户端（延迟创建）
        self.target_client: Optional[Any] = None

        # 时间追踪
        self.data_received: bool = False
        self.last_data_time: float = time.time()

        # 推送线程
        self.push_thread: Optional[threading.Thread] = None
        self.push_running: bool = False

        # 隐式状态
        self._closing: bool = False
        self._fscan_request_sent: bool = False
        self._band_buffer_time: float = 0

        # Band 收集器
        self._band_collector: Optional[BandCollector] = None

        # outputchannel 转发器（主动连接模式）
        self.outputchannel_forwarder: Optional[Any] = None
        self.outputchannel_frame_count: int = 0  # 发送给 outputchannel 的帧数

    def attach_target(self, target_client: Any):
        """关联 RMCP 客户端"""
        with self.lock:
            self.target_client = target_client

    def close_all(self):
        """关闭所有连接（幂等操作）

        清理顺序：
        1. 设置停止事件，阻止新数据进入
        2. 清空 RMCP 客户端 recv_buffer
        3. 清空 BandCollector
        4. 清空各模式数据队列
        5. 关闭 socket 连接
        6. 关闭 outputchannel_forwarder
        """
        with self.lock:
            if self.streamsrc_client is None and self.target_client is None and self.outputchannel_forwarder is None:
                return

            # 设置关闭状态
            self._closing = True
            self.push_running = False
            self._stop_event.set()
            self._fscan_request_sent = False

            # 1. 清空 RMCP 客户端 recv_buffer（防止残留数据污染新 session）
            if self.target_client:
                if hasattr(self.target_client, '_recv_buffer'):
                    self.target_client._recv_buffer = b''

            # 2. 关闭 streamsrc 客户端
            if self.streamsrc_client:
                try:
                    self.streamsrc_client.close()
                except Exception:
                    pass
                self.streamsrc_client = None

            # 3. 关闭 RMCP 客户端
            if self.target_client:
                try:
                    self.target_client.disconnect()
                except Exception:
                    pass
                self.target_client = None

            # 4. 关闭 outputchannel_forwarder（主动连接模式）
            if self.outputchannel_forwarder:
                try:
                    self.outputchannel_forwarder.close()
                except Exception:
                    pass
                # 打印发送统计
                if self.outputchannel_frame_count > 0:
                    log(f"[STREAM] outputchannel 发送完成: {self.outputchannel_frame_count} 帧", LogTag.STREAM)
                self.outputchannel_forwarder = None

            # 5. 清空 BandCollector
            if self._band_collector:
                self._band_collector.clear()
                self._band_collector = None

            # 6. 清空各模式数据队列
            for attr in ['_mscan_data_queue', '_sglfreq_data_queue']:
                q = getattr(self, attr, None)
                if q:
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except:
                            break
                    delattr(self, attr)

            # 7. 清空 PScan 相关状态
            for attr in ['_pscan_data_event', '_pscan_band']:
                if hasattr(self, attr):
                    try:
                        delattr(self, attr)
                    except:
                        pass

    def stop_push(self):
        """停止推送线程"""
        self.push_running = False
        self._stop_event.set()

    def update_data_time(self):
        """更新最后收数据时间"""
        self.last_data_time = time.time()
        self.data_received = True

    def get_band_collector(self) -> BandCollector:
        """获取或创建 BandCollector"""
        if self._band_collector is None:
            self._band_collector = BandCollector()
        return self._band_collector

    def is_closing(self) -> bool:
        """检查是否正在关闭"""
        return self._closing
