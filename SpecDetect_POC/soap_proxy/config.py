"""SOAP Proxy 配置"""

# =============================================================================
# SOAP Proxy 配置
# =============================================================================

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8284

# Real Atom 目标地址
ATOM_HOST = "127.0.0.1"
ATOM_PORT = 8282

ATOM_BASE_URL = f"http://{ATOM_HOST}:{ATOM_PORT}"

# SINK模式outputchannel使用的本机IP（供设备连接）
OUTPUT_HOST = "127.0.0.1"

# 日志配置（使用绝对路径，确保无论从哪个目录运行都能正确保存）
import os
# soap_proxy 目录的父目录
SOAP_PROXY_DIR = os.path.dirname(os.path.abspath(__file__))
# 日志保存在 soap_proxy/logs/ 目录下
LOG_DIR = os.path.join(SOAP_PROXY_DIR, "logs")
# SOAP → RMCP 转换输出目录
CONVERSION_OUTPUT_DIR = os.path.join(SOAP_PROXY_DIR, "conversion_output")
LOG_FILE = "soap_proxy.log"
LOG_FORMAT = "[{timestamp}] {level} - {message}"
