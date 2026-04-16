#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RMCPTP 设备连接监测工具
监听 1449 端口，捕获设备的所有通信
"""

import socket
import struct
import threading
import time
import sys
import os
from datetime import datetime

def parse_rmcp_frame(data):
    """解析 RMCPTP 帧"""
    if len(data) < 18:
        return None

    try:
        dwLength = struct.unpack('<I', data[0:4])[0]
        tmStamp = struct.unpack('<Q', data[4:12])[0]
        version = data[12] if len(data) >= 13 else 0
        msgType = data[13] if len(data) >= 14 else 0
        flags = data[14] if len(data) >= 15 else 0
        checksum = struct.unpack('<H', data[16:18])[0] if len(data) >= 18 else 0

        msg_type_names = {
            0: 'DATA', 1: 'KEEPALIVE', 2: 'ANNOUNCE', 3: 'REQUEST',
            4: 'RESPONSE', 5: 'CONFIRM', 6: 'REPLY', 7: 'ABORT',
            90: 'XML_REQUEST', 91: 'XML_RESPONSE', 92: 'HEARTBEAT'
        }

        return {
            'dwLength': dwLength,
            'tmStamp': tmStamp,
            'version': version,
            'msgType': msgType,
            'msgTypeName': msg_type_names.get(msgType, f'UNKNOWN({msgType})'),
            'flags': flags,
            'checksum': checksum,
            'payload': data[18:]
        }
    except Exception as e:
        return None

def handle_device(client_socket, client_addr, log_file, connected_event=None):
    """处理设备连接"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"\n[{timestamp}] *** 设备已连接: {client_addr} ***")
    print(f"[{timestamp}] 在同一终端发送 SOAP 请求来触发流数据")

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n[{timestamp}] *** 设备连接: {client_addr} ***\n")

    client_socket.settimeout(60.0)
    recv_buffer = b''
    frame_count = 0
    data_frames = 0

    try:
        while True:
            try:
                chunk = client_socket.recv(8192)
                if not chunk:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    print(f"[{timestamp}] 设备断开: {client_addr}")
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

                    parsed = parse_rmcp_frame(frame_data)
                    if parsed:
                        # 写入日志
                        with open(log_file, 'a', encoding='utf-8') as f:
                            log_line = (f"[{timestamp}] #{frame_count}: "
                                       f"nMsgType={parsed['msgType']}({parsed['msgTypeName']}), "
                                       f"dwLength={parsed['dwLength']}, "
                                       f"payload_hex={frame_data[18:min(18+64, len(frame_data))].hex()}\n")
                            f.write(log_line)

                        # 控制台输出
                        if parsed['msgType'] == 0:  # DATA
                            data_frames += 1
                            payload = parsed['payload']
                            print(f"[{timestamp}] DATA #{frame_count}: dwLength={parsed['dwLength']}, "
                                  f"tmStamp={parsed['tmStamp']}")
                            if len(payload) >= 23:
                                leader = struct.unpack('<i', payload[0:4])[0]
                                ver = payload[4]
                                stc = struct.unpack('<I', payload[5:9])[0]
                                print(f"    >> nBdType={ver}, STC={stc}, leader=0x{leader & 0xFFFFFFFF:08x}")
                        elif parsed['msgType'] == 90:  # XML_REQUEST
                            print(f"[{timestamp}] XML_REQUEST #{frame_count}: dwLength={parsed['dwLength']}")
                            try:
                                xml_text = payload.decode('gb2312', errors='replace')
                                if '<action' in xml_text:
                                    funcid_start = xml_text.find('funcid="')
                                    if funcid_start != -1:
                                        funcid_end = xml_text.find('"', funcid_start + 8)
                                        funcid = xml_text[funcid_start+8:funcid_end]
                                        print(f"    >> funcid={funcid}")
                            except:
                                pass
                        elif parsed['msgType'] == 91:  # XML_RESPONSE
                            print(f"[{timestamp}] XML_RESPONSE #{frame_count}: dwLength={parsed['dwLength']}")
                        elif parsed['msgType'] == 6:  # RESPONSE
                            print(f"[{timestamp}] RESPONSE #{frame_count}: dwLength={parsed['dwLength']}")
                        else:
                            print(f"[{timestamp}] {parsed['msgTypeName']} #{frame_count}: dwLength={parsed['dwLength']}")

                        # 通知主线程（如果设置了事件）
                        if connected_event and parsed['msgType'] == 0:
                            connected_event.set()

            except socket.timeout:
                continue

    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] 连接错误: {e}")
    finally:
        client_socket.close()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] 连接已关闭 (共 {frame_count} 帧, {data_frames} DATA帧)")

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] 连接关闭: {frame_count} 帧, {data_frames} DATA帧\n")

def start_monitor(host='0.0.0.0', port=1449):
    """启动监测"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/rmcp_monitor_{timestamp}.log'
    os.makedirs('logs', exist_ok=True)

    print(f"=" * 60)
    print(f"RMCPTP 设备连接监测")
    print(f"=" * 60)
    print(f"监听地址: {host}:{port}")
    print(f"日志文件: {log_file}")
    print(f"")
    print(f"等待设备连接...")
    print(f"设备连接后，在另一终端发送 SOAP 请求")
    print(f"按 Ctrl+C 停止")
    print(f"=" * 60)

    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"RMCPTP Monitor Log - {datetime.now()}\n")
        f.write(f"=" * 60 + "\n")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 监测启动成功")

        while True:
            try:
                server_socket.settimeout(1.0)
                try:
                    client_socket, client_addr = server_socket.accept()
                except socket.timeout:
                    continue

                thread = threading.Thread(
                    target=handle_device,
                    args=(client_socket, client_addr, log_file),
                    daemon=True
                )
                thread.start()

            except KeyboardInterrupt:
                print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 停止监测...")
                break

    except Exception as e:
        print(f"错误: {e}")
    finally:
        server_socket.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='RMCPTP 设备连接监测')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=1449, help='监听端口 (默认: 1449)')
    args = parser.parse_args()

    start_monitor(args.host, args.port)