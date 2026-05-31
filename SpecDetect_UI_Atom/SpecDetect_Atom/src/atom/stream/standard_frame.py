# -*- coding: utf-8 -*-
"""
标准 GWJ004 §5.17 帧格式构建模块

用于 Sink 模式推送，与 RXAtomSvcV3 数据格式对齐。
帧头使用标准 GWJ004 24B 格式，私有元数据复用 frame.py 的 _get_band_metadata()。
"""

import struct
import time


# === 帧头常量 ===
SYNC_WORD = 0xEEEEEEEE
VER_MAJOR = 1
VER_MINOR = 0
EL_DEFAULT = 0

# === DT 值 (GWJ004 §5.14) ===
DT_UUID = 102       # UUID 注册帧
DT_FSCAN = 12       # FSCAN 频谱数据
DT_SPECTRUM = 7     # 频谱数据 (单频测量结果)


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


def build_uuid_frame(taskid: str, stc: int) -> bytes:
    """构建 UUID 注册帧 (DT=102, 65 bytes)

    DATA: 36 字节 ASCII taskid 字符串（来自 SOAP 请求）

    Args:
        taskid: 任务 ID（SOAP 请求携带）
        stc: 通道标识
    """
    data = taskid.encode('ascii')[:36].ljust(36, b'\x00')
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

    DATA = metadata(33B) + [dBm_byte, 0xFF] spectrum × n

    Args:
        levels_int16: 频谱数据 (int16 列表, 单位 dBm×10)
        metadata: 33 字节私有元数据（来自 frame.py _get_band_metadata）
        stc: 通道标识
    """
    # 频谱数据 [dBm_byte, 0xFF] 编码（与 RXAtomSvcV3 对齐）
    spectrum = b''
    for v in levels_int16:
        dbm = v / 10.0
        if dbm < 0:
            byte_val = int(256 + dbm)
        else:
            byte_val = int(dbm)
        byte_val = max(0, min(255, byte_val))
        spectrum += bytes([byte_val, 0xFF])

    data = metadata + spectrum
    dl = len(data)
    pl = 1 + 4 + dl  # DT(1) + DL(4) + DATA

    frame = bytearray(24 + pl)
    frame[0:24] = build_frame_header(stc, pl)
    frame[24] = DT_FSCAN
    struct.pack_into('<I', frame, 25, dl)
    frame[29:29 + dl] = data
    return bytes(frame)


def build_pscan_frame(levels_raw: list,
                      stc: int,
                      start_freq_hz: float = 750000000.0,
                      stop_freq_hz: float = 1000000000.0,
                      step_hz: float = 25000.0) -> bytes:
    """构建标准 PScan 频谱帧 (DT=12, GWJ004 24B 帧头)

    DATA = metadata(33B) + spectrum(int16 LE)
    频谱编码: RMCP int16 / 10 → int16 LE（与 RXAtom 对齐）

    Args:
        levels_raw: RMCP DSCAN int16 全频段电平数据
        stc: 通道标识
        start_freq_hz: 起始频率 Hz
        stop_freq_hz: 结束频率 Hz
        step_hz: 步长 Hz

    Returns:
        GWJ004 标准帧 bytes
    """
    n_points = len(levels_raw)

    # Metadata 33B 布局 (对齐 RXAtom 二进制输出):
    #   [0]     n_bands             UINT8
    #   [1-2]   n_points_total      UINT16 LE
    #   [3-4]   reserved            (2B)
    #   [5-12]  start_freq          double LE
    #   [13-20] stop_freq           double LE
    #   [21-24] frame_start_index   UINT32 LE (= 0)
    #   [25-28] step                float32 LE
    #   [29-30] n_points_in_frame   UINT16 LE
    #   [31-32] reserved            (2B)
    metadata = bytearray(33)
    metadata[0] = 1  # n_bands
    struct.pack_into('<H', metadata, 1, n_points)
    struct.pack_into('<d', metadata, 5, start_freq_hz)
    struct.pack_into('<d', metadata, 13, stop_freq_hz)
    struct.pack_into('<I', metadata, 21, 0)         # frame_start_index = 0
    struct.pack_into('<f', metadata, 25, step_hz)   # step as float32
    struct.pack_into('<H', metadata, 29, n_points)  # n_points_in_frame

    # 频谱编码: RMCP int16 / 10 → int16 LE
    spectrum = b''
    for raw_val in levels_raw:
        spectrum += struct.pack('<h', int(raw_val / 10.0))

    data = bytes(metadata) + spectrum
    dl = len(data)
    pl = 1 + 4 + dl  # DT(1) + DL(4) + DATA

    frame = bytearray(24 + pl)
    frame[0:24] = build_frame_header(stc, pl)
    frame[24] = DT_FSCAN
    struct.pack_into('<I', frame, 25, dl)
    frame[29:29 + dl] = data
    return bytes(frame)


def build_sglfreq_frame(levels_raw: list,
                        stc: int,
                        center_freq_hz: float = 97100000.0,
                        ifbw_hz: float = 40000000.0) -> bytes:
    """构建 SglFreq IFANALYSIS 频谱帧 (DT=7, GWJ004 24B 帧头 + 25B streamsrc meta)

    Java 客户端对 DT=7 (spectrum) 帧使用 25B streamsrc 元数据布局，
    与 PScan/FScan 使用的 33B 布局不同。此处匹配 RXAtom 已验证的格式。

    Body = 25B meta + spectrum(n) × int16 LE
    n_points = len(levels_raw) = 1601

    Args:
        levels_raw: RMCP IFANALYSIS int16 频谱数据 (int(v/10) 截断后, 1601点含首点标记)
        stc: 通道标识
        center_freq_hz: 中心频率 Hz (保留参数, 25B meta 中不使用)
        ifbw_hz: 中频带宽 Hz (保留参数)
    """
    n_real = len(levels_raw)
    n_points = n_real  # = 1601, 直接使用所有值 (无合成标记)

    # 25B streamsrc 元数据布局 (与 frame.py build_pscan_spectrum_frame 一致)
    metadata = bytearray(25)
    metadata[0] = 0x00                      # streamsrc 格式标识
    struct.pack_into('<I', metadata, 1, n_points)   # [1:5]: n_points (UINT32 LE)
    # [5:21]: 设备固定元数据 (与旧 frame.py 对齐)
    metadata[5:9] = bytes([0x00, 0x00, 0x00, 0x00])
    metadata[9:17] = bytes([0xd0, 0x12, 0x93, 0x41, 0x00, 0x50, 0xc3, 0x46])
    metadata[17:21] = bytes([0x00, 0x00, 0x00, 0x00])
    struct.pack_into('<I', metadata, 21, n_points)  # [21:25]: n_points 重复

    # 频谱编码: 直接写入所有数据 (int16 LE, 与 v1.4.9 RXAtom 一致)
    spectrum = b''
    for raw_val in levels_raw:
        spectrum += struct.pack('<h', raw_val)

    data = bytes(metadata) + spectrum
    dl = len(data)
    pl = 1 + 4 + dl

    frame = bytearray(24 + pl)
    frame[0:24] = build_frame_header(stc, pl)
    frame[24] = DT_SPECTRUM
    struct.pack_into('<I', frame, 25, dl)
    frame[29:29 + dl] = data
    return bytes(frame)
