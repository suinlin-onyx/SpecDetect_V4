# -*- coding: utf-8 -*-
"""
日志模块

提供统一的日志输出，支持：
- 按业务模块分 tag
- 可配置日志级别
- 输出到文件和控制台
"""

import os
import sys
import io
from datetime import datetime
from enum import Enum
from typing import Optional

# 设置输出编码 (Windows)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


class LogLevel(Enum):
    """日志级别"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class LogTag(Enum):
    """日志 tag，按业务模块分类"""
    ATOM = "ATOM"       # 主服务日志
    STREAM = "STREAM"   # streamsrc 服务器
    SOAP = "SOAP"       # SOAP 处理
    SESSION = "SESSION" # Session 管理
    RMCP = "RMCP"       # RMCP 通信
    PARSE = "PARSE"     # 数据解析
    DEBUG = "DEBUG"     # 帧级别调试
    FILTER = "FILTER"   # 数据过滤


class Logger:
    """日志器"""

    _instance: Optional['Logger'] = None

    def __init__(self, log_dir: str = "./logs", log_level: str = "INFO"):
        self.log_dir = log_dir
        self.log_level = LogLevel[log_level.upper()]
        self.log_file = None
        self.log_file_handle = None

        # 创建日志目录
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(log_dir, f"atom_{timestamp}.log")
            try:
                self.log_file_handle = open(self.log_file, 'w', encoding='utf-8')
                # 验证文件是否可写
                self.log_file_handle.write(f"[INIT] Log file created: {self.log_file}\n")
                self.log_file_handle.flush()
            except Exception as e:
                print(f"[LOGGER ERROR] Failed to create log file: {e}", flush=True)
                self.log_file_handle = None

    @classmethod
    def get_instance(cls) -> 'Logger':
        """获取单例"""
        return cls._instance

    @classmethod
    def init(cls, log_dir: str = "./logs", log_level: str = "INFO") -> 'Logger':
        """初始化日志器"""
        cls._instance = cls(log_dir, log_level)
        return cls._instance

    def set_level(self, level: str):
        """设置日志级别"""
        self.log_level = LogLevel[level.upper()]

    def _should_log(self, level: LogLevel) -> bool:
        """判断是否应该记录"""
        return level.value >= self.log_level.value

    def log(self, message: str, tag: LogTag = LogTag.ATOM, level: LogLevel = LogLevel.INFO):
        """输出日志

        Args:
            message: 日志消息
            tag: 日志 tag
            level: 日志级别
        """
        if not self._should_log(level):
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        line = f"[{timestamp}] [{tag.value:6}] {message}"

        # 输出到控制台
        try:
            print(line, flush=True)
        except Exception as e:
            pass

        # 输出到文件
        if self.log_file_handle:
            try:
                self.log_file_handle.write(line + '\n')
                self.log_file_handle.flush()
            except Exception as e:
                try:
                    print(f"[LOGGER ERROR] Write failed: {e}", flush=True)
                except Exception:
                    pass

    def debug(self, message: str, tag: LogTag = LogTag.DEBUG):
        self.log(message, tag, LogLevel.DEBUG)

    def info(self, message: str, tag: LogTag = LogTag.ATOM):
        self.log(message, tag, LogLevel.INFO)

    def warning(self, message: str, tag: LogTag = LogTag.ATOM):
        self.log(message, tag, LogLevel.WARNING)

    def error(self, message: str, tag: LogTag = LogTag.ATOM):
        self.log(message, tag, LogLevel.ERROR)

    def close(self):
        """关闭日志文件"""
        if self.log_file_handle:
            self.log_file_handle.close()
            self.log_file_handle = None


def _normalize_tag(tag) -> LogTag:
    """将 tag 转换为 LogTag enum"""
    if isinstance(tag, LogTag):
        return tag
    if isinstance(tag, str):
        try:
            return LogTag[tag.upper()]
        except KeyError:
            return LogTag.ATOM
    return LogTag.ATOM


def log(message: str, tag="ATOM", level: str = "INFO"):
    """全局日志函数

    Args:
        message: 日志消息
        tag: 日志 tag (LogTag enum 或字符串)
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
    """
    logger = Logger.get_instance()
    if logger is None:
        print(f"[FALLBACK] {message}", flush=True)
        return

    log_tag = _normalize_tag(tag)
    log_level = LogLevel[level.upper()]
    logger.log(message, log_tag, log_level)


def debug(message: str, tag="DEBUG"):
    log(message, tag, "DEBUG")


def info(message: str, tag="ATOM"):
    log(message, tag, "INFO")


def warning(message: str, tag="ATOM"):
    log(message, tag, "WARNING")


def error(message: str, tag="ATOM"):
    log(message, tag, "ERROR")
