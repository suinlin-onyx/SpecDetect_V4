# -*- coding: utf-8 -*-
"""
streamsrc 帧生成模块

负责生成各类型 streamsrc 帧
与 RMCP 解析完全解耦
"""

import struct
import time
import logging

log = logging.getLogger('atom.stream.frame')

# streamsrc 帧通用常量
SYNC_WORD = 0xEEEEEEEE          # 帧同步字 (大端)
VER = 1                          # 帧版本号 (小端)
HEADER_SIZE = 62                 # 帧头长度 (含 metadata 起始)
DEFAULT_FREQUENCY = 100000000    # 默认频率 100MHz (Hz)
DEFAULT_IFBW = 40000000          # 默认中频带宽 40MHz (Hz)
_FIXED_MSCAN_LEVEL = bytes([0x84, 0xD7, 0x97, 0x41])  # Level帧固定常量
_BAND3_FRAME_COUNTER_BASE = 16804                       # Band3 帧计数器基准值

# 模块级帧计数器（用于 metadata 动态字段）
_fscan_frame_counter = 0


def _next_frame_counter() -> int:
    """获取并递增帧计数器"""
    global _fscan_frame_counter
    counter = _fscan_frame_counter
    _fscan_frame_counter += 1
    return counter


_PRIVATE_METADATA_BAND1 = bytes([
    0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x80, 0xe8, 0x54, 0xa0, 0x41, 0x00, 0x00, 0x00,
    0x30, 0xc5, 0xda, 0xa1, 0x41, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x50, 0xc3, 0x46, 0x00, 0x02, 0x00,
    0x00
])

_PRIVATE_METADATA_BAND2 = bytes([
    0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x80, 0x88, 0xdb, 0xa1, 0x41, 0x00, 0x00, 0x00,
    0x30, 0x65, 0x61, 0xa3, 0x41, 0x00, 0x02, 0x00,
    0x00, 0x00, 0x50, 0xc3, 0x46, 0x00, 0x02, 0x00,
    0x00
])

_PRIVATE_METADATA_BAND3 = bytes([
    0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x80, 0x28, 0x62, 0xa3, 0x41, 0x00, 0x00, 0x00,
    0x80, 0x8a, 0x9f, 0xa4, 0x41, 0x00, 0x04, 0x00,
    0x00, 0x00, 0x50, 0xc3, 0x46, 0xa1, 0x01, 0x00,
    0x00
])

_INDICATOR_BAND1 = 0x0026
_INDICATOR_BAND2 = 0x0126
_INDICATOR_BAND3 = 0x0168

_FSCAN_TYPE_529 = bytes([0x04, 0x00, 0x00, 0x00])
_FSCAN_TYPE_434 = bytes([0x03, 0x00, 0x00, 0x00])
_FSCAN_TYPE_PSCAN = bytes([0x0b, 0x00, 0x00, 0x00])  # PScan IFANALYSIS

_DT_FSCAN = 12
_DT_MSCAN = 13
_DT_PSCANDATA = 7
_DT_PSCANLEVEL = 101
_DT_PSCANITU = 8
_DT_UUID = 33  # UUID 注册帧

# PScan FSCAN 帧常量
_PSCAN_TOTAL_POINTS = 1441
_PSCAN_RMCP_POINTS = 605  # 旧值，保留兼容
_PSCAN_HIGH_FREQ_POINTS = 836
_PSCAN_HIGH_FREQ_DBM = -88.0

# RMCP 80-180MHz (4001点, 25kHz步长) → streamsrc 137-173MHz (1441点) 频率映射
# 137MHz = RMCP index (137-80)/0.025 = 2280
# 173MHz = RMCP index (173-80)/0.025 = 3720
# slice [2280:3721] = 1441 points
_PSCAN_RMCPCENTER_START = 2280  # RMCP 80MHz起始，137MHz对应索引
_PSCAN_RMCPCENTER_END = 3721   # RMCP 80MHz起始，173MHz对应索引+1

