#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2b: SOAP 响应 STC ↔ streamsrc 帧内定位 配对抓包"""
import socket, struct, time, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from test_soap_full import send_soap_and_get_channel

def capture_streamsrc(host, port, stc, n_frames=10):
    """连接 streamsrc，发注册，收 n_frames 帧原始字节"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))

    # 注册包 (copy from test_soap_full.py)
    payload = struct.pack('<q', stc) + (b'RX_admin' + b'\x00' * 56)
    frame_len = 18 + len(payload)
    version = 0x0007
    data_type = 3
    flags = 0
    checksum = (sum(payload[:16]) + version + data_type + flags) & 0xFFFF
    header = struct.pack('<I', frame_len) + struct.pack('<Q', 0) + struct.pack('<H', version) + struct.pack('<BB', data_type, flags) + struct.pack('<H', checksum)
    register = header + payload
    sock.send(register)

    buf = b''
    frames = []
    start = time.time()
    while len(frames) < n_frames and time.time() - start < 10:
        try:
            chunk = sock.recv(8192)
            if not chunk:
                break
            buf += chunk
        except socket.timeout:
            break
        # 解析 0xEEEEEEEE 开头的 65 字节帧
        while True:
            idx = buf.find(b'\xee\xee\xee\xee')
            if idx < 0 or len(buf) < idx + 65:
                break
            frames.append(buf[idx:idx+65])
            buf = buf[idx+65:]
    sock.close()
    return frames


def locate_stc(stc, frames):
    """在帧内查找 STC 字节模式"""
    stc_le = stc.to_bytes(4, 'little')
    stc_be = stc.to_bytes(4, 'big')
    print(f"\n查找 STC 0x{stc:08X} (LE={stc_le.hex()}, BE={stc_be.hex()}) 在 {len(frames)} 帧内的位置:")
    hits_le = set()
    hits_be = set()
    for f in frames:
        for off in range(len(f) - 4):
            if f[off:off+4] == stc_le:
                hits_le.add(off)
            if f[off:off+4] == stc_be:
                hits_be.add(off)
    print(f"  LE 命中偏移: {sorted(hits_le) if hits_le else '(无)'}")
    print(f"  BE 命中偏移: {sorted(hits_be) if hits_be else '(无)'}")

    # 额外打印每帧 offset 4-15 区域
    print(f"\n前 5 帧 offset 4-15 区域:")
    for i, f in enumerate(frames[:5]):
        print(f"  #{i}: o4-11={f[4:12].hex()}  o12-15={f[12:16].hex()}")


def main():
    print("=" * 60)
    print("V2b: STC 配对抓包")
    print("=" * 60)
    r = send_soap_and_get_channel()
    if not r:
        print("[!] SOAP 失败"); return
    host, port, stc = r
    print(f"\nSOAP STC = {stc} (0x{stc:08X})")

    frames = capture_streamsrc(host, port, stc, n_frames=15)
    print(f"\n抓到 {len(frames)} 帧")
    if not frames:
        return

    locate_stc(stc, frames)

    # 保存
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = f'logs/v2b_stc_{stc:08x}_{ts}.log'
    with open(out, 'w') as fo:
        fo.write(f'stc={stc}\nhost={host}\nport={port}\n\n')
        for f in frames:
            fo.write(f.hex() + '\n')
    print(f"\n已保存 {out}")


if __name__ == '__main__':
    main()
