# -*- coding: utf-8 -*-
"""
streamsrc 服务模块

负责接收 streamsrc 客户端连接和数据推送
完全按照 emulated_atom.py 实现
"""

import socket
import struct
import threading
import time
from typing import Optional, Callable
from atom.session import StreamSession
from atom.stream.frame import build_uuid_frame
from log.logger import info, warning, error, LogTag


def _format_levels(levels: list) -> str:
    """格式化电平数组前20个元素用于日志输出"""
    if not levels:
        return ""
    sample = levels[:20]
    vals = ', '.join(f'{v/10:.1f}' if abs(v) > 100 else str(v) for v in sample)
    suffix = '...' if len(levels) > 20 else ''
    return f" levels[{len(levels)}]=[{vals}{suffix}]"


class StreamSrcServer:
    """streamsrc 服务器"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._session_manager = None
        self._push_callback: Optional[Callable] = None
        self._session_matched_callback: Optional[Callable] = None
        self._clients: list = []       # 活跃客户端列表
        self._clients_lock = threading.Lock()

    def set_session_manager(self, session_manager):
        """设置会话管理器"""
        self._session_manager = session_manager

    def set_push_callback(self, callback: Callable[[StreamSession, bytes], None]):
        """设置推送回调"""
        self._push_callback = callback

    def set_session_matched_callback(self, callback: Callable[[StreamSession], None]):
        """设置 session 匹配成功回调"""
        self._session_matched_callback = callback

    def bind(self) -> bool:
        """绑定端口，始终绑定 0.0.0.0 以接受本地和远端连接"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(('0.0.0.0', self.port))
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
        last_check_time = time.time()
        while self._running:
            try:
                self._sock.settimeout(1.0)
                try:
                    client, addr = self._sock.accept()
                    info(f"[STREAM] 收到客户端连接: {addr}", LogTag.STREAM)
                    thread = threading.Thread(target=self._handle_client, args=(client, addr), daemon=True)
                    thread.start()
                except socket.timeout:
                    # 每3秒检查一次死客户端
                    now = time.time()
                    if now - last_check_time >= 3:
                        self._check_dead_clients()
                        last_check_time = now
            except Exception:
                break

    def _check_dead_clients(self):
        """检查并移除断开的客户端（使用 select，非阻塞检测）"""
        import select as select_module

        disconnected = []
        with self._clients_lock:
            for client in self._clients[:]:
                try:
                    # 使用 select 检测客户端是否可读（断开时 recv 返回空）
                    r, _, _ = select_module.select([client], [], [], 0)
                    if r and client in r:
                        # 客户端可读，检查是否为空（断开）
                        try:
                            data = client.recv(1, socket.MSG_PEEK)
                            if data == b'':
                                info(f"[STREAM] 检测到死客户端", LogTag.STREAM)
                                disconnected.append(client)
                        except (ConnectionResetError, BrokenPipeError, OSError, socket.error):
                            info(f"[STREAM] 客户端已断开", LogTag.STREAM)
                            disconnected.append(client)
                except Exception:
                    disconnected.append(client)

        # 移除死客户端并关闭对应 session
        for client in disconnected:
            with self._clients_lock:
                if client in self._clients:
                    self._clients.remove(client)

            if self._session_manager:
                session = self._session_manager.get_session_by_socket(client)
                if session:
                    self._session_manager.close_session(session)

    def _handle_client(self, client: socket.socket, addr):
        """处理客户端连接

        客户端连上 streamsrc 后纯等待推送，不发任何数据。
        1. 立即 FIFO 匹配 pending_session
        2. 触发 RMCP 请求和推送
        """
        try:
            info(f"[STREAM] 收到客户端连接: {addr}", LogTag.STREAM)

            session = None
            if self._session_manager:
                # FIFO 匹配最早的 pending session
                session = self._session_manager.match_session(client)
                if session:
                    info(f"[STREAM] FIFO 匹配 session: taskid={session.taskid}", LogTag.STREAM)

            if session:
                # 加入活跃客户端列表
                with self._clients_lock:
                    self._clients.append(client)

                # 发送 UUID 注册帧（设备行为：连接后第一帧）
                try:
                    uuid_frame = build_uuid_frame(session.taskid)
                    # 会引起一系列无关的信息发送, 待验证
                    # client.sendall(uuid_frame)
                    info(f"[STREAM] UUID帧已发送: taskid={session.taskid}, {len(uuid_frame)}B", LogTag.STREAM)
                except Exception as e:
                    info(f"[STREAM] UUID帧发送失败: {e}", LogTag.STREAM)

                if self._session_matched_callback:
                    self._session_matched_callback(session)
                self._start_push(session)
            else:
                info(f"[STREAM] 无 pending session，关闭连接: {addr}", LogTag.STREAM)
                try:
                    client.close()
                except Exception:
                    pass

        except Exception:
            pass

    def _start_push(self, session: StreamSession):
        """启动推送线程"""
        def push_loop():
            session.push_running = True
            mode = session.fscan_params.get('mode', 'fscan')
            info(f"[STREAM] 推送线程启动: taskid={session.taskid}, mode={mode}", LogTag.STREAM)

            band_collector = session.get_band_collector()
            sglfreq_frame_count = 0

            push_count = 0
            while not session._stop_event.is_set():
                try:
                    push_count += 1
                    if mode == 'fscan':
                        all_bands = band_collector.get()
                        if not all_bands:
                            if push_count % 50 == 1:
                                info(f"[STREAM] push_loop 运行中 #{push_count}: 等待band数据...", LogTag.STREAM)
                            continue

                        if self._push_callback:
                            for band in all_bands:
                                start_idx = band.get('counters', [0,0,0])[2]
                                spectrum = band.get('levels', [])
                                frame = self._push_callback(session, band)
                                info(f"[STREAM] Band{1 if start_idx == 0 else 2 if start_idx == 512 else 3}: {len(spectrum)}点 frame={len(frame)}B{_format_levels(spectrum)}",LogTag.STREAM)
                                if frame:
                                    # 发送给 streamsrc 客户端（如果存在）
                                    if session.streamsrc_client:
                                        session.streamsrc_client.sendall(frame)
                                    # 发送给 outputchannel forwarder（如果存在，主动连接模式）
                                    if session.outputchannel_forwarder:
                                        if session.outputchannel_forwarder.send(frame):
                                            session.outputchannel_frame_count += 1

                    elif mode == 'mscan':
                        # 事件驱动：从队列逐个取出 RMCP 回调推帧
                        data_queue = getattr(session, '_mscan_data_queue', None)
                        if data_queue:
                            try:
                                band_info = data_queue.get(timeout=3.0)
                            except Exception:
                                if push_count % 10 == 1:
                                    info(f"[STREAM] push_loop #{push_count}: MScan等待数据超时", LogTag.STREAM)
                                continue
                        else:
                            time.sleep(0.1)
                            continue

                        # 过滤 level=0 的数据（设备初始化帧）
                        if not band_info or not band_info.get('levels'):
                            continue
                        raw_level = band_info['levels'][0]
                        if raw_level == 0:
                            continue

                        # 存储最新数据供 _push_callback 使用
                        session._latest_band_info = band_info

                        if self._push_callback:
                            frame = self._push_callback(session, None)
                            if frame:
                                # 发送给 streamsrc 客户端（如果存在）
                                if session.streamsrc_client:
                                    session.streamsrc_client.sendall(frame)
                                # 发送给 outputchannel forwarder（如果存在，主动连接模式）
                                if session.outputchannel_forwarder:
                                    if session.outputchannel_forwarder.send(frame):
                                        session.outputchannel_frame_count += 1
                                levels = band_info.get('levels', [])
                                levels_str = _format_levels(levels)
                                info(f"[STREAM] MSCAN: {len(frame)}B{levels_str}", LogTag.STREAM)

                    elif mode == 'sglfreq':
                        # 事件驱动：从队列取出 RMCP 回调，每个回调推 3 帧（频谱+电平+ITU）
                        data_queue = getattr(session, '_sglfreq_data_queue', None)
                        if data_queue:
                            try:
                                band_info = data_queue.get(timeout=3.0)
                            except Exception:
                                if push_count % 10 == 1:
                                    info(f"[STREAM] push_loop #{push_count}: SglFreq等待数据超时", LogTag.STREAM)
                                continue
                        else:
                            time.sleep(0.1)
                            continue

                        # 过滤无效数据
                        if not band_info or not band_info.get('levels'):
                            continue

                        # 存储最新数据供 _push_callback 使用
                        session._latest_band_info = band_info

                        # 每个回调推 3 帧：频谱(DT:7) + 电平(DT:101) + ITU(DT:8)
                        if self._push_callback:
                            levels = band_info.get('levels', [])
                            levels_str = _format_levels(levels)
                            for frame_idx in range(3):
                                frame = self._push_callback(session, None)
                                if frame:
                                    # 发送给 streamsrc 客户端（如果存在）
                                    if session.streamsrc_client:
                                        session.streamsrc_client.sendall(frame)
                                    # 发送给 outputchannel forwarder（如果存在，主动连接模式）
                                    if session.outputchannel_forwarder:
                                        if session.outputchannel_forwarder.send(frame):
                                            session.outputchannel_frame_count += 1
                                    sglfreq_frame_count += 1
                                    if len(frame) == 3256:
                                        info(f"[STREAM] SglFreq#{sglfreq_frame_count} 频谱(DT:7) {len(frame)}B{levels_str}", LogTag.STREAM)
                                    elif len(frame) == 40:
                                        info(f"[STREAM] SglFreq#{sglfreq_frame_count} 电平(DT:101) {len(frame)}B{levels_str}", LogTag.STREAM)
                                    elif len(frame) == 36:
                                        info(f"[STREAM] SglFreq#{sglfreq_frame_count} ITU(DT:8) {len(frame)}B{levels_str}", LogTag.STREAM)
                                    else:
                                        info(f"[STREAM] SglFreq#{sglfreq_frame_count} {len(frame)}B{levels_str}", LogTag.STREAM)

                    elif mode == 'pscan':
                        # 事件驱动：等待 RMCP 接收线程通知新数据到达
                        data_event = getattr(session, '_pscan_data_event', None)
                        if data_event:
                            got_data = data_event.wait(timeout=3.0)
                            data_event.clear()
                            if not got_data:
                                if push_count % 10 == 1:
                                    info(f"[STREAM] push_loop #{push_count}: PScan等待数据超时", LogTag.STREAM)
                                continue

                        # 从 session 获取最新 DSCAN band 数据
                        band = getattr(session, '_pscan_band', None)
                        if band and self._push_callback:
                            frame = self._push_callback(session, band)
                            if frame:
                                # 发送给 streamsrc 客户端（如果存在）
                                if session.streamsrc_client:
                                    session.streamsrc_client.sendall(frame)
                                # 发送给 outputchannel forwarder（如果存在，主动连接模式）
                                if session.outputchannel_forwarder:
                                    if session.outputchannel_forwarder.send(frame):
                                        session.outputchannel_frame_count += 1
                                levels = band.get('levels', [])
                                levels_str = _format_levels(levels)
                                info(f"[STREAM] PScan: {len(frame)}B{levels_str}", LogTag.STREAM)

                except Exception as e:
                    info(f"[STREAM] 推送错误: {e}", LogTag.STREAM)
                    break

            session.push_running = False
            session._stop_event.clear()
            if band_collector:
                band_collector.clear()
            # 从活跃客户端列表移除
            if session.streamsrc_client:
                with self._clients_lock:
                    if session.streamsrc_client in self._clients:
                        self._clients.remove(session.streamsrc_client)
            info(f"[STREAM] 推送线程结束: taskid={session.taskid}", LogTag.STREAM)

        session.push_thread = threading.Thread(target=push_loop, daemon=True)
        session.push_thread.start()

    def push_frame_to_session(self, session: StreamSession, frame: bytes):
        """推送帧到 session"""
        if not session.streamsrc_client:
            warning(f"[STREAM] push_frame_to_session: session无客户端", LogTag.STREAM)
            return

        try:
            session.streamsrc_client.sendall(frame)
            info(f"[STREAM] push_frame_to_session: {len(frame)}B{frame}", LogTag.STREAM)
        except Exception:
            warning(f"[STREAM] push_frame_to_session: 发送帧失败", LogTag.STREAM)
            if self._session_manager:
                self._session_manager.close_session(session)

    def remove_client(self, client: socket.socket):
        """从活跃客户端列表移除（用于 close_session 时清理）"""
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)
                info(f"[STREAM] remove_client: 已从 _clients 移除", LogTag.STREAM)