# PScan PL与Payload/Indicator映射（与真实设备对齐）
_PSCAN_PL_PAYLOAD_MAP = {
    104: 34,
    360: 162,
    616: 290,
    872: 418,
}
_PSCAN_PL_START_INDEX_MAP = {
    104: 0,
    360: 0,
    616: 0,
    872: 0,
}
_PSCAN_PL_INDICATOR_MAP = {
    104: 0x0068,
    360: 0x0168,
    616: 0x0268,
    872: 0x0368,
}


def _get_streamsrc_timestamp() -> bytes:
    """生成与真实设备匹配的 streamsrc 时间戳 (8 bytes)"""
    now = time.localtime()
    year = now.tm_year
    month = now.tm_mon
    day = now.tm_mday
    hour = now.tm_hour
    minute = now.tm_min
    second = now.tm_sec
    ms = int(time.time() * 1000) % 256

    year_bytes = struct.pack('<H', year)
    rest = bytes([month, day, hour, minute, second, ms])
    return year_bytes + rest


def _get_band_metadata(start_index: int) -> bytes:
    if start_index <= 0:
        return bytes(_PRIVATE_METADATA_BAND1)
    elif start_index <= 512:
        return bytes(_PRIVATE_METADATA_BAND2)
    else:
        return bytes(_PRIVATE_METADATA_BAND3)


def _get_band_indicator(start_index: int) -> int:
    if start_index <= 0:
        return _INDICATOR_BAND1
    elif start_index <= 512:
        return _INDICATOR_BAND2
    else:
        return _INDICATOR_BAND3


def _get_fscan_type(start_index: int) -> bytes:
    if start_index <= 0:
        return _FSCAN_TYPE_529
    elif start_index <= 512:
        return _FSCAN_TYPE_529
    else:
        return _FSCAN_TYPE_434


def _get_pscan_indicator(pl: int) -> int:
    """根据PL值返回PScan FSCAN Indicator"""
    return _PSCAN_PL_INDICATOR_MAP.get(pl, 0x0068)


def _get_pscan_start_index(pl: int) -> int:
    """根据PL值返回PScan起始频率序号"""
    return _PSCAN_PL_START_INDEX_MAP.get(pl, 0)


def _get_pscan_metadata(start_index: int = 0) -> bytes:
    """获取PScan FSCAN帧的Metadata (33字节)

    所有帧使用同一份 metadata（与真实设备一致）:
    - start_index=0 (全频段)
    - 1441 通道
    - bytes 16-19: 设备值 (待确认含义)
    - bytes 29-30: 0x05a1 (1441)
    """
    return bytes([
        0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x80, 0xe8, 0x54, 0xa0, 0x41, 0x00, 0x00, 0x00,
        0x80, 0x8a, 0x9f, 0xa4, 0x41, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x50, 0xc3, 0x46, 0xa1, 0x05, 0x00,
        0x00
    ])


def build_uuid_frame(taskid: str, stc: int = None, ts: bytes = None) -> bytes:
    """构建 UUID 注册帧 (65字节)

    客户端连接 streamsrc 后，设备首先发送此帧。
    与真实设备对齐:
    - Header (22B): sync(4) + VER(2) + STC(4) + TS(8) + indicator(2) + meta(2)
    - Payload (43B): meta(7) + UUID(36)
    - UUID 从 offset 29 开始
    """
    if stc is None:
        stc = 0
    if ts is None:
        ts = _get_streamsrc_timestamp()

    # UUID: 36字节 ASCII，用 taskid 填充，不足部分用 0 填充
    uuid_bytes = taskid.encode('ascii')[:36].ljust(36, b'\x00')

    frame = bytearray(65)

    # Header (22字节)
    frame[0:4] = struct.pack('>I', SYNC_WORD)
    frame[4:6] = struct.pack('<H', 1)
    frame[6:10] = struct.pack('<I', stc)
    frame[10:18] = ts
    frame[18:20] = struct.pack('>H', 0x0129)  # indicator (与设备一致)

    # Payload (43字节)
    frame[22] = 0x00           # meta byte
    frame[23] = 0x00           # meta byte
    frame[24:26] = bytes([0xc9, 0x24])  # 固定元数据
    frame[26:29] = bytes([0x00, 0x00, 0x00])  # 固定元数据
    frame[29:65] = uuid_bytes  # UUID (36 bytes)

    return bytes(frame)


