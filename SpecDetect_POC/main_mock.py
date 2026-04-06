"""虚拟设备入口"""
import sys
import os
import asyncio
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.mock_device.tcp_server import MockDeviceServer, DeviceCapabilities
from config.settings import SERVICES
from utils.logger import setup_logger

logger = setup_logger('mock')


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='虚拟设备服务')
    parser.add_argument('--device', '-d', type=str, default='MS950',
                        choices=['MD1000', 'MS845', 'MS950', 'MS970'],
                        help='设备类型 (默认: MS950)')
    parser.add_argument('--scenario', '-s', type=str, default='normal',
                        choices=['normal', 'interference', 'abnormal', 'boundary', 'stress'],
                        help='模拟场景 (默认: normal)')
    args = parser.parse_args()

    config = SERVICES['mock_device']
    server = MockDeviceServer(
        host=config['host'],
        port=config['port'],
        scenario=args.scenario,
        device_type=args.device
    )

    logger.info(f"启动虚拟设备: {config['host']}:{config['port']}")
    logger.info(f"设备类型: {args.device} ({DeviceCapabilities.get_capabilities(args.device)['name']})")
    logger.info(f"模拟场景: {args.scenario}")

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("收到停止信号，关闭虚拟设备")
    except Exception as e:
        logger.error(f"虚拟设备异常退出: {e}")


if __name__ == '__main__':
    main()
