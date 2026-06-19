# -*- coding: utf-8 -*-
"""
会话管理器

负责管理所有 StreamSession
"""

import socket
import threading
import time
from typing import Optional, Dict
from .session import StreamSession, SessionState


class SessionManager:
    """会话管理器 - 追踪所有配对的 streamsrc/RMCP 会话"""

    def __init__(self, stale_timeout: int = 30, idle_timeout: int = 30, max_sessions: int = 5):
        self.sessions: Dict[socket.socket, StreamSession] = {}
        self.taskid_to_session: Dict[str, StreamSession] = {}
        self.pending_sessions: list = []  # 按时间顺序排列的 pending session
        self.lock = threading.Lock()

        # 超时配置
        self.stale_timeout = stale_timeout
        self.idle_timeout = idle_timeout
        self.max_sessions = max_sessions

        # 清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False

        # StreamSrcServer 引用（用于 close_session 时清理 _clients）
        self._stream_server = None

    def set_stream_server(self, stream_server):
        """设置 StreamSrcServer 引用"""
        self._stream_server = stream_server

    def start_cleanup_thread(self):
        """启动清理线程"""
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop_cleanup_thread(self):
        """停止清理线程"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2.0)

    def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            self.cleanup_stale()
            time.sleep(1.0)

    def create_pending(self, taskid: str, fscan_params: dict = None) -> StreamSession:
        """创建待关联会话

        Args:
            taskid: 任务 ID
            fscan_params: 扫描参数

        Returns:
            StreamSession 实例
        """
        with self.lock:
            # PENDING session 也计入占用（max_sessions=1 时防止窗口绕过）
            if self.pending_sessions:
                raise RuntimeError("设备使用冲突")

            # 检查 session 数量限制
            active_count = sum(1 for s in self.sessions.values() if s.state == SessionState.ACTIVE)
            if active_count >= self.max_sessions:
                raise RuntimeError(f"达到最大 session 数 {self.max_sessions}")

            # 创建 session（不关联 streamsrc client）
            session = StreamSession(None, taskid, fscan_params)
            session.state = SessionState.PENDING

            # 按 taskid 存储
            self.taskid_to_session[taskid] = session

            # 加入 pending 列表
            self.pending_sessions.append(session)

            return session

    def match_session(self, streamsrc_client: socket.socket) -> Optional[StreamSession]:
        """匹配 pending session

        Args:
            streamsrc_client: streamsrc 客户端 socket

        Returns:
            匹配的 StreamSession 或 None
        """
        with self.lock:
            # 检查是否有 pending session
            if not self.pending_sessions:
                # 无 pending session，创建孤立 session
                session = StreamSession(streamsrc_client, f"orphan_{id(streamsrc_client)}")
                session.state = SessionState.ACTIVE
                self.sessions[streamsrc_client] = session
                return session

            # 按 taskid 匹配（如果有的话）
            # 这里简化处理，直接取最早的 pending session (FIFO)
            session = self.pending_sessions.pop(0)

            # 关联 streamsrc client
            session.streamsrc_client = streamsrc_client
            session.state = SessionState.ACTIVE

            # 存储到 sessions
            self.sessions[streamsrc_client] = session

            return session

    def match_session_by_taskid(self, taskid: str, streamsrc_client: socket.socket) -> Optional[StreamSession]:
        """按 taskid 精确匹配 session

        Args:
            taskid: 任务 ID
            streamsrc_client: streamsrc 客户端 socket

        Returns:
            匹配的 StreamSession 或 None
        """
        with self.lock:
            session = self.taskid_to_session.get(taskid)

            if session and session.state == SessionState.PENDING:
                # 从 pending 列表移除
                if session in self.pending_sessions:
                    self.pending_sessions.remove(session)

                # 关联 streamsrc client
                session.streamsrc_client = streamsrc_client
                session.state = SessionState.ACTIVE

                # 存储到 sessions
                self.sessions[streamsrc_client] = session

                return session

            return None

    def activate_session(self, session: StreamSession):
        """激活 session"""
        with self.lock:
            session.state = SessionState.ACTIVE

    def get_session_by_socket(self, sock: socket.socket) -> Optional[StreamSession]:
        """通过 socket 获取 session"""
        with self.lock:
            return self.sessions.get(sock)

    def get_session_by_taskid(self, taskid: str) -> Optional[StreamSession]:
        """通过 taskid 获取 session"""
        with self.lock:
            return self.taskid_to_session.get(taskid)

    def close_session(self, session: StreamSession):
        """关闭 session（外部调用：B_StopMeas / push_loop 异常退出）"""
        with self.lock:
            self._do_close(session)

    def cleanup_stale(self):
        """清理超时的 pending session 及僵死的 active session"""
        with self.lock:
            current_time = time.time()
            stale_sessions = []

            # 1. 清理超时的 PENDING session
            for session in self.pending_sessions:
                if current_time - session.last_data_time > self.stale_timeout:
                    stale_sessions.append(session)

            for session in stale_sessions:
                self._do_close(session)

            # 2. 清理 ACTIVE 但 push_loop 已死且超时的 session（兜底）
            stale_active = []
            for session in list(self.sessions.values()):
                if session.state == SessionState.ACTIVE:
                    if not session.push_running:
                        if current_time - session.last_data_time > self.idle_timeout:
                            stale_active.append(session)

            for session in stale_active:
                self._do_close(session)

    def _do_close(self, session):
        """内部清理方法（仅供 cleanup_stale 使用）"""
        if session.state == SessionState.CLOSED:
            return
        session.state = SessionState.CLOSING
        client = session.streamsrc_client
        if client and self._stream_server:
            self._stream_server.remove_client(client)
        session.close_all()
        if session in self.pending_sessions:
            self.pending_sessions.remove(session)
        if session.taskid in self.taskid_to_session:
            del self.taskid_to_session[session.taskid]
        for sock, s in list(self.sessions.items()):
            if s == session:
                del self.sessions[sock]
        session.state = SessionState.CLOSED

    def close_all(self):
        """关闭所有 session"""
        with self.lock:
            for session in list(self.sessions.values()):
                session.close_all()
                session.state = SessionState.CLOSED

            for session in self.pending_sessions:
                session.close_all()
                session.state = SessionState.CLOSED

            self.sessions.clear()
            self.taskid_to_session.clear()
            self.pending_sessions.clear()

    def get_active_sessions(self) -> list:
        """获取所有活动状态的 session

        用于 B_QueryFaciDevStat 确定设备是否正在测量

        Returns:
            活动 session 列表（ACTIVE 状态）
        """
        with self.lock:
            active = []
            for session in self.sessions.values():
                if session.state == SessionState.ACTIVE:
                    active.append(session)
            # 也检查 pending sessions（Sink 模式启动时先创建 pending 再激活）
            for session in self.pending_sessions:
                if session.state == SessionState.ACTIVE and session not in active:
                    active.append(session)
            return active