def build_fscan_frame(spectrum_dbm: list, start_index: int = 0, stc: int = None, ts: bytes = None) -> bytes:
    """构建 FSCAN streamsrc 帧"""
    if ts is None:
        ts = _get_streamsrc_timestamp()
    if stc is None:
        stc = 0

    indicator = _get_band_indicator(start_index)
    metadata = bytearray(_get_band_metadata(start_index))
    fscan_type = _get_fscan_type(start_index)

    spectrum_data = b''
    try:
        for i, dbm in enumerate(spectrum_dbm):
            if dbm < 0:
                byte_val = int(256 + dbm)
            else:
                byte_val = int(dbm)
            if byte_val < 0 or byte_val > 255:
                raise ValueError(f"spectrum_dbm[{i}]={dbm} → byte_val={byte_val} 超出范围(0-255)")
            spectrum_data += bytes([byte_val, 0xFF])
    except Exception as e:
        log.error(f"[FSCAN] 频谱编码失败: {e}, start_index={start_index}, n_arrays={len(spectrum_dbm)}")
        # 输出异常值附近的数据用于调试
        if 'spectrum_dbm' in dir() and len(spectrum_dbm) > 0:
            start = max(0, i - 5)
            end = min(len(spectrum_dbm), i + 6)
            log.error(f"[FSCAN] 问题点附近 spectrum_dbm[{start}:{end}] = {spectrum_dbm[start:end]}")
        raise

    struct.pack_into('<H', metadata, 21, start_index)

    dl = len(metadata) + len(spectrum_data)
    frame_len = 62 + dl

    frame = bytearray(frame_len)

    struct.pack_into('<I', frame, 0, SYNC_WORD)
    struct.pack_into('<H', frame, 4, 1)   # VER=1 (little-endian 0x0001)，与真实设备一致
    struct.pack_into('<I', frame, 6, stc)
    frame[10:18] = ts
    struct.pack_into('>H', frame, 18, indicator)
    frame[20:24] = fscan_type
    frame[24] = _DT_FSCAN
    struct.pack_into('<I', frame, 25, dl)
    frame[29:62] = metadata
    frame[62:] = spectrum_data

    return bytes(frame)


def build_pscan_fscan_frame(rmcp_levels: list, pl: int, stc: int = 0, ts: bytes = None) -> bytes:
    """构建PScan streamsrc FSCAN帧 (DT=12)

    与真实设备对齐:
    - FScanType = 0x0b (IFANALYSIS)
    - 所有帧使用同一份 metadata (start_index=0, 1441ch)
    - PL 值决定 indicator 和 payload_points
    - RMCP 4001点 (80-180MHz) → 选取 137-173MHz 子带 (indices 2280-3720, 1441点)

    Args:
        rmcp_levels: RMCP DSCAN数据，int16 (4001点, 80-180MHz)
        pl: PL值 (360/616/872)
        stc: 通道标识
        ts: 时间戳 (可选)

    Returns:
        streamsrc FSCAN帧 bytes (2944B)
    """
    if ts is None:
        ts = _get_streamsrc_timestamp()

    # 1. 从 RMCP 4001点中选取 137-173MHz 子带 (1441点)
    #    RMCP 覆盖 80-180MHz, 25kHz步长
    #    137MHz = index 2280, 173MHz = index 3720
    sub_band = rmcp_levels[_PSCAN_RMCPCENTER_START:_PSCAN_RMCPCENTER_END]

    # 如果 RMCP 数据不足 3721 点，用 0 填充
    if len(sub_band) < _PSCAN_TOTAL_POINTS:
        sub_band = list(sub_band) + [0] * (_PSCAN_TOTAL_POINTS - len(sub_band))

    # 2. 获取参数（所有帧统一 metadata，PL 仅控制 indicator）
    indicator = _get_pscan_indicator(pl)
    metadata = _get_pscan_metadata()

    # 3. 频谱数据编码 (与真实设备对齐: 第二字节 0x00)
    spectrum_data = b''
    for i in range(_PSCAN_TOTAL_POINTS):
        raw_val = sub_band[i]
        # RMCP int16 ÷ 10 = dBm, 再编码为单字节 (0-255)
        dbm = raw_val / 10.0
        if dbm < 0:
            byte_val = int(256 + dbm)  # 负dBm: 256+dbm (如 -88 → 168)
        else:
            byte_val = min(int(dbm), 255)  # 正dBm: 直接取整, 限制255
        # 与真实设备对齐: 第二字节始终 0x00
        spectrum_data += bytes([byte_val & 0xFF, 0x00])

    # 4. 组装帧
    dl = len(metadata) + len(spectrum_data)
    frame_len = 62 + dl

    frame = bytearray(frame_len)

    struct.pack_into('<I', frame, 0, SYNC_WORD)
    struct.pack_into('<H', frame, 4, 1)
    struct.pack_into('<I', frame, 6, stc)
    frame[10:18] = ts
    struct.pack_into('>H', frame, 18, indicator)
    frame[20:24] = _FSCAN_TYPE_PSCAN  # 0x0b (IFANALYSIS)
    frame[24] = _DT_FSCAN
    struct.pack_into('<I', frame, 25, dl)
    frame[29:62] = metadata
    frame[62:] = spectrum_data

    return bytes(frame)


