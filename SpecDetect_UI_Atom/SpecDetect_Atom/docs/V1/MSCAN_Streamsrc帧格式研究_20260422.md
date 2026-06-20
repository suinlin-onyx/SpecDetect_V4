# MSCAN streamsrc 帧格式研究

创建时间：2026-04-22
更新时间：2026-04-25

---

## MSCAN streamsrc 帧格式 (45 字节)

### 帧头 (24 字节)

| Offset | 大小 | 字段 | 来源 | 说明 |
|--------|------|------|------|------|
| 0-3 | 4 | Sync | 固定 | `0xEEEEEEEE` (大端) |
| 4-5 | 2 | VER | 固定 | `1` (小端) |
| 6-9 | 4 | STC | 配置 | `session.fscan_params['stc']` |
| 10-17 | 8 | TS | 生成 | `_get_streamsrc_timestamp()` |
| 18-19 | 2 | PL | 固定 | `21` (大端) = payload 长度 |
| 20-21 | 2 | EL | 固定 | `0` (大端) |
| 22-23 | 2 | PAD | 固定 | `0` |

### 帧体 (21 字节)

| Offset | 大小 | 字段 | 来源 | 说明 |
|--------|------|------|------|------|
| 24 | 1 | DT | 固定 | `13` = MSCAN 类型 |
| 25 | 1 | DL | 固定 | `16` |
| 26-29 | 4 | freq_count | 固定 | `1` (大端) |
| 30-33 | 4 | frequency | 配置 | `session.fscan_params['frequency']` (Hz, 大端) |
| 34-37 | 4 | fixed | 固定 | `0x00000001` |
| 38-41 | 4 | fixed | 固定 | `0x0084D797` |
| 43-44 | 2 | level | RMCP | `band.get('levels', [0])[0] // 10` (小端) |

---

## 数据来源汇总

### 从配置获取 (session.fscan_params)

| 字段 | 来源 | 默认值 |
|------|------|--------|
| stc | `session.fscan_params['stc']` | int(time.time()) |
| frequency | `session.fscan_params['frequency']` | "100000000" (100MHz) |

### 从 RMCP 解析

| 字段 | 来源 | 说明 |
|------|------|------|
| level | SGLFREQ payload offset 11-12 | int16, little-endian, ÷10 转换为 dBm |

### 固定值

| 字段 | 值 |
|------|-----|
| Sync | `0xEEEEEEEE` |
| VER | `1` |
| PL | `21` |
| EL | `0` |
| PAD | `0` |
| DT | `13` |
| DL | `16` |
| freq_count | `1` |
| fixed (offset 34-37) | `0x00000001` |
| fixed (offset 38-41) | `0x0084D797` |

---

## RMCP SGLFREQ 帧解析

### RMCP 帧格式 (总长 49 字节)

| 部分 | 大小 | 说明 |
|------|------|------|
| RMCP Header | 18 | 标准 RMCP 帧头 |
| Payload | 31 | SGLFREQ 业务数据 |

### RMCP Header

| Offset | 大小 | 字段 | 说明 |
|--------|------|------|------|
| 0-3 | 4 | dwLength | 帧长度 (小端) |
| 4-11 | 8 | tmStamp | 时间戳 (小端) |
| 12-13 | 2 | nVersion | 版本号 (大端，必须为 7) |
| 14 | 1 | nMsgType | 消息类型 |
| 15 | 1 | nFlags | 标志 |
| 16-17 | 2 | nCheckSum | 校验和 |

### RMCP Payload (SGLFREQ, 31 bytes)

| Offset | 大小 | 字段 | 说明 |
|--------|------|------|------|
| 0 | 1 | n_bd_type | `14` = SGLFREQ |
| 1-8 | 8 | counters | 4 * int16 (little-endian) |
| 9-10 | 2 | ? | 未知 |
| 11-12 | 2 | level | int16, little-endian |

### 示例

```
RMCP SGLFREQ payload: 0e010001000000000000000d02
                      │└─┬─┘│││││││││└─┬─┘
                      │   │ │ │ │ │ │ │ │  └─ level = 0x020d = 525
                      │   │ │ │ │ │ │ │ │      (39.6 dBm)
                      │   │ │ │ │ │ │ │ │      
n_bd_type=14 ─────────┘   │ │ │ │ │ │ │ │
counters[0]=1 ───────────┘ │ │ │ │ │ │ │
counters[1]=0 ──────────────┘ │ │ │ │ │ │
counters[2]=0 ────────────────┘ │ │ │ │ │
counters[3]=0 ──────────────────┘ │ │ │ │
?=0 ──────────────────────────────┘ │ │ │
?=0 ─────────────────────────────────┘ │ │
```

---

## 关键问题

### 1. RMCP nVersion 校验缺失

**问题**：`receive_responses` 只校验 `dwLength` 是否在 18~10000 范围内，没有校验 `nVersion` 是否为 7。

**后果**：垃圾数据可能被当作有效帧处理。

**修复**：在帧解析时校验 `nVersion == 7`。

### 2. TCP 粘包导致帧解析偏移

**问题**：日志显示帧数据从 offset 11 开始才是有效的 RMCP 帧。

**示例**：
```
日志帧数据: 00010000000000000095... (274 bytes)
             ↑ 垃圾数据 (11 bytes)
offset 11: 1f000000... (真正的 RMCP 帧开始)
```

**修复**：
1. 在帧解析时校验 `nVersion == 7`
2. 如果 nVersion != 7，跳过 1 字节继续寻找

### 3. level 解析位置

**确认**：SGLFREQ level 在 payload offset 11-12 (little-endian)

**示例**：
- payload: `0e010001000000000000000d02`
- offset 11-12: `0d02` = 525 (little-endian)
- 实际电平: 525 / 10 = 52.5 dBm

---

## 相关文件

- `src/atom/rmcp/client.py` - receive_responses 方法
- `src/atom/rmcp/frame.py` - parse_fscan_payload 函数
- `src/atom/stream/frame.py` - build_mscan_frame 函数
- `src/atom/service.py` - B_MScan 处理和帧推送

---

## 当前状态 (2026-04-25)

- nVersion 校验: ✅ 已在 `validate_rmcp_frame()` 中实现
- frequency: ✅ 已修复为 Hz 数值格式
- level: ✅ 从 RMCP IFANALYSIS 回调获取真实数据
- 推送间隔: ✅ MScan 使用 `session._latest_band_info` 机制
