#!/usr/bin/env python
"""分析 GWJ004 5.17 streamsrc 帧格式"""
import struct

def analyze_streamsrc_frame(frame: bytes):
    """解析 GWJ004 5.17 标准的 streamsrc 帧"""
    print(f"帧长度: {len(frame)} bytes")

    # 数据帧头
    print("\n=== 数据帧头 (Frame Header) ===")

    # LEADER (4 bytes, offset 0-3)
    leader = struct.unpack('<I', frame[0:4])[0]
    print(f"Offset 0-3: LEADER = 0x{leader:08X}")

    # VER (2 bytes, offset 4-5, big-endian)
    ver = struct.unpack('>H', frame[4:6])[0]
    print(f"Offset 4-5: VER = 0x{ver:04X}")

    # STC (4 bytes, offset 6-9, little-endian)
    stc = struct.unpack('<I', frame[6:10])[0]
    print(f"Offset 6-9: STC = 0x{stc:08X}")

    # TS (8 bytes, offset 10-17, FILETIME)
    ts = struct.unpack('<Q', frame[10:18])[0]
    print(f"Offset 10-17: TS = {ts}")

    # PL (4 bytes, offset 18-21,负载长度)
    pl = struct.unpack('<I', frame[18:22])[0]
    print(f"Offset 18-21: PL = {pl}")

    # EL (1 byte, offset 22)
    el = struct.unpack('B', frame[22:23])[0]
    print(f"Offset 22: EL = {el}")

    # ExHeader (EL bytes, offset 23)
    if el > 0:
        exheader = frame[23:23+el]
        print(f"Offset 23-{23+el-1}: ExHeader = {exheader.hex()}")

    # 数据帧体
    body_offset = 23 + el
    print(f"\n=== 数据帧体 (Frame Body) @ offset {body_offset} ===")

    # DT (1 byte, 数据类型)
    dt = struct.unpack('B', frame[body_offset:body_offset+1])[0]
    print(f"Offset {body_offset}: DT = {dt} (12=FSCAN, 13=MSCAN)")
    body_offset += 1

    # DL (4 bytes, 数据长度)
    dl = struct.unpack('<I', frame[body_offset:body_offset+4])[0]
    print(f"Offset {body_offset}-{body_offset+3}: DL = {dl}")
    body_offset += 4

    # Business Data (DL bytes)
    print(f"\n=== 业务数据 (Business Data) @ offset {body_offset} ===")

    # Metadata (7 int16, 14 bytes)
    metadata_offset = body_offset
    print(f"\nOffset {metadata_offset}-{metadata_offset+13}: Metadata (7 × int16)")
    metadata = []
    for i in range(7):
        val = struct.unpack('<h', frame[metadata_offset + i*2 : metadata_offset + i*2 + 2])[0]
        metadata.append(val)
        print(f"  metadata[{i}] = {val}")

    # Spectrum (512 int16)
    spectrum_offset = metadata_offset + 14
    spectrum = []
    for i in range(min(10, 512)):
        val = struct.unpack('<h', frame[spectrum_offset + i*2 : spectrum_offset + i*2 + 2])[0]
        spectrum.append(val / 10.0)  # 转换回 dBm 值
    print(f"\nOffset {spectrum_offset}+: Spectrum (前10点, dBm): {spectrum}")

    return metadata, spectrum

if __name__ == '__main__':
    # 使用当前 build_streamsrc_frame 生成的数据
    from emulated_atom import build_streamsrc_frame

    # 生成测试帧 (使用假数据)
    test_spectrum = [-70.0] * 512
    test_spectrum[100:120] = [-50.0] * 20  # 信号峰值

    frame = build_streamsrc_frame(test_spectrum)
    analyze_streamsrc_frame(frame)