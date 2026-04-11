"""SOAP Proxy 入口"""
import sys
import os

# 添加项目根目录到路径（支持直接运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soap_proxy.proxy import create_proxy_app
from soap_proxy.config import PROXY_HOST, PROXY_PORT, ATOM_HOST, ATOM_PORT, LOG_DIR


def main():
    """启动 SOAP Proxy"""
    app = create_proxy_app(
        atom_host=ATOM_HOST,
        atom_port=ATOM_PORT,
        log_dir=LOG_DIR
    )

    print(f"=" * 60)
    print(f"SOAP Proxy 启动 (透明转发模式)")
    print(f"监听地址: {PROXY_HOST}:{PROXY_PORT}")
    print(f"转发目标: http://{ATOM_HOST}:{ATOM_PORT}/")
    print(f"日志目录: {LOG_DIR}/")
    print(f"=" * 60)

    app.run(
        host=PROXY_HOST,
        port=PROXY_PORT,
        debug=False,
        threaded=True
    )


if __name__ == '__main__':
    main()
