# -*- coding: utf-8 -*-
"""
实验性功能: 使用本地 Mock 设备测试 soap_to_rmcp_direct

由于无法直接连接真实设备 (超时拒绝)，改用本地 Mock 设备测试
"""

import sys
import os
import socket
import struct
import time
import threading
import asyncio

# 导入 mock device
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.mock_device.tcp_server import MockDeviceServer
from experimental.soap_to_rmcp_direct import build_rmcp_frame, build_action_xml, parse_rmcp_response


# 配置
MOCK_HOST = '127.0.0.1'
MOCK_PORT = 9997  # 使用不同端口避免冲突


def start_mock_device(port):
    """启动本地 Mock 设备"""
    from config.settings import SERVICES

    config = SERVICES.get('mock_device', {'host': '127.0.0.1', 'port': 9000})
    config['port'] = port

    server = MockDeviceServer(
        host=config['host'],
        port=port,
        device_type='MS845'
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.start())


def send_and_receive(frame_bytes, host=MOCK_HOST, port=MOCK_PORT, timeout=5.0):
    """发送 RMCP 帧并接收响应"""
    start_time = time.time()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.send(frame_bytes)

            # 接收响应
            response = b''
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    if time.time() - start_time > timeout:
                        break
                except socket.timeout:
                    break

            elapsed = time.time() - start_time
            return response, elapsed
    except Exception as e:
        return None, time.time() - start_time, str(e)


def test_with_mock_device():
    """使用 Mock 设备测试"""

    # 启动 mock device 在后台
    mock_thread = threading.Thread(target=start_mock_device, args=(MOCK_PORT,), daemon=True)
    mock_thread.start()
    time.sleep(2)  # 等待设备启动

    print(f"Mock device started on {MOCK_HOST}:{MOCK_PORT}")

    # 测试 B_FScan
    soap_fscan = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    print("\n=== Testing B_FScan ===")

    # 1. SOAP → Action XML
    action_xml = build_action_xml(soap_fscan)
    print(f"Action XML:\n{action_xml}")

    # 2. Action XML → RMCP Frame
    rmcp_frame = build_rmcp_frame(action_xml)
    print(f"\nRMCP Frame ({len(rmcp_frame)} bytes): {rmcp_frame.hex()[:80]}...")

    # 3. 发送到 mock device
    print(f"\nSending to mock device at {MOCK_HOST}:{MOCK_PORT}...")
    response, elapsed, *extra = send_and_receive(rmcp_frame)

    if response is None:
        error = extra[0] if extra else "Unknown error"
        print(f"Error: {error}")
        return False

    print(f"Response ({len(response)} bytes) in {elapsed:.3f}s")

    # 4. 解析响应
    parsed = parse_rmcp_response(response)
    print(f"Parsed response: {parsed}")

    return True


if __name__ == '__main__':
    test_with_mock_device()
