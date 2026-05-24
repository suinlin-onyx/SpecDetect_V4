# -*- coding: utf-8 -*-
"""
SOAP 服务模块

负责接收和处理 SOAP 请求
"""

import socket
import threading
from typing import Optional, Callable, Dict, Any
from .parser import extract_soap_request


class SOAPServer:
    """SOAP 服务器"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handler: Optional[Callable] = None

    def set_handler(self, handler: Callable[[Dict], bytes]):
        """设置请求处理器"""
        self._handler = handler

    def bind(self) -> bool:
        """绑定端口"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.listen(5)
            self._sock.settimeout(1.0)
            return True
        except Exception as e:
            self._sock = None
            return False

    def start(self):
        """启动服务"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止服务"""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _accept_loop(self):
        """接受连接循环"""
        while self._running:
            try:
                client, addr = self._sock.accept()
                thread = threading.Thread(target=self._handle_client, args=(client, addr), daemon=True)
                thread.start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_client(self, client: socket.socket, addr):
        """处理客户端请求"""
        try:
            client.settimeout(10.0)
            data = b''
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'Content-Length:' in data:
                    import re
                    match = re.search(b'Content-Length:\s*(\d+)', data)
                    if match:
                        content_length = int(match.group(1))
                        body_start = data.find(b'\r\n\r\n')
                        if body_start < 0:
                            body_start = data.find(b'\n\n')
                        if body_start >= 0:
                            sep_len = 4 if data[body_start:body_start+2] == b'\r\n' else 2
                            received = len(data) - body_start - sep_len
                            if received >= content_length:
                                break
                elif len(data) > 1024 * 1024:
                    break

            if not data:
                client.close()
                return

            request = extract_soap_request(data)
            if not request:
                client.close()
                return

            if self._handler:
                response = self._handler(request)
                if response:
                    client.sendall(response)

        except Exception:
            pass
        finally:
            try:
                client.close()
            except Exception:
                pass