# -*- coding: utf-8 -*-
"""
Stream Forwarder 模块

负责主动连接到外部地址并转发 streaming 数据
类似于原版 Atom 的 TpOpen[host:port] 行为
"""

import socket
import threading
import time
from typing import Optional
from log.logger import info, warning, error, LogTag


class StreamForwarder:
    """主动连接到外部地址并转发 streaming 数据"""

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._connected = False
        self._connecting = False
        self._lock = threading.Lock()
        self._connect_time: Optional[float] = None

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        with self._lock:
            return self._connected and self._sock is not None

    def connect(self) -> bool:
        """主动连接到指定地址（重试3次）

        Returns:
            True if connection successful, False otherwise
        """
        max_retries = 3
        retry_delay = 1.0  # 秒

        for attempt in range(1, max_retries + 1):
            with self._lock:
                if self._connected or self._connecting:
                    return self._connected

                self._connecting = True

            try:
                info(f"[STREAM] 正在连接到 {self.host}:{self.port} (尝试 {attempt}/{max_retries})...", LogTag.STREAM)

                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(self.timeout)
                self._sock.connect((self.host, self.port))

                with self._lock:
                    self._connected = True
                    self._connecting = False
                    self._connect_time = time.time()

                info(f"[STREAM] 连接成功: {self.host}:{self.port}", LogTag.STREAM)
                return True

            except socket.timeout:
                error(f"[STREAM] 连接超时 (尝试 {attempt}/{max_retries}): {self.host}:{self.port}", LogTag.STREAM)
                self._cleanup()

            except socket.error as e:
                error(f"[STREAM] 连接失败 (尝试 {attempt}/{max_retries}): {self.host}:{self.port}, error={e}", LogTag.STREAM)
                self._cleanup()

            except Exception as e:
                error(f"[STREAM] 连接异常 (尝试 {attempt}/{max_retries}): {self.host}:{self.port}, error={e}", LogTag.STREAM)
                self._cleanup()

            # 重试前等待（除了最后一次尝试后）
            if attempt < max_retries:
                info(f"[STREAM] 等待 {retry_delay}秒后重试...", LogTag.STREAM)
                time.sleep(retry_delay)

        error(f"[STREAM] 连接失败，已重试 {max_retries} 次: {self.host}:{self.port}", LogTag.STREAM)
        return False

    def send(self, data: bytes) -> bool:
        """发送数据到已建立的连接

        Args:
            data: 要发送的数据

        Returns:
            True if send successful, False otherwise
        """
        if not self.is_connected:
            warning(f"[STREAM] send失败: 未连接 {self.host}:{self.port}", LogTag.STREAM)
            return False

        try:
            self._sock.sendall(data)
            info(f"[STREAM] 已发送 {len(data)}B -> {self.host}:{self.port}", LogTag.STREAM)
            return True

        except socket.error as e:
            error(f"[STREAM] 发送失败: {self.host}:{self.port}, error={e}", LogTag.STREAM)
            self._on_disconnect()
            return False

        except Exception as e:
            error(f"[STREAM] 发送异常: {self.host}:{self.port}, error={e}", LogTag.STREAM)
            self._on_disconnect()
            return False

    def close(self):
        """关闭连接"""
        with self._lock:
            if self._connect_time:
                duration = time.time() - self._connect_time
                info(f"[STREAM] 关闭连接: {self.host}:{self.port}, 持续时间={duration:.1f}s", LogTag.STREAM)
            self._cleanup()

    def _cleanup(self):
        """内部清理方法"""
        self._connecting = False
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _on_disconnect(self):
        """连接断开时的处理"""
        with self._lock:
            was_connected = self._connected
            self._cleanup()

        if was_connected:
            warning(f"[STREAM] 连接已断开: {self.host}:{self.port}", LogTag.STREAM)

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False

    def __del__(self):
        """析构时确保关闭连接"""
        try:
            self.close()
        except Exception:
            pass
