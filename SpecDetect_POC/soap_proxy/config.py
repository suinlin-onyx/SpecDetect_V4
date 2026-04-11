"""SOAP Proxy 配置"""

# =============================================================================
# SOAP Proxy 配置
# =============================================================================

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8082

# Real Atom 目标地址
ATOM_HOST = "127.0.0.1"
ATOM_PORT = 8282

ATOM_BASE_URL = f"http://{ATOM_HOST}:{ATOM_PORT}"

# 日志配置（使用绝对路径，确保无论从哪个目录运行都能正确保存）
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs", "soap_proxy")
LOG_FILE = "soap_proxy.log"
LOG_FORMAT = "[{timestamp}] {level} - {message}"
