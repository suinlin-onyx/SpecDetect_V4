"""设备管理服务"""
from typing import Dict, Any, Optional
from ..device_client import DeviceClient
from utils.logger import get_logger

logger = get_logger('atom.device')


class DeviceService:
    """设备管理服务"""

    def __init__(self, device_client: DeviceClient):
        self.device_client = device_client
        self.connected: bool = False

    async def connect(self) -> Dict[str, Any]:
        """连接设备"""
        try:
            self.connected = await self.device_client.connect()
            return {'success': True, 'message': '设备连接成功'}
        except Exception as e:
            logger.error(f"设备连接失败: {e}")
            return {'success': False, 'message': str(e)}

    async def disconnect(self) -> Dict[str, Any]:
        """断开设备连接"""
        try:
            await self.device_client.disconnect()
            self.connected = False
            return {'success': True, 'message': '设备断开成功'}
        except Exception as e:
            logger.error(f"设备断开失败: {e}")
            return {'success': False, 'message': str(e)}

    async def get_status(self) -> Dict[str, Any]:
        """获取设备状态"""
        return {
            'connected': self.connected,
            'host': self.device_client.host,
            'port': self.device_client.port
        }
