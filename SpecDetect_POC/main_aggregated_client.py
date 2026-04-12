"""聚合客户端入口

【功能说明】
本模块是聚合客户端（Mock客户端），用于：
1. 替代真实客户端向 Mock Atom 发送 SOAP 请求
2. 验证 Proxy-A 链路可行性（Client -> Proxy-A -> Mock Atom）
3. 聚合多个原子服务的请求

【与 RXAtomTestTool3.exe 的关系】
- RXAtomTestTool3.exe: 真实客户端
- main_aggregated_client.py: 聚合客户端（Mock客户端）
- 两者等效，都向 Atom 发送 SOAP 请求

【架构定位 - Proxy-A 链路】
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 聚合客户端   │ ──▶ │ Proxy-A     │ ──▶ │ Mock Atom   │
│ main_agg    │     │ :8080       │     │ :9090       │
└─────────────┘     └─────────────┘     └─────────────┘

使用方式:
    python main_aggregated_client.py
    # 启动后访问: http://localhost:8080/dashboard
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from app.proxy_service.routes import proxy_bp
from config.settings import SERVICES
from utils.logger import setup_logger

logger = setup_logger('proxy')


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    CORS(app)

    # 注册蓝图
    app.register_blueprint(proxy_bp)

    # 获取静态文件目录
    static_dir = os.path.dirname(os.path.abspath(__file__))

    @app.route('/')
    def index():
        """首页"""
        return send_from_directory(static_dir, 'dashboard.html')

    @app.route('/dashboard')
    def dashboard():
        """Dashboard页面"""
        return send_from_directory(static_dir, 'dashboard.html')

    @app.route('/dashboard.html')
    def dashboard_html():
        """Dashboard页面"""
        return send_from_directory(static_dir, 'dashboard.html')

    return app


def main():
    """主函数"""
    config = SERVICES['proxy']
    app = create_app()

    logger.info(f"启动聚合客户端: {config['host']}:{config['port']}")
    logger.info(f"SOAP接口: POST /soap")
    logger.info(f"可视化控制台: http://localhost:{config['port']}/dashboard")
    logger.info(f"原子服务: {SERVICES['atom']['host']}:{SERVICES['atom']['port']}")

    app.run(
        host=config['host'],
        port=config['port'],
        debug=config.get('debug', False),
        use_reloader=False
    )


if __name__ == '__main__':
    main()
