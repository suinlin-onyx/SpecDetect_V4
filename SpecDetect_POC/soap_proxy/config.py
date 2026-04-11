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

# 日志配置
LOG_DIR = "logs/soap_proxy"
LOG_FILE = "soap_proxy.log"
LOG_FORMAT = "[{timestamp}] {level} - {message}"
