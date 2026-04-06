"""代理服务入口 - Proxy-B (双Proxy模式)

用于双Proxy并行模式 - Proxy-B (8081) 连接到 Real Atom

使用方式:
    python main_proxy_b.py
    # 启动后访问: http://localhost:8081/dashboard
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置 Proxy-B 模式环境变量（在导入 routes 之前设置）
os.environ['PROXY_MODE'] = 'B'

from flask import Flask, send_from_directory
from flask_cors import CORS
from app.proxy_service.routes import proxy_bp
from config.settings_proxy_b import SERVICES, PROXY_B_CONFIG
from utils.logger import setup_logger

logger = setup_logger('proxy_b')


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

    logger.info(f"启动 Proxy-B: {config['host']}:{config['port']}")
    logger.info(f"SOAP接口: POST /soap")
    logger.info(f"可视化控制台: http://localhost:{config['port']}/dashboard")
    logger.info(f"原子服务 (Real Atom): {SERVICES['atom']['host']}:{SERVICES['atom']['port']}")

    app.run(
        host=config['host'],
        port=config['port'],
        debug=config.get('debug', False),
        use_reloader=False  # 禁用 reloader，避免环境变量丢失
    )


if __name__ == '__main__':
    main()
