# PScan streamsrc 帧封装方案

**创建日期**: 2026-04-24
**最后更新**: 2026-04-25
**状态**: 已实现并验证

---

## 1. 方案概述

### 1.1 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| rmcp_levels | List[int] | RMCP DSCAN 数据，4001 点 int16 (80-180MHz, 25kHz步长) |
| pl | int | PL 值 (360/616/872)，仅控制 indicator 字段 |
| stc | int | 通道标识 |
| ts | bytes | 时间戳 (可选) |

### 1.2 输出

streamsrc FSCAN 帧 (DT=12)，2944 字节，1441 点数据

### 1.3 频率映射

```
RMCP:   80-180MHz, 4001点, 25kHz步长
streamsrc: 137-173MHz, 1441点, 25kHz步长

137MHz = RMCP index (137-80)/0.025 = 2280
173MHz = RMCP index (173-80)/0.025 = 3720
slice: rmcp_levels[2280:3721] = 1441点
```

### 1.4 字节编码

```
RMCP int16 ÷ 10 = dBm
dBm → 单字节编码:
  负dBm: 256 + dBm (如 -88 → 168 = 0xA8)
  正dBm: 直接取整, 限制255
第二字节: 0x00 (与真实设备对齐, 不同于 FScan 的 0xFF)
```

---

## 2. 帧结构 (2944 字节)

| Offset | 大小 | 字段 | 值 |
|--------|------|------|-----|
| 0-3 | 4 | Sync | 0xEEEEEEEE |
| 4-5 | 2 | VER | 1 (little-endian) |
| 6-9 | 4 | STC | 通道标识 |
| 10-17 | 8 | Timestamp | streamsrc 时间戳 |
| 18-19 | 2 | Indicator | PL 决定 (大端) |
| 20-23 | 4 | FScanType | 0x0b (IFANALYSIS) |
| 24 | 1 | DT | 12 (FSCAN) |
| 25-28 | 4 | DL | metadata(33) + spectrum(2882) |
| 29-61 | 33 | Metadata | 统一 metadata (start_index=0, 1441ch) |
| 62-2943 | 2882 | Spectrum | 1441点 × 2字节 |

### 2.1 Metadata (33 字节, 所有帧统一)

```
01a1050000000000 80e854a041000000 808a9fa441000000 000050c346a1050000
```

- bytes 29-30: `a105` = 1441 (通道数)

### 2.2 Indicator 与 PL 映射

| Indicator | PL 值 | Band |
|-----------|-------|------|
| 0x0168 | 360 | Band2 |
| 0x0268 | 616 | Band3 |
| 0x0368 | 872 | Band4 |

### 2.3 PL 序列 (与真实设备对齐)

```
帧1: PL=872 (indicator=0x0368)
帧2: PL=616 (indicator=0x0268)
帧3: PL=360 (indicator=0x0168)
帧4: PL=872 (indicator=0x0368)
帧5: PL=616 (indicator=0x0268)
→ 5帧循环
```

---

## 3. 核心函数

### 3.1 build_pscan_fscan_frame()

位置: `src/atom/stream/frame.py`

```python
def build_pscan_fscan_frame(rmcp_levels: list, pl: int, stc: int = 0, ts: bytes = None) -> bytes:
    # 1. 从 RMCP 4001点中选取 137-173MHz 子带 (1441点)
    sub_band = rmcp_levels[2280:3721]

    # 2. 获取参数 (所有帧统一 metadata, PL 仅控制 indicator)
    indicator = _get_pscan_indicator(pl)
    metadata = _get_pscan_metadata()

    # 3. 频谱数据编码 (第二字节 0x00)
    spectrum_data = b''
    for i in range(1441):
        dbm = sub_band[i] / 10.0
        byte_val = int(256 + dbm) if dbm < 0 else min(int(dbm), 255)
        spectrum_data += bytes([byte_val & 0xFF, 0x00])

    # 4. 组装帧 (62头 + 33metadata + 2882spectrum = 2944B)
    ...
```

### 3.2 辅助函数

| 函数 | 说明 |
|------|------|
| `_get_pscan_indicator(pl)` | PL → indicator 映射 |
| `_get_pscan_metadata()` | 返回统一 33 字节 metadata |

---

## 4. 数据流

```
RMCP DSCAN 回调 (4001点, 80-180MHz)
    ↓
receive_pscan_raw() → _parse_raw_dscan()
    ↓
session._pscan_band = { 'levels': [int16 x 4001], ... }
    ↓
push_loop (pscan 分支)
    ↓
_push_frame(session, band)
    ↓
build_pscan_fscan_frame(rmcp_levels, pl, stc)
    ↓
rmcp_levels[2280:3721] → 1441点 (137-173MHz)
    ↓
编码: int16→dBm→单字节 (第二字节 0x00)
    ↓
streamsrc 2944B 帧 → streamsrc_client.sendall()
```

---

## 5. 与旧方案的差异

| 项目 | 旧方案 (已废弃) | 当前方案 |
|------|-----------------|----------|
| 数据来源 | RMCP 605 点 | RMCP 4001 点 [2280:3721] |
| PL 作用 | 控制 payload 点数和 gap 填充 | 仅控制 indicator 字段 |
| 高频填充 | -88dBm 固定值填充 836 点 | 无填充，全部实数据 |
| 帧构建 | 调用 `build_fscan_frame()` | 独立 `build_pscan_fscan_frame()` |
| 帧大小 | 可变 | 固定 2944B |
| 编码 | 第二字节 0xFF | 第二字节 0x00 |

---

## 6. 参考文件

| 文件 | 说明 |
|------|------|
| `src/atom/stream/frame.py` | `build_pscan_fscan_frame()` 实现 |
| `src/atom/service.py` | `_push_frame()` pscan 分支 |
| `src/atom/rmcp/client.py` | `receive_pscan_raw()` + `_parse_raw_dscan()` |
| `docs/PSCAN_STREAMSRC_ARCHIVE_20260424.md` | 帧结构归档 |
