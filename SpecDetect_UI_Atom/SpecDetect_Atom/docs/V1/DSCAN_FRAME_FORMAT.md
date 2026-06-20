# DSCAN 帧格式文档

**创建日期**: 2026-04-24
**更新日期**: 2026-04-24
**数据来源**: `rmcp_DSCAN_9996_20260424_170202.log`

---

## 1. RMCP帧头结构 (18 bytes)

| Offset | 字段 | 大小 | 字节序 | 说明 |
|--------|------|------|--------|------|
| 0-3 | dwLength | 4B | Little | payload长度 |
| 4-13 | Timestamp | 10B | - | 时间戳 |
| 12-13 | nVersion | 2B | Big | 7 (0x0007) |
| 14 | nMsgType | 1B | - | 0=数据帧, 6=控制帧 |
| 15 | nFlags | 1B | - | 0x01 |
| 16-17 | Reserved | 2B | - | - |

**帧总长**: `18 + dwLength` bytes

---

## 2. Business Header (11 bytes, offset 18-28)

| Offset | 字段 | 大小 | 字节序 | 说明 |
|--------|------|------|--------|------|
| 18 | nBdType | 1B | - | 0x10 (16) = DSCAN |
| 19-20 | Reserved | 2B | - | - |
| 21-28 | Counters | 4×int16 | Little | [总通道数, 0, 0, 0] |

**关键发现**:
- `counters[0] = 1441` 表示总通道数(对应PScan的1441点)
- 不是当前帧的数据点数！

---

## 3. Spectrum Data (从offset 29开始)

| 属性 | 值 | 说明 |
|------|-----|------|
| 编码 | int16 | little-endian |
| 转换 | RMCP值 ÷ 10 = dBm | |
| 数据点数 | `(total_size - 18 - 11) / 2` | 动态计算 |

**示例** (total_size=2480):
- Spectrum长度 = 2480 - 18 - 11 = 2451 bytes
- 数据点数 = 2451 / 2 = **1225 points**

---

## 4. 帧类型说明

### 数据帧 (msg_type=0)
- nBdType = 0x10 (16)
- 包含完整的spectrum数据
- 数据点数可能小于1441(分包发送)

### 控制帧 (msg_type=6)
- nBdType = 0x10 (16)
- payload较短(如51字节)
- 用于设备状态/确认消息
- 示例: `len=69` → payload=51字节

---

## 5. 帧解析代码

```python
def parse_dscan_payload(payload: bytes) -> Optional[dict]:
    """解析 DSCAN payload"""
    if len(payload) < 11:
        return None

    n_bd_type = payload[0]
    if n_bd_type != 16:  # DSCAN
        return None

    counters = struct.unpack('<4h', payload[3:11])
    spectrum_offset = 11

    # 数据点数从payload长度计算
    n_arrays = (len(payload) - 11) // 2

    if n_arrays == 0 or n_arrays > 2000:
        return None

    levels = []
    for i in range(n_arrays):
        if spectrum_offset + 2 > len(payload):
            break
        level_raw = struct.unpack('<h', payload[spectrum_offset:spectrum_offset+2])[0]
        levels.append(level_raw)
        spectrum_offset += 2

    return {
        'n_bd_type': n_bd_type,
        'counters': list(counters),
        'n_arrays': n_arrays,
        'levels': levels,
    }
```

---

## 6. 待解决问题

### 6.1 帧长异常 (len=8049)
**现象**: 某些DSCAN帧len=8049，远大于正常值(2480)

**可能原因**:
1. TCP粘包 - 多个帧粘在一起
2. 帧头解析位置错误

**验证方法**: 捕获原始TCP数据，分析8049字节的实际内容

### 6.2 数据点数差异
- counters[0] = 1441 (总通道数)
- 实际数据点数 = 1225 (从2480字节计算)

**结论**: 设备分包发送，每次发送部分数据点

---

## 7. RMCP类型值参考

| n_bd_type | 类型 | 说明 |
|-----------|------|------|
| 0x0B (11) | IFANALYSIS | 605点 |
| 0x0E (14) | SGLFREQ | 单频点 |
| 0x0F (15) | FSCAN | 512/417点 |
| 0x10 (16) | DSCAN | PScan数据 |

| nMsgType | 类型 | 说明 |
|----------|------|------|
| 0 | DATA | 数据帧 |
| 6 | CONTROL | 控制/状态帧 |

---

## 8. 修订历史

| 日期 | 版本 | 修改内容 |
|------|------|---------|
| 2026-04-24 | 1.0 | 初版创建，整理DSCAN帧结构 |
