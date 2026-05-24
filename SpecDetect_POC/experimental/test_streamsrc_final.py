# -*- coding: utf-8 -*-
"""
完整测试脚本：连接 streamsrc + 发送 SOAP 请求
正确解析 streamsrc FSCAN 帧 (1086字节/896字节)
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
    """接收 streamsrc FSCAN 帧"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((STREAMSRC_HOST, STREAMSRC_PORT))
    print(f"[STREAM] 已连接 {STREAMSRC_HOST}:{STREAMSRC_PORT}")

    recv_count = 0
    while recv_count < 30:  # 最多收30帧
        try:
            # 接收帧头 (62字节: 29字节标准头 + 33字节metadata)
            header = b''
            while len(header) < 62:
                chunk = sock.recv(62 - len(header))
                if not chunk:
                    break
                header += chunk

            if len(header) < 62:
                break

            recv_count += 1

            # 解析 streamsrc 帧头
            # Offset 0-3: LEADER (4 bytes, big-endian)
            leader = struct.unpack('>I', header[0:4])[0]
            # Offset 4-5: VER (2 bytes, little-endian)
            ver = struct.unpack('<H', header[4:6])[0]
            # Offset 6-9: STC (4 bytes, little-endian)
            stc = struct.unpack('<I', header[6:10])[0]
            # Offset 18-19: Indicator (2 bytes, big-endian)
            indicator = struct.unpack('>H', header[18:20])[0]
            # Offset 24: DT (1 byte)
            dt = header[24]
            # Offset 25-28: DL (4 bytes, little-endian)
            dl = struct.unpack('<I', header[25:29])[0]

            print(f"[STREAM] 帧{recv_count}: leader=0x{leader:08X}, ver={ver}, stc={stc}, indicator=0x{indicator:04X}, dt={dt}, dl={dl}")

            # 检查 leader 是否正确
            if leader != 0xEEEEEEEE:
                print(f"[STREAM]   -> 错误: leader 不正确!")
                # 跳过这帧，继续接收
                continue

            # 计算 spectrum_data 长度: dl - 33 (metadata)
            spectrum_len = dl - 33

            # 判断频段
            if indicator == 0x0026:
                band_name = "Band1 (512点)"
            elif indicator == 0x0126:
                band_name = "Band2 (512点)"
            elif indicator == 0x0168:
                band_name = "Band3 (417点)"
            else:
                band_name = f"Unknown(0x{indicator:04X})"

            # 接收 spectrum_data
            # 交替模式: [dBm][0xFF][dBm][0xFF]...
            spectrum_data = b''
            while len(spectrum_data) < spectrum_len:
                chunk = sock.recv(spectrum_len - len(spectrum_data))
                if not chunk:
                    break
                spectrum_data += chunk

            # 解析频谱数据
            spectrum = []
            for i in range(min(spectrum_len // 2, 512)):
                if i*2 + 1 < len(spectrum_data):
                    dbm_byte = spectrum_data[i*2]
                    if dbm_byte != 0xFF:
                        dbm_val = dbm_byte - 256 if dbm_byte > 127 else dbm_byte
                        spectrum.append(dbm_val)

            print(f"[STREAM]   -> {band_name}, {len(spectrum)} 点, 前5个值={spectrum[:5]}")

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