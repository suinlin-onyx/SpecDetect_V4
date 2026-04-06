"""协议Hook系统

用于记录请求在各层之间的转换过程
"""
import uuid
import time
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from contextvars import ContextVar

# 创建专用 logger
logger = logging.getLogger('protocol.hook')
logger.setLevel(logging.INFO)

# 确保 logs 目录存在
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 文件 handler - 持久化到 logs/protocol.log
file_handler = logging.FileHandler(os.path.join(log_dir, 'protocol.log'), encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - protocol.hook - %(message)s', datefmt='%H:%M:%S'))

# 添加 handler
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 异步上下文变量（协程安全）
_current_context: ContextVar[Optional['ProtocolContext']] = ContextVar(
    'current_context', default=None
)


@dataclass
class ProtocolFrame:
    """帧记录"""
    direction: str          # "send" 或 "recv"
    frame_type: str         # "RMCPTP_CMD" / "RMCPTP_RESP" / "SOAP"
    hex_data: str           # 十六进制数据
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProtocolContext:
    """请求上下文，贯穿所有层次"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    layers: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    frames: List[ProtocolFrame] = field(default_factory=list)

    def add_layer(self, layer_name: str, data: Dict[str, Any]):
        """各层添加自己的数据（追加模式）"""
        if layer_name not in self.layers:
            self.layers[layer_name] = []
        self.layers[layer_name].append(data)

    def add_frame(self, direction: str, frame_type: str, hex_data: str):
        """记录帧"""
        # 限制十六进制字符串长度，避免日志过大
        self.frames.append(ProtocolFrame(
            direction=direction,
            frame_type=frame_type,
            hex_data=hex_data[:500] if hex_data else ''
        ))

    def to_summary(self) -> str:
        """生成完整日志摘要"""
        elapsed = time.time() - self.timestamp
        lines = [f"[{self.request_id}] 耗时: {elapsed*1000:.1f}ms"]

        for layer, data_list in self.layers.items():
            for data in data_list:
                lines.append(f"  ├─ {layer}: {data}")

        for frame in self.frames:
            direction_symbol = "→" if frame.direction == "send" else "←"
            lines.append(f"     {direction_symbol} {frame.direction.upper()} {frame.frame_type}: {frame.hex_data}")

        return "\n".join(lines)


class HookManager:
    """Hook管理器（单例）"""
    _instance = None

    def __init__(self):
        self.enabled = True
        self._logger = logger

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HookManager()
        return cls._instance

    def start_context(self) -> ProtocolContext:
        """开始新的请求上下文"""
        ctx = ProtocolContext()
        _current_context.set(ctx)
        self._logger.info(f"[{ctx.request_id}] ===== Hook开始 =====")
        return ctx

    def get_context(self) -> Optional[ProtocolContext]:
        """获取当前上下文"""
        return _current_context.get()

    def end_context(self) -> Optional[ProtocolContext]:
        """结束上下文并输出日志"""
        ctx = _current_context.get()
        if ctx and self.enabled:
            summary = ctx.to_summary()
            self._logger.info(summary)
            # 确保日志立即写入文件
            for handler in self._logger.handlers:
                handler.flush()
        _current_context.set(None)
        return ctx

    def log_layer(self, layer_name: str, data: Dict[str, Any]):
        """记录层数据"""
        ctx = self.get_context()
        if ctx:
            ctx.add_layer(layer_name, data)
            self._logger.debug(f"[{ctx.request_id}] {layer_name}: {data}")

    def log_frame(self, direction: str, frame_type: str, hex_data: str):
        """记录帧"""
        ctx = self.get_context()
        if ctx:
            ctx.add_frame(direction, frame_type, hex_data)
            # 帧数据量大，用debug级别
            preview = hex_data[:100] + "..." if len(hex_data) > 100 else hex_data
            self._logger.debug(f"[{ctx.request_id}] {direction.upper()} {frame_type}: {preview}")


def bytes_to_hex(data: bytes) -> str:
    """字节数据转十六进制字符串"""
    if not data:
        return ''
    return ' '.join(f'{b:02X}' for b in data)