def build_fscan_frame_434(spectrum_dbm: list, start_index: int = 1024, stc: int = None, ts: bytes = None) -> bytes:
    """构建 FSCAN-434 Band3 streamsrc 帧 (896字节)

    Band3 帧格式 (896 bytes):
    - Offset 0-3:   Sync (0xEEEEEEEE)
    - Offset 4-61:  Header + Metadata
    - Offset 62+:    Spectrum (417点, 交替字节模式 [dBm][0xFF]...)

    与 Band1/2 的关键差异:
    - 帧长: 896B (Band1/2: 1086B)
    - DL: 867 (Band1/2: 1057)
    - FSCAN type: 0x03000000 (Band1/2: 0x04000000)
    - Indicator: 0x0168 (Band1/2: 0x0026/0x0126)
    - Spectrum: 417点 × 2 = 834 bytes
    - Metadata: frame_counter 动态字段

    Args:
        spectrum_dbm: 频谱数据点 (dBm 值列表，取前417点)
        start_index: 起始频率序号 (默认1024)
        stc: 同步通道号
        ts: 时间戳
    """
    if ts is None:
        ts = _get_streamsrc_timestamp()
    if stc is None:
        stc = 0

    frame_counter = _next_frame_counter()
    n_arrays = min(len(spectrum_dbm), 417)

    # Band3 专用 metadata (33 bytes)
    # frame_counter 写入 offset 0-1 (little-endian uint16)
    metadata = bytearray([
        0x01, 0xa1, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x80, 0x28, 0x62, 0xa3, 0x41, 0x00, 0x00, 0x00,
        0x80, 0x8a, 0x9f, 0xa4, 0x41, 0x00, 0x04, 0x00,
        0x00, 0x00, 0x50, 0xc3, 0x46, 0xa1, 0x01, 0x00,
        0x00
    ])
    # offset 0-1: 帧计数 (动态)
    struct.pack_into('<H', metadata, 0, _BAND3_FRAME_COUNTER_BASE + frame_counter)
    # offset 2-3: start_index
    struct.pack_into('<H', metadata, 2, start_index)

    # 频谱数据编码 (417点 × 2 = 834 bytes)
    spectrum_data = b''
    try:
        for i, dbm in enumerate(spectrum_dbm[:n_arrays]):
            if dbm < 0:
                byte_val = int(256 + dbm)
            else:
                byte_val = int(dbm)
            if byte_val < 0 or byte_val > 255:
                raise ValueError(f"spectrum_dbm[{i}]={dbm} → byte_val={byte_val} 超出范围(0-255)")
            spectrum_data += bytes([byte_val, 0xFF])
    except Exception as e:
        log.error(f"[FSCAN-434] 频谱编码失败: {e}, start_index={start_index}, n_arrays={n_arrays}")
        # 输出异常值附近的数据用于调试
        start = max(0, i - 5)
        end = min(len(spectrum_dbm[:n_arrays]), i + 6)
        log.error(f"[FSCAN-434] 问题点附近 spectrum_dbm[{start}:{end}] = {spectrum_dbm[start:end]}")
        raise

    # DL = metadata(33) + spectrum_data(834) = 867
    dl = len(metadata) + len(spectrum_data)
    # 帧长 = header(62, 内含DL字段4字节) + spectrum_data
    frame_len = 62 + len(spectrum_data)

    frame = bytearray(frame_len)

    struct.pack_into('<I', frame, 0, SYNC_WORD)
    struct.pack_into('<H', frame, 4, 1)   # VER=1 (little-endian 0x0001)，与真实设备一致
    struct.pack_into('<I', frame, 6, stc)
    frame[10:18] = ts
    struct.pack_into('>H', frame, 18, 0x0168)
    frame[20:24] = _FSCAN_TYPE_434
    frame[24] = _DT_FSCAN
    struct.pack_into('<I', frame, 25, dl)
    frame[29:62] = metadata
    frame[62:] = spectrum_data

    return bytes(frame)


