#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
streamsrc 端口抓包工具
监听 18012 端口，捕获设备连接和数据
"""

import socket
import struct
import threading
import time
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def parse_rmcp_frame(data):
    """解析 RMCPTP 帧"""
    if len(data) < 18:
        return None

    try:
        dwLength = struct.unpack('<I', data[0:4])[0]
        tmStamp = struct.unpack('<Q', data[4:12])[0]
        version = struct.unpack('<B', data[12:13])[0] if len(data) >= 13 else 0
        msgType = struct.unpack('<B', data[13:14])[0] if len(data) >= 14 else 0
        flags = struct.unpack('<B', data[14:15])[0] if len(data) >= 15 else 0
        checksum = struct.unpack('<H', data[16:18])[0] if len(data) >= 18 else 0

        return {
            'dwLength': dwLength,
            'tmStamp': tmStamp,
            'version': version,
            'msgType': msgType,
            'flags': flags,
            'checksum': checksum,
            'payload': data[18:]
        }
    except Exception as e:
        return None

def handle_client(client_socket, client_addr, log_file):
    """处理客户端连接"""
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Client connected: {client_addr}")

    client_socket.settimeout(30.0)
    recv_buffer = b''
    frame_count = 0

    try:
        while True:
            try:
                chunk = client_socket.recv(8192)
                if not chunk:
                    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Client disconnected: {client_addr}")
                    break

                recv_buffer += chunk
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                # 解析所有完整帧
                while len(recv_buffer) >= 18:
                    dwLength = struct.unpack('<I', recv_buffer[0:4])[0]
                    if len(recv_buffer) < dwLength:
                        break

                    frame_data = recv_buffer[:dwLength]
                    recv_buffer = recv_buffer[dwLength:]
                    frame_count += 1

                    # 解析帧
                    parsed = parse_rmcp_frame(frame_data)
                    if parsed:
                        msg_type_names = {0: 'DATA', 1: 'KEEPALIVE', 2: 'ANNOUNCE',
                                         3: 'REQUEST', 4: 'RESPONSE', 5: 'CONFIRM',
                                         6: 'REPLY', 7: 'ABORT', 90: 'XML_REQUEST',
                                         91: 'XML_RESPONSE', 92: 'HEARTBEAT'}
                        msg_name = msg_type_names.get(parsed['msgType'], f'UNKNOWN({parsed["msgType"]})')

                        print(f"[{timestamp}] Frame #{frame_count}: dwLength={parsed['dwLength']}, "
                              f"nMsgType={parsed['msgType']}({msg_name}), "
                              f"tmStamp={parsed['tmStamp']}")

                        # 记录到文件
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{timestamp}] Frame #{frame_count}: "
                                   f"dwLength={parsed['dwLength']}, "
                                   f"nMsgType={parsed['msgType']}({msg_name}), "
                                   f"tmStamp={parsed['tmStamp']}, "
                                   f"payload_hex={frame_data[18:min(18+64, len(frame_data))].hex()}\n")

                        # 如果是 DATA 帧，打印更多信息
                        if parsed['msgType'] == 0:
                            payload = parsed['payload']
                            if len(payload) >= 23:
                                leader = struct.unpack('<i', payload[0:4])[0]
                                ver = payload[4] if len(payload) > 4 else 0
                                stc = struct.unpack('<I', payload[5:9])[0] if len(payload) >= 9 else 0
                                print(f"    >> DATA frame: leader=0x{leader:08x}, ver={ver}, stc={stc}")

            except socket.timeout:
                # 发送心跳探测
                try:
                    client_socket.sendall(b'\x00')
                    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Heartbeat sent to {client_addr}")
                except:
                    break

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Error handling {client_addr}: {e}")
    finally:
        client_socket.close()
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Connection closed: {client_addr}")

def start_sniffer(host='0.0.0.0', port=18012):
    """启动抓包监听"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/streamsrc_capture_{timestamp}.log'
    os.makedirs('logs', exist_ok=True)

    print(f"=" * 60)
    print(f"streamsrc 抓包工具")
    print(f"=" * 60)
    print(f"监听地址: {host}:{port}")
    print(f"日志文件: {log_file}")
    print(f"按 Ctrl+C 停止")
    print(f"=" * 60)

    # 初始化日志文件
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"streamsrc Capture Log - {datetime.now()}\n")
        f.write(f"=" * 60 + "\n")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 监听启动成功")

        while True:
            try:
                server_socket.settimeout(1.0)
                try:
                    client_socket, client_addr = server_socket.accept()
                except socket.timeout:
                    continue

                # 为每个客户端创建独立线程
                thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_addr, log_file),
                    daemon=True
                )
                thread.start()

            except KeyboardInterrupt:
                print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 停止监听...")
                break

    except Exception as e:
        print(f"错误: {e}")
    finally:
        server_socket.close()
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 监听已停止")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='streamsrc 抓包工具')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=18012, help='监听端口 (默认: 18012)')
    args = parser.parse_args()

    start_sniffer(args.host, args.port)