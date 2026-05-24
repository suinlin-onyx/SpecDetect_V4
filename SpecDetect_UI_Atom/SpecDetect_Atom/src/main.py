# -*- coding: utf-8 -*-
"""
SGAtom (SpecGuardAtom) 服务入口

用法:
    python main.py
    python main.py --config config/settings.json
"""

import sys
import os
import signal
import argparse
import ctypes

# 添加 src 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _show_error_and_exit(title: str, message: str, exit_code: int = 1):
    """显示错误对话框，按任意键后退出"""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        print(f'\n{title}\n{message}', file=sys.stderr)
        input('\n按任意键退出...')
    sys.exit(exit_code)

# 初始化日志（最早，避免后续 import 时日志未初始化）
if getattr(sys, 'frozen', False):
    # exe 模式：日志在 exe 同级 logs 目录
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    log_dir = os.path.join(exe_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_level = os.environ.get('ATOM_LOG_LEVEL', 'INFO')
else:
    # 开发模式：日志在 ./logs
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_level = 'DEBUG'

from log.logger import Logger, info, error, LogTag
Logger.init(log_dir=log_dir, log_level=log_level)

# 导入服务（在日志初始化之后）
from atom.service import AtomService
from license.manager import verify_license


def main():
    parser = argparse.ArgumentParser(description='SpecDetect_Atom 服务')
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='配置文件路径'
    )
    args = parser.parse_args()

    # 确定配置文件路径
    config_file = args.config
    if config_file is None:
        if getattr(sys, 'frozen', False):
            # exe 模式
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            exe_config = os.path.join(exe_dir, 'config', 'settings.json')
            if os.path.exists(exe_config):
                config_file = exe_config
            else:
                # 查找当前工作目录的 config
                cwd_config = os.path.join(os.getcwd(), 'config', 'settings.json')
                if os.path.exists(cwd_config):
                    config_file = cwd_config
                else:
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    config_file = os.path.join(base_dir, 'config', 'settings.json')
        else:
            # 开发模式
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_file = os.path.join(base_dir, 'config', 'settings.json')

    # 许可证验证
    license_dir = os.path.dirname(os.path.abspath(config_file))
    license_path = os.path.join(license_dir, 'license.dat')
    if not verify_license(license_path):
        error("设备授权验证失败：当前设备未授权运行本软件，请联系管理员", LogTag.ATOM)
        _show_error_and_exit(
            title='SpecDetect Atom - 设备授权验证失败',
            message='当前设备未授权运行本软件，请联系管理员。\n\n按确定键退出...'
        )

    # 创建服务
    service = AtomService(config_file)

    # 信号处理
    def signal_handler(signum, frame):
        info(f"收到信号 {signum}，停止服务...", LogTag.ATOM)
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动服务
    try:
        service.start()
        info("Atom 服务运行中，按 Ctrl+C 停止", LogTag.ATOM)

        # 等待
        while True:
            import time
            time.sleep(1)

    except KeyboardInterrupt:
        info("收到键盘中断", LogTag.ATOM)
    except Exception as e:
        error(f"服务异常: {e}", LogTag.ATOM)
    finally:
        service.stop()


if __name__ == '__main__':
    main()