def build_mscan_frame(dbm_level: int, frequency: int = DEFAULT_FREQUENCY, stc: int = None, ts: bytes = None) -> bytes:
    """构建 MSCAN 单频点扫描帧 (45字节)

    帧结构 (参考 working stream):
    - offset 24: DT=13
    - offset 25: DL=16
    - offset 26-29: 频率个数=1
    - offset 30-37: 频率(8字节)
    - offset 38-41: 频率重复?或另一格式
    - offset 43-44: level
    """
    if stc is None:
        stc = 0
    if ts is None:
        ts = _get_streamsrc_timestamp()

    frame = bytearray(45)

    frame[0:4] = struct.pack('>I', SYNC_WORD)      # 0-3: sync
    frame[4:6] = struct.pack('<H', 1)              # 4-5: VER=1
    frame[6:10] = struct.pack('<I', stc)            # 6-9: STC
    frame[10:18] = ts                               # 10-17: timestamp
    frame[18:20] = struct.pack('>H', 21)            # 18-19: PL=21
    frame[20:22] = struct.pack('>H', 0)             # 20-21: EL=0
    frame[22:24] = struct.pack('>H', 0)             # 22-23: reserved

    frame[24] = _DT_MSCAN                           # 24: DT=13
    frame[25] = 16                                  # 25: DL=16
    frame[26:30] = struct.pack('>I', 1)             # 26-29: 频率个数=1

    # 频率: 8字节格式 (offset 30-37)
    # working stream 中该字段可能是一个特殊编码，与实际频率无关
    # test tool 可能从 SOAP 参数获取频率，而非从 streamsrc 帧
    # 尝试写入 0
    frame[30:38] = bytes(8)  # 30-37: frequency (placeholder)

    # level 在 offset 43-44
    struct.pack_into('<H', frame, 43, dbm_level)    # 43-44: level

    return bytes(frame)


def build_pscan_level_frame(dbm_level: int, stc: int = None, ts: bytes = None) -> bytes:
    """构建 PScan 电平数据帧 (40字节) - DT=101"""
    if stc is None:
        stc = 0
    if ts is None:
        ts = _get_streamsrc_timestamp()

    frame = bytearray(40)

    frame[0:4] = struct.pack('>I', SYNC_WORD)
    frame[4:6] = struct.pack('<H', 16)
    frame[6:10] = struct.pack('<I', stc)
    frame[10:18] = ts
    frame[18:20] = struct.pack('>H', 16)
    frame[20:22] = struct.pack('>H', 0)
    frame[22:24] = struct.pack('>H', 0)

    frame[24] = _DT_PSCANLEVEL
    frame[25] = 11
    # bytes 26-33: zeros (reserved)
    frame[34:38] = _FIXED_MSCAN_LEVEL
    frame[38] = dbm_level & 0xFF  # level as uint8
    frame[39] = 0x00

    return bytes(frame)


