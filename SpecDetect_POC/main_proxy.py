"""代理服务入口

提供SOAP接口，将请求转发到原子服务
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

    logger.info(f"启动代理服务: {config['host']}:{config['port']}")
    logger.info(f"SOAP接口: POST /soap")
    logger.info(f"可视化控制台: http://localhost:{config['port']}/dashboard")
    logger.info(f"原子服务: {SERVICES['atom']['host']}:{SERVICES['atom']['port']}")

    app.run(
        host=config['host'],
        port=config['port'],
        debug=config.get('debug', False)
    )


if __name__ == '__main__':
    main()
