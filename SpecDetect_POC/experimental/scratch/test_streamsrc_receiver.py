#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TestTool 模拟器 - 测试 streamsrc 数据回调
功能：
1. 发送 SOAP 请求 (B_FScan)
2. 解析 outputchannel 获取 18012 和 stc
3. 连接 18012 等待数据回调
4. 接收并显示数据
"""

import socket
import struct
import time
import subprocess
import re
from datetime import datetime

# SOAP 配置
ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
B_FSCAN_SOAP = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>scanmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
<srrc:outputchannel><srrc:mode>source</srrc:mode><srrc:datachannel>stream</srrc:datachannel></srrc:outputchannel>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''


def send_soap_request():
    """发送 SOAP 请求并获取 outputchannel"""
    print("=" * 60)
    print("1. 发送 B_FScan 请求到 Atom")
    print("=" * 60)

    # 使用 curl 发送请求
    cmd = [
        'curl', '-s', '-X', f'http://{ATOM_HOST}:{ATOM_PORT}/B_FScan',
        '-H', 'Content-Type: text/xml; charset=utf-8',
        '-H', 'SOAPAction: B_FScan',
        '-d', B_FSCAN_SOAP
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    response = result.stdout

    print(f"响应状态: {'成功' if 'BIZ-000001' in response else '失败'}")
    print(f"响应长度: {len(response)} bytes")

    # 解析 outputchannel
    host_match = re.search(r'<srrc:host>([^<]+)</srrc:host>', response)
    port_match = re.search(r'<srrc:port>(\d+)</srrc:port>', response)
    stc_match = re.search(r'<srrc:stc>(\d+)</srrc:stc>', response)
    taskid_match = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', response)

    if host_match and port_match:
        host = host_match.group(1)
        port = int(port_match.group(1))
        stc = int(stc_match.group(1)) if stc_match else 0
        taskid = taskid_match.group(1) if taskid_match else ""

        print(f"\noutputchannel:")
        print(f"  host: {host}")
        print(f"  port: {port}")
        print(f"  stc: {stc}")
        print(f"  taskid: {taskid}")

        return host, port, stc, taskid
    else:
        print("解析 outputchannel 失败")
        print(f"响应内容: {response[:500]}")
        return None, None, None, None


def connect_streamsrc_and_receive(host, port, stc, timeout=30):
    """连接 streamsrc 并接收数据"""
    print("\n" + "=" * 60)
    print(f"2. 连接 streamsrc {host}:{port}")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((host, port))
        print(f"连接成功!")

        # 发送注册信息 (根据 stc 值构建)
        # 72字节数据：8字节 nTaskid (int64) + 64字节 szUser
        stc_bytes = struct.pack('<q', stc)  # little-endian int64
        username = b'RX_admin\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        register_data = stc_bytes + username

        print(f"发送注册数据: {len(register_data)} bytes")
        sock.send(register_data)
        print(f"发送完成")

        # 设置接收超时
        sock.settimeout(2.0)

        print(f"\n等待数据回调 (超时 {timeout} 秒)...")
        start_time = time.time()
        data_count = 0
        recv_buffer = b''

        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    print("连接被关闭")
                    break

                recv_buffer += chunk
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

                # 解析所有完整帧
                while len(recv_buffer) >= 18:
                    dwLength = struct.unpack('<I', recv_buffer[0:4])[0]
                    if len(recv_buffer) < dwLength:
                        break

                    frame_data = recv_buffer[:dwLength]
                    recv_buffer = recv_buffer[dwLength:]
                    data_count += 1

                    # 解析帧头
                    tmStamp = struct.unpack('<Q', frame_data[4:12])[0]
                    msgType = frame_data[13]
                    flags = frame_data[14]

                    msg_type_names = {
                        0: 'DATA', 1: 'KEEPALIVE', 2: 'ANNOUNCE',
                        3: 'REQUEST', 4: 'RESPONSE', 5: 'CONFIRM',
                        6: 'REPLY', 7: 'ABORT', 90: 'XML_REQUEST',
                        91: 'XML_RESPONSE', 92: 'HEARTBEAT'
                    }
                    msg_name = msg_type_names.get(msgType, f'UNKNOWN({msgType})')

                    elapsed = time.time() - start_time
                    print(f"[{timestamp}] 帧 #{data_count}: {msg_name}, dwLength={dwLength}, tmStamp={tmStamp}")

                    if msgType == 0 and len(frame_data) > 18:
                        payload = frame_data[18:]
                        if len(payload) >= 23:
                            leader = struct.unpack('<i', payload[0:4])[0]
                            ver = payload[4]
                            stc_val = struct.unpack('<I', payload[5:9])[0]
                            print(f"    >> nBdType={ver}, STC={stc_val}")

            except socket.timeout:
                # 检查是否超时
                if time.time() - start_time >= timeout:
                    print(f"接收超时 (共收到 {data_count} 帧)")
                    break
                continue
            except Exception as e:
                print(f"接收异常: {e}")
                break

        return data_count

    except Exception as e:
        print(f"连接失败: {e}")
        return 0
    finally:
        sock.close()
        print("连接已关闭")


def main():
    print("=" * 60)
    print("TestTool 模拟器 - streamsrc 数据回调测试")
    print("=" * 60)
    print()

    # 1. 发送 SOAP 请求
    host, port, stc, taskid = send_soap_request()

    if not host or not port:
        print("\n发送 SOAP 请求失败，退出")
        return

    # 2. 连接 streamsrc 并接收数据
    data_count = connect_streamsrc_and_receive(host, port, stc, timeout=30)

    print("\n" + "=" * 60)
    print("测试完成")
    print(f"共收到 {data_count} 帧数据")
    print("=" * 60)

    # 返回 0 如果收到数据，1 如果没有
    return 0 if data_count > 0 else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())