def build_pscan_itu_frame(itu_value: float, stc: int = None, ts: bytes = None) -> bytes:
    """构建 PScan ITU数据帧 (36字节)

    与真实设备对齐:
    - payload[0]: DT=8
    - payload[1]: DL=7
    - payload[2:6]: zeros
    - payload[6]: item_count=1
    - payload[7]: 0x01 (固定)
    - payload[8:12]: ITU值 (LE float32)
    """
    if stc is None:
        stc = 0
    if ts is None:
        ts = _get_streamsrc_timestamp()

    frame = bytearray(36)

    frame[0:4] = struct.pack('>I', SYNC_WORD)
    frame[4:6] = struct.pack('<H', 16)
    frame[6:10] = struct.pack('<I', stc)
    frame[10:18] = ts
    frame[18:20] = struct.pack('>H', 12)
    frame[20:22] = struct.pack('>H', 0)
    frame[22:24] = struct.pack('>H', 0)

    frame[24] = _DT_PSCANITU  # payload[0]: DT=8
    frame[25] = 7             # payload[1]: DL=7
    # payload[2:6]: zeros (frame[26:30])
    frame[30] = 1             # payload[6]: item_count
    frame[31] = 1             # payload[7]: 固定值
    frame[32:36] = struct.pack('<f', itu_value)  # payload[8:12]: ITU float32 LE

    return bytes(frame)


def build_pscan_spectrum_frame(spectrum_data: list, stc: int = None, ts: bytes = None) -> bytes:
    """构建 PScan 频谱数据帧 (3256字节)

    与真实设备对齐:
    - Header (24B): sync + VER + STC + TS + indicator(PL) + reserved
    - Payload (3232B = PL):
      - DT(1B) + DL(4B) + metadata(25B) + spectrum(3202B)
      - DL = metadata(25) + spectrum(3202) = 3227
    - Metadata (25B, frame[29:54]):
      - [0]:     0x00
      - [1:5]:   n_points (LE uint32)
      - [5:13]:  固定 0x00000000D0129341
      - [13:21]: 固定 0x0050C34600000000
      - [21:25]: n_points (LE uint32, 重复)
    - Spectrum (3202B, frame[54:3256]): n_points × int16 LE
    """
    if stc is None:
        stc = 0
    if ts is None:
        ts = _get_streamsrc_timestamp()

    n_points = min(len(spectrum_data), 1601)

    frame = bytearray(3256)

    # 帧头 (24字节)
    frame[0:4] = struct.pack('>I', SYNC_WORD)
    frame[4:6] = struct.pack('<H', 1)
    frame[6:10] = struct.pack('<I', stc)
    frame[10:18] = ts
    frame[18:20] = struct.pack('>H', 3232)  # PL = payload size
    frame[20:24] = bytes([0x0C, 0x00, 0x00, 0x00])  # fscan_type = 0x0C (与设备一致)

    # Payload DT + DL (5字节)
    frame[24] = _DT_PSCANDATA  # DT=7
    # DL = metadata(25) + spectrum(n_points*2) = 3227
    struct.pack_into('<I', frame, 25, 3227)  # DL
    # frame[26:30]: zeros (payload[2:6])

    # Metadata (25字节, frame[29:54])
    # frame[30:34]: n_points (LE uint32) at payload[6:10]
    struct.pack_into('<I', frame, 30, n_points)
    # frame[34:42]: 设备固定元数据 at payload[10:18]
    frame[34:42] = bytes([0x00, 0x00, 0x00, 0x00, 0xd0, 0x12, 0x93, 0x41])
    # frame[42:50]: 设备固定元数据 at payload[18:26]
    frame[42:50] = bytes([0x00, 0x50, 0xc3, 0x46, 0x00, 0x00, 0x00, 0x00])
    # frame[50:54]: n_points 重复 (payload[26:30])
    struct.pack_into('<I', frame, 50, n_points)
    spectrum_offset = 54
    for i in range(n_points):
        struct.pack_into('<h', frame, spectrum_offset, int(spectrum_data[i]))
        spectrum_offset += 2

    return bytes(frame)