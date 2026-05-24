# -*- coding: utf-8 -*-
"""
标准 GWJ004 §5.17 帧格式构建模块

用于 Sink 模式推送，与 RXAtomSvcV3 数据格式对齐。
帧头使用标准 GWJ004 24B 格式，私有元数据复用 frame.py 的 _get_band_metadata()。
"""

import struct
import time
import uuid


# === 帧头常量 ===
SYNC_WORD = 0xEEEEEEEE
VER_MAJOR = 1
VER_MINOR = 0
EL_DEFAULT = 0

# === DT 值 (GWJ004 §5.14) ===
DT_UUID = 102   # UUID 注册帧
DT_FSCAN = 12   # FSCAN 频谱数据


def build_standard_ts() -> bytes:
    """构建 9 字节标准时间戳 (GWJ004 §5.17)

    格式: 年(UINT16 LE) + 月(1) + 日(1) + 时(1) + 分(1) + 秒(1) + 毫秒(UINT16 LE)
    """
    now = time.localtime()
    ms = int((time.time() * 1000) % 1000)
    ts = struct.pack('<H', now.tm_year)
    ts += bytes([now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec])
    ts += struct.pack('<H', ms)
    return ts


def build_frame_header(stc: int, pl: int, el: int = EL_DEFAULT) -> bytes:
    """构建 24 字节标准帧头

    Args:
        stc: 通道标识 (UINT32)
        pl: 载荷长度, DT + DL + DATA (UINT32)
        el: 扩展头长度, 默认 0
    """
    header = struct.pack('>I', SYNC_WORD)           # 0-3:   LEADER
    header += bytes([VER_MAJOR, VER_MINOR])          # 4-5:   VER
    header += struct.pack('<I', stc)                 # 6-9:   STC
    header += build_standard_ts()                    # 10-18: TS
    header += struct.pack('<I', pl)                  # 19-22: PL
    header += bytes([el])                            # 23:    EL
    return header


def build_uuid_frame(stc: int) -> bytes:
    """构建 UUID 注册帧 (DT=102, 65 bytes)

    DATA: 36 字节 ASCII GUID 字符串

    Args:
        stc: 通道标识
    """
    guid = str(uuid.uuid4())
    data = guid.encode('ascii')
    dl = len(data)
    pl = 1 + 4 + dl  # DT(1) + DL(4) + DATA

    frame = bytearray(24 + pl)
    frame[0:24] = build_frame_header(stc, pl)
    frame[24] = DT_UUID
    struct.pack_into('<I', frame, 25, dl)
    frame[29:29 + dl] = data
    return bytes(frame)


def build_fscan_frame(levels_int16: list,
                      metadata: bytes,
                      stc: int) -> bytes:
    """构建标准 FSCAN 频谱帧 (DT=12)

    DATA = metadata(33B) + INT16 LE spectrum × n

    Args:
        levels_int16: 频谱数据 (int16 列表, 单位 dBm×10)
        metadata: 33 字节私有元数据（来自 frame.py _get_band_metadata）
        stc: 通道标识
    """
    # 频谱数据 INT16 LE
    spectrum = b''
    for v in levels_int16:
        spectrum += struct.pack('<h', int(v))

    data = metadata + spectrum
    dl = len(data)
    pl = 1 + 4 + dl  # DT(1) + DL(4) + DATA

    frame = bytearray(24 + pl)
    frame[0:24] = build_frame_header(stc, pl)
    frame[24] = DT_FSCAN
    struct.pack_into('<I', frame, 25, dl)
    frame[29:29 + dl] = data
    return bytes(frame)
