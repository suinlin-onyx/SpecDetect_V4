# -*- coding: utf-8 -*-
"""
完整测试脚本：连接 streamsrc + 发送 SOAP 请求
正确处理不同长度的 streamsrc 帧
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
    """接收 streamsrc FSCAN 帧（动态长度）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((STREAMSRC_HOST, STREAMSRC_PORT))
    print(f"[STREAM] 已连接 {STREAMSRC_HOST}:{STREAMSRC_PORT}")

    recv_count = 0
    while recv_count < 30:  # 最多收30帧
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

            recv_count += 1

            # 解析 streamsrc 帧头
            # Offset 0-3: LEADER (4 bytes, big-endian)
            leader = struct.unpack('>I', header[0:4])[0]
            # Offset 4-5: VER (2 bytes)
            ver = struct.unpack('<H', header[4:6])[0]
            # Offset 6-9: STC (4 bytes)
            stc = struct.unpack('<I', header[6:10])[0]
            # Offset 18-19: PL (2 bytes, big-endian) - payload length
            pl = struct.unpack('>H', header[18:20])[0]
            # Offset 24: DT (1 byte)
            dt = header[24]
            # Offset 25-28: DL (4 bytes, little-endian) - data length
            dl = struct.unpack('<I', header[25:29])[0]

            print(f"[STREAM] 帧{recv_count}: leader=0x{leader:08X}, ver={ver}, stc={stc}, dt={dt}, dl={dl}, pl={pl}")

            # 检查 leader 是否正确
            if leader != 0xEEEEEEEE:
                print(f"[STREAM]   -> 错误: leader 不正确!")
                # 跳过这帧，继续接收
                continue

            # 计算帧总长度: 29 (header) + pl
            frame_total = 29 + pl

            # 接收完整帧
            frame = header
            while len(frame) < frame_total:
                chunk = sock.recv(frame_total - len(frame))
                if not chunk:
                    break
                frame += chunk

            # 解析频谱数据
            # 频谱从 offset 62 开始 (29 + 33 = 62)
            # 交替字节模式: [dBm][0xFF][dBm][0xFF]...
            spectrum = []
            spectrum_offset = 62
            for i in range(min(dl, 512)):
                if spectrum_offset + i*2 + 1 < len(frame):
                    dbm_byte = frame[spectrum_offset + i*2]
                    if dbm_byte != 0xFF:
                        dbm_val = dbm_byte - 256 if dbm_byte > 127 else dbm_byte
                        spectrum.append(dbm_val)

            # 判断频段
            if dt == 12:
                if dl == 1057:
                    band = "Band1/2 (512点)"
                elif dl == 867:
                    band = "Band3 (417点)"
                else:
                    band = f"DT{dt}_DL{dl}"
            else:
                band = f"DT{dt}"

            if spectrum:
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