# -*- coding: utf-8 -*-
"""
完整测试脚本：连接 streamsrc + 发送 SOAP 请求
"""
import socket
import struct
import threading
import time
import requests

# 配置
SOAP_URL = "http://127.0.0.1:8285"
STREAMSRC_HOST = "127.0.0.1"
STREAMSRC_PORT = 18015

# 读取 SOAP 请求
with open(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_UI_Atom\SpecDetect_Atom\docs\手动请求接口示例\接口soap请求报文\B_FScan.xml", "r", encoding="utf-8") as f:
    SOAP_XML = f.read()

def receive_streamsrc():
    """接收 streamsrc 数据"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((STREAMSRC_HOST, STREAMSRC_PORT))
    print(f"[STREAM] 已连接 {STREAMSRC_HOST}:{STREAMSRC_PORT}")

    # 接收数据
    recv_count = 0
    while recv_count < 20:  # 最多收20帧
        try:
            # 接收帧头 (29字节)
            header = b''
            while len(header) < 29:
                chunk = sock.recv(29 - len(header))
                if not chunk:
                    break
                header += chunk
            if len(header) < 29:
                break

            # 解析帧头
            leader = struct.unpack('<I', header[0:4])[0]
            ver = struct.unpack('>H', header[4:6])[0]
            stc = struct.unpack('<I', header[6:10])[0]
            indicator = struct.unpack('>H', header[18:20])[0]
            dt = header[24]
            dl = struct.unpack('<I', header[25:29])[0]

            recv_count += 1
            print(f"[STREAM] 帧{recv_count}: leader=0x{leader:08X}, dt={dt}, dl={dl}")

            # 接收帧体
            body_len = 20 + dl  # 20字节私有头 + dl
            body = b''
            while len(body) < body_len:
                chunk = sock.recv(body_len - len(body))
                if not chunk:
                    break
                body += chunk

            # 解析频段
            if dl > 0:
                # 跳过20字节私有头，读取频谱数据
                spectrum_start = 20
                spectrum = []
                for i in range(min(dl, 512)):
                    if spectrum_start + i*2 + 2 <= len(body):
                        val = struct.unpack('<h', body[spectrum_start + i*2:spectrum_start + i*2 + 2])[0]
                        spectrum.append(val)

                # 根据 dt 判断频段
                if dt == 12:
                    if len(spectrum) == 512:
                        band = "Band1" if stc == 0 else "Band2"
                    else:
                        band = "Band3"
                else:
                    band = f"DT{dt}"
                print(f"[STREAM]   -> {band}, {len(spectrum)} 点, 前5个值={spectrum[:5]}")

        except socket.timeout:
            continue
        except Exception as e:
            print(f"[STREAM] 接收错误: {e}")
            break

    print(f"[STREAM] 共接收 {recv_count} 帧")
    sock.close()

# 启动接收线程
recv_thread = threading.Thread(target=receive_streamsrc, daemon=True)
recv_thread.start()

# 等待连接建立
time.sleep(0.5)

# 发送 SOAP 请求
print("[SOAP] 发送 B_FScan 请求...")
headers = {"Content-Type": "text/xml; charset=gb2312"}
try:
    response = requests.post(SOAP_URL, data=SOAP_XML.encode('gb2312'), headers=headers, timeout=5)
    print(f"[SOAP] 响应状态: {response.status_code}")
except Exception as e:
    print(f"[SOAP] 请求失败: {e}")

# 等待数据接收
recv_thread.join(timeout=10)
print("[TEST] 测试完成")