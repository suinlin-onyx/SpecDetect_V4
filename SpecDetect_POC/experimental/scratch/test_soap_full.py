#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TestTool 模拟器 - 直接用 Python 发送 SOAP 并连接 streamsrc
"""
import socket
import struct
import time
import re
import threading
from datetime import datetime

ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
STREAMSRC_PORT = 18012

def send_soap_and_get_channel():
    """发送 SOAP 请求并获取 outputchannel"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)

    try:
        sock.connect((ATOM_HOST, ATOM_PORT))

        soap_request = b'''POST /B_FScan HTTP/1.1\r
Host: 127.0.0.1:8282\r
Content-Type: text/xml; charset=utf-8\r
SOAPAction: B_FScan\r
Content-Length: 1047\r
\r
<?xml version="1.0" encoding="UTF-8"?>
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

        sock.send(soap_request)
        print("[1] SOAP 请求已发送")

        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b'</soapenv:Envelope>' in response:
                    break
            except socket.timeout:
                break

        response_text = response.decode('utf-8', errors='replace')
        print(f"[2] 收到响应: {len(response)} bytes")

        # 解析 outputchannel
        host_match = re.search(r'<srrc:host>([^<]+)</srrc:host>', response_text)
        port_match = re.search(r'<srrc:port>(\d+)</srrc:port>', response_text)
        stc_match = re.search(r'<srrc:stc>(\d+)</srrc:stc>', response_text)

        if host_match and port_match:
            host = host_match.group(1)
            port = int(port_match.group(1))
            stc = int(stc_match.group(1)) if stc_match else 0
            print(f"[3] outputchannel: {host}:{port}, stc={stc}")
            return host, port, stc

        print("[!] 未找到 outputchannel")
        if 'conflict' in response_text:
            print("[!] 设备使用冲突，需要先停止之前的任务")
        return None, None, None

    except Exception as e:
        print(f"[!] SOAP 请求失败: {e}")
        return None, None, None
    finally:
        sock.close()


def connect_streamsrc_and_receive(host, port, stc, timeout=30):
    """连接 streamsrc 并接收数据"""
    print(f"\n[4] 连接 streamsrc {host}:{port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)

    try:
        sock.connect((host, port))
        print("[5] streamsrc 连接成功!")

        # 发送注册信息
        # RMCP帧头(18字节) + 数据(72字节) = 90字节
        payload = struct.pack('<q', stc) + (b'RX_admin' + b'\x00' * 56)  # 72字节
        # RMCP帧头
        frame_len = 18 + len(payload)  # = 90
        timestamp = 0  # 可以用实际时间戳
        version = 0x0007
        data_type = 3  # 分发请求
        flags = 0
        # 计算校验和 (简单累加)
        checksum = (sum(payload[:16]) + version + data_type + flags) & 0xFFFF

        header = struct.pack('<I', frame_len)  # dwLength (4 bytes)
        header += struct.pack('<Q', timestamp)  # tmStamp (8 bytes)
        header += struct.pack('<H', version)  # nVersion (2 bytes)
        header += struct.pack('<BB', data_type, flags)  # nDataType + nFlags (2 bytes)
        header += struct.pack('<H', checksum)  # nCheckSum (2 bytes)

        register_data = header + payload
        print(f"[6a] stc={stc}, payload_hex={payload.hex()}")
        print(f"[6b] frame_len={frame_len}, header_hex={header.hex()}")

        sock.send(register_data)
        print(f"[6] 发送注册数据: {len(register_data)} bytes")

        print(f"\n[7] 等待数据回调 (最多 {timeout} 秒)...")
        start_time = time.time()
        data_count = 0
        recv_buffer = b''

        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    elapsed = time.time() - start_time
                    print(f"[8] 连接关闭 (收到 {data_count} 帧, 耗时 {elapsed:.1f}s)")
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
                    print(f"[{timestamp}] 帧 #{data_count}: {msg_name}, dwLength={dwLength}")

                    if msgType == 0 and len(frame_data) > 18:
                        payload = frame_data[18:]
                        if len(payload) >= 23:
                            leader = struct.unpack('<i', payload[0:4])[0]
                            ver = payload[4]
                            stc_val = struct.unpack('<I', payload[5:9])[0]
                            print(f"      >> nBdType={ver}, STC={stc_val}")

            except socket.timeout:
                if time.time() - start_time >= timeout:
                    print(f"[9] 接收超时 (收到 {data_count} 帧)")
                    break
                continue
            except Exception as e:
                print(f"[!] 接收异常: {e}")
                break

        return data_count

    except Exception as e:
        print(f"[!] streamsrc 连接失败: {e}")
        return 0
    finally:
        sock.close()
        print("[10] 连接已关闭")


def main():
    print("=" * 60)
    print("TestTool 模拟器 - streamsrc 数据回调测试")
    print("=" * 60)
    print()

    # 1. 发送 SOAP 请求
    host, port, stc = send_soap_and_get_channel()

    if not host:
        print("\n失败，退出")
        return 1

    # 2. 连接 streamsrc 并接收数据
    data_count = connect_streamsrc_and_receive(host, port, stc, timeout=30)

    print("\n" + "=" * 60)
    print(f"测试完成: 收到 {data_count} 帧数据")
    print("=" * 60)

    return 0 if data_count > 0 else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())