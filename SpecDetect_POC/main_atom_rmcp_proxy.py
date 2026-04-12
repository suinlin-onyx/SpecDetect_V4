#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mock Atom - 转发到 rmcp_proxy 版本

此版本将 SOAP 请求转发到 rmcp_proxy (9996)

使用方式:
    python main_atom_rmcp_proxy.py
"""

import sys
import os
import socket
import threading

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 在导入 main_atom 之前，替换 settings
import config.settings as old_settings
import config.settings_rmcp_proxy as new_settings

# 替换 SERVICES
old_settings.SERVICES = new_settings.SERVICES
old_settings.PROTOCOL = new_settings.PROTOCOL

# 导入 Flask app 和相关函数
from main_atom import app, dispatch_soap_operation, build_soap_response, generate_taskid, _parse_real_atom_request
from utils.logger import setup_logger

logger = setup_logger('atom.rmcp_proxy')

# streamsrc 配置
STREAMSRC_HOST = '0.0.0.0'
STREAMSRC_PORT = 18012

# 全局 streamsrc 服务器控制
streamsrc_running = False
streamsrc_server = None


class StreamSrcServer:
    """streamsrc TCP 服务器 - 监听设备连接"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.client_threads = []
        self.lock = threading.Lock()

    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            logger.info(f"streamsrc 服务器已启动: {self.host}:{self.port}")
            logger.info(f"等待设备连接 streamsrc ({self.host}:{self.port})...")

            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    try:
                        client_socket, client_addr = self.server_socket.accept()
                    except socket.timeout:
                        continue

                    logger.info(f"设备已连接 streamsrc: {client_addr}")
                    # 为每个客户端创建独立线程处理
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_addr),
                        daemon=True
                    )
                    with self.lock:
                        self.client_threads.append(thread)
                    thread.start()
                except Exception as e:
                    if self.running:
                        logger.error(f"接受连接错误: {e}")
        except Exception as e:
            logger.error(f"streamsrc 服务器启动失败: {e}")
        finally:
            self.stop()

    def _handle_client(self, client_socket, client_addr):
        """处理设备客户端连接"""
        try:
            client_socket.settimeout(30.0)
            while self.running:
                try:
                    data = client_socket.recv(8192)
                    if not data:
                        logger.info(f"设备断开连接: {client_addr}")
                        break

                    # 记录接收到的数据
                    hex_data = data.hex()
                    logger.info(f"收到设备数据 from {client_addr}: {len(data)} bytes")
                    logger.debug(f"数据内容: {hex_data[:200]}...")

                    # 解析 RMCPTP 帧（如果可解析）
                    self._parse_and_log_data(data)

                except socket.timeout:
                    # 30秒无数据，发送心跳探测
                    try:
                        client_socket.send(b'\x00')
                    except:
                        break
                except Exception as e:
                    logger.error(f"接收数据错误: {e}")
                    break
        except Exception as e:
            logger.error(f"客户端处理错误: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            logger.info(f"客户端连接已关闭: {client_addr}")

    def _parse_and_log_data(self, data: bytes):
        """解析并记录 RMCPTP 数据"""
        if len(data) < 18:
            logger.debug(f"数据太短无法解析帧头: {len(data)} bytes")
            return

        try:
            import struct
            # 解析 RMCPTP 帧头
            # dwLength(4) + tmStamp(8) + nVersion(2) + nMsgType(1) + nFlags(1) + nCheckSum(2) = 18
            if len(data) >= 18:
                dw_length = struct.unpack('<I', data[0:4])[0]
                tm_stamp = struct.unpack('<Q', data[4:12])[0]
                n_version = struct.unpack('>H', data[12:14])[0]
                n_msg_type = data[14]
                n_flags = data[15]

                logger.info(f"RMCPTP帧: len={dw_length}, time={tm_stamp}, ver=0x{n_version:04x}, type=0x{n_msg_type:02x}, flags=0x{n_flags:02x}")

                # 根据 nMsgType 记录数据类型
                if n_msg_type == 0x00:
                    logger.info(f"  -> 数据帧 (DATA)")
                elif n_msg_type == 0x06:
                    logger.info(f"  -> 响应帧 (RESPONSE)")
                elif n_msg_type == 0x5A:
                    logger.info(f"  -> 请求帧 (REQUEST)")
                else:
                    logger.info(f"  -> 类型未知")
        except Exception as e:
            logger.debug(f"帧解析失败: {e}")

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("streamsrc 服务器已停止")


def start_streamsrc_server():
    """启动 streamsrc 服务器（后台线程）"""
    global streamsrc_running, streamsrc_server
    if streamsrc_running:
        logger.warning("streamsrc 服务器已在运行")
        return

    streamsrc_server = StreamSrcServer(STREAMSRC_HOST, STREAMSRC_PORT)
    streamsrc_running = True
    thread = threading.Thread(target=streamsrc_server.start, daemon=True)
    thread.start()
    logger.info(f"streamsrc 服务器已启动 (端口 {STREAMSRC_PORT})")


def add_b_routes():
    """添加 /B_XXX 路由

    这些路由与 Real Atom 兼容，将请求转发到 dispatch_soap_operation
    """
    from flask import request

    # 定义 B_XXX 端点
    b_endpoints = [
        'B_QueryDeviceInfo',
        'B_QueryFaciDevStat',
        'B_StopMeas',
        'B_SglFreqMeas',
        'B_SglFreqDF',
        'B_FScan',
        'B_FScanDF',
        'B_MScan',
        'B_MScanDF',
        'B_PScan',
        'B_WBDF',
    ]

    for endpoint in b_endpoints:
        # 使用动态函数避免闭包问题
        def create_route(name):
            @app.route(f'/{name}', methods=['POST'], endpoint=f'b_{name}')
            def handler():
                xml_data = request.data.decode('utf-8')
                logger.info(f"收到 {name} 请求")

                # 解析 SOAP 请求
                try:
                    from lxml import etree
                    root = etree.fromstring(xml_data.encode('utf-8'))
                except Exception as e:
                    logger.error(f"SOAP XML 解析失败: {e}")
                    return build_soap_response(False, error=f"SOAP XML 解析失败: {e}"), 500, {'Content-Type': 'text/xml; charset=utf-8'}

                # 提取 Body
                SOAP_NS = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/'}
                body = root.find('soap:Body', namespaces=SOAP_NS)
                if body is None or len(body) == 0:
                    return build_soap_response(False, error="未找到 SOAP Body"), 400, {'Content-Type': 'text/xml; charset=utf-8'}

                # 获取 requestbody
                requestbody = body[0]
                soap_action = request.headers.get('SOAPAction', name)

                # 解析请求
                operation_name, params = _parse_real_atom_request(requestbody, soap_action)

                # 如果解析的操作名为空，使用路由名称
                if not operation_name:
                    operation_name = name

                logger.info(f"操作: {operation_name}, 参数: {params}")

                # 分发操作
                result = dispatch_soap_operation(operation_name, params)

                # 构建响应
                is_success = result.get('success', True)
                error_msg = result.get('error')

                if not is_success and error_msg:
                    response = build_soap_response(
                        success=False,
                        error=error_msg,
                        error_code=result.get('error_code')
                    )
                else:
                    response = build_soap_response(
                        success=True,
                        data=result
                    )

                return response, 200, {'Content-Type': 'text/xml; charset=utf-8'}

            return handler

        # 注册路由
        create_route(endpoint)
        logger.info(f"注册端点: /{endpoint}")


def main():
    """主函数"""
    from config.settings_rmcp_proxy import SERVICES
    config = SERVICES['atom']
    logger.info(f"启动 Mock Atom (rmcp_proxy 模式)")
    logger.info(f"  - SOAP 端口: {config['port']}")
    logger.info(f"  - 设备地址: {config['device_host']}:{config['device_port']}")
    logger.info(f"  - 目标: rmcp_proxy")

    # 启动 streamsrc 服务器（监听设备连接）
    start_streamsrc_server()

    # 添加 B_XXX 路由
    add_b_routes()

    # 启动 Flask
    app.run(
        host='0.0.0.0',
        port=config['port'],
        debug=False,
        threaded=True
    )


if __name__ == '__main__':
    main()
