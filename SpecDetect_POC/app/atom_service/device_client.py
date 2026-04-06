"""设备通信客户端"""
import asyncio
from typing import Optional
from .protocol_builder import RMCPTPBuilder
from .protocol_parser import RMCPTPParser
from utils.exceptions import DeviceConnectionError, DeviceTimeoutError
from utils.logger import get_logger

logger = get_logger('atom.client')


class DeviceClient:
    """设备通信客户端（TCP）"""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.parser = RMCPTPParser()
        self.builder = RMCPTPBuilder()

    async def connect(self) -> bool:
        """
        建立TCP连接

        Returns:
            是否连接成功
        """
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )
            logger.info(f"成功连接到设备 {self.host}:{self.port}")
            return True
        except asyncio.TimeoutError:
            raise DeviceTimeoutError(f"连接设备超时: {self.host}:{self.port}")
        except Exception as e:
            raise DeviceConnectionError(f"连接设备失败: {e}")

    async def disconnect(self):
        """断开连接"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            logger.info(f"已断开与设备 {self.host}:{self.port} 的连接")

    async def send_command(self, frame: bytes) -> bool:
        """
        发送命令帧

        Args:
            frame: RMCPTP帧字节数据

        Returns:
            是否发送成功
        """
        if not self.writer:
            raise DeviceConnectionError("未建立连接")

        try:
            self.writer.write(frame)
            await asyncio.wait_for(self.writer.drain(), timeout=self.timeout)
            logger.debug(f"发送命令帧: {len(frame)} 字节")
            return True
        except asyncio.TimeoutError:
            raise DeviceTimeoutError("发送命令超时")
        except Exception as e:
            raise DeviceConnectionError(f"发送命令失败: {e}")

    async def receive_response(self, expect_length: int = 1024) -> tuple:
        """
        接收响应帧

        Args:
            expect_length: 期望接收的字节数

        Returns:
            (头部信息, 业务数据, 原始帧数据)
        """
        if not self.reader:
            raise DeviceConnectionError("未建立连接")

        try:
            # 先读取帧头
            header_data = await asyncio.wait_for(
                self.reader.read(RMCPTPParser.HEADER_SIZE),
                timeout=self.timeout
            )

            if not header_data:
                raise DeviceConnectionError("连接已关闭")

            # 解析帧头
            header_info, _ = self.parser.parse_frame(header_data)

            # 根据长度读取业务数据
            payload_length = header_info['dw_length']
            payload_data = b''
            if payload_length > 0:
                payload_data = await asyncio.wait_for(
                    self.reader.read(payload_length),
                    timeout=self.timeout
                )

            # 记录原始帧数据
            raw_frame = header_data + payload_data

            logger.debug(f"接收响应帧: type={hex(header_info['n_data_type'])}, length={payload_length}")
            return header_info, payload_data, raw_frame

        except asyncio.TimeoutError:
            raise DeviceTimeoutError("接收响应超时")
        except Exception as e:
            raise DeviceConnectionError(f"接收响应失败: {e}")

    async def send_and_receive(self, frame: bytes) -> tuple:
        """
        发送命令并接收响应

        Args:
            frame: RMCPTP帧字节数据

        Returns:
            (头部信息, 业务数据, 原始响应帧数据)
        """
        await self.send_command(frame)
        return await self.receive_response()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
