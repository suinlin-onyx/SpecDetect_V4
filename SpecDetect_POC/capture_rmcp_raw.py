#!/usr/bin/env python
"""抓取 rmcp_proxy FSCAN 原始响应"""
import socket
import struct
import sys

def capture_fscan():
    """发送 FSCAN 并捕获原始响应"""
    # 连接 rmcp_proxy
    sock = socket.socket()
    sock.settimeout(10)
    sock.connect(('127.0.0.1', 9996))

    # 发送 FSCAN 命令
    from app.atom_service.protocol_builder import RMCPTPBuilder
    builder = RMCPTPBuilder()
    cmd = builder.build_fscan_command(137000000, 173000000, 25000)

    print(f"发送命令: {len(cmd)} bytes")
    print(f"命令头: {cmd[:18].hex()}")

    sock.sendall(cmd)

    # 接收响应头 (18 bytes)
    header = sock.recv(18)
    if len(header) < 18:
        print(f"响应头太短: {len(header)} bytes")
        return

    dw_length = struct.unpack('<I', header[0:4])[0]
    print(f"\n响应头 ({len(header)} bytes):")
    print(f"  dwLength: {dw_length}")
    print(f"  header hex: {header.hex()}")

    if dw_length == 0:
        print("  (ACK 响应，无 body)")
        # 继续接收下一条消息
        print("\n等待下一条消息...")
        header2 = sock.recv(18)
        if len(header2) < 18:
            print(f"第二条消息头太短: {len(header2)} bytes")
            return

        dw_length2 = struct.unpack('<I', header2[0:4])[0]
        print(f"第二条消息 dwLength: {dw_length2}")
        print(f"header2 hex: {header2.hex()}")

        body = b''
        while len(body) < dw_length2:
            chunk = sock.recv(dw_length2 - len(body))
            if not chunk:
                break
            body += chunk
    else:
        # 接收完整 body
        body = b''
        while len(body) < dw_length:
            chunk = sock.recv(dw_length - len(body))
            if not chunk:
                break
            body += chunk

    print(f"\n响应体: {len(body)} bytes")
    print(f"body hex (前100字节): {body[:100].hex()}")

    # 分析 GWJ004 格式
    if len(body) >= 50:
        print(f"\n=== GWJ004 格式解析 ===")
        print(f"DT (偏移24): {body[24]}")
        dl = struct.unpack('<I', body[25:29])[0]
        print(f"DL (偏移25-28): {dl}")
        start_freq = struct.unpack('<d', body[29:37])[0]
        print(f"起始频率 (偏移29-36): {start_freq}")
        freq_step = struct.unpack('<f', body[37:41])[0]
        print(f"频率步进 (偏移37-40): {freq_step}")
        freq_index = struct.unpack('<I', body[41:45])[0]
        print(f"频率序号 (偏移41-44): {freq_index}")
        freq_count = struct.unpack('<I', body[45:49])[0]
        print(f"频率数量 (偏移45-48): {freq_count}")

        # 频谱数据
        spectrum_start = 49
        spectrum = body[spectrum_start:spectrum_start + 20]
        print(f"\n频谱数据 (前10点): {[struct.unpack('<h', spectrum[i:i+2])[0] for i in range(0, 20, 2)]}")

    sock.close()

if __name__ == '__main__':
    capture_fscan()