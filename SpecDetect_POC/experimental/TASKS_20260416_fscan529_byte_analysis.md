# 任务清单 - FSCAN-529 字节级结构解析

**创建时间**: 2026-04-16
**来源**: `streamsrc_raw_20260416_101328.log` (428帧) + `raw_fscan_20260416_101230.log` (rmcp配对数据)
**目标**: 破解 streamsrc FSCAN-529 帧的字节级结构，找出元数据与频谱数据的精确分界

---

## 一、streamsrc 单帧结构（65 字节）

```
Offset 0-3:   0xEEEEEEEE  (LEADER, 帧同步标记)
Offset 4-27:  24 bytes header
              offset 4  = 0x01 (固定)
              offset 19 = 0x26 (FSCAN-529) 或 0x68 (FSCAN-434)
Offset 28-37: vals[0:5] = [256, 1441, 0, 0, -32768]  ← 固定元数据头
Offset 38-63: vals[5:17] = 13 个 int16  ← 频谱电平数据
Offset 64-64: padding (3 bytes)
```

**验证**: 428 帧中 vals[0:5] 完全固定 = `[256, 1441, 0, 0, -32768]`，无一帧例外。

| vals[index] | 值 | 含义 |
|-------------|-----|------|
| vals[0] | 256 | FFT 窗口参数（固定，428/428帧） |
| vals[1] | 1441 | 总信道数（137~173MHz / 25kHz） |
| vals[2] | 0 | 保留 |
| vals[3] | 0 | 保留 |
| vals[4] | -32768 | 无效值标记 |
| vals[5:17] | 13×int16 | 该帧的频谱电平（原始值） |

---

## 二、重组算法验证

**重组逻辑**（对齐 `atom_streamsrc_listener.py`）:
```python
buffer_529.extend(result['levels'])  # 拼接所有 FSCAN-529 帧的 18 int16
while len(buffer_529) >= 529:
    spectrum = buffer_529[:529]
    buffer_529 = buffer_529[529:]
    output_spectrum('FSCAN-529', spectrum, elapsed)
```

**428帧重组结果**:
- FSCAN-529: 9 完整帧（帧#44,88,133,176,220,265,308,353,397 触发输出）
- FSCAN-434: 5 完整帧
- 总计: 14 完整频谱 ✅ 与 spectrum_log 完全吻合

---

## 三、元数据在重组 buffer 中的分布

**关键发现**: 元数据 `[256,1441,0,0,-32768]` 均匀分布在重组 buffer 中，间隔完全恒定 = 18。

```
FSCAN-529#1: 256位置 = [0, 18, 36, 54, 72, 90, ..., 522]  (30个)
FSCAN-529#2: 256位置 = [11, 29, 47, 65, 83, ..., 515]     (29个)
FSCAN-529#3: 256位置 = [4, 22, 40, 58, 76, ..., 526]      (30个)

间隔恒为 18: [18, 18, 18, 18, 18, ...]
```

**原因**: 529 不能被 18 整除（529 = 29×18 + 7），导致每帧起始偏移不同，元数据"穿插"在频谱数据中。

---

## 四、频谱数据点计数

**重组后 buffer 结构**:
```
每帧: 5(元数据) + 13(频谱) = 18 int16
FSCAN-529#1: 30 帧 → 30×18 = 540 int16
             → 去掉最后 11 int16（凑 529）: 30×13 - 11 = 379 有效频谱点
             → 实际提取: 379 点 ✅

FSCAN-529#2: 29 帧（起始偏移 11）→ 纯频谱点数因起始偏移而不同
```

| 帧 | 256位置数 | 帧数 | 纯频谱点数 |
|----|-----------|------|-----------|
| #1 | 30 | 30 | 379 |
| #2 | 29 | 29 | 379（实际） |
| #3 | 30 | 30 | 377 |

---

## 五、streamsrc vs rmcp 数据对比 (2026-04-16 更正)

**配对数据**: streamsrc `18012.pcap` ↔ rmcp `9996.pcap`（同一时刻抓包）

**重大发现**: 之前的结论错误！两者512点完全匹配。

| 属性 | streamsrc (旧结论) | streamsrc (正确) | rmcp |
|------|-------------------|-------------------|------|
| 帧大小 | 65 bytes | **1086 bytes** | 1053 bytes |
| 点数/帧 | 379 (需提取) | **512** | 512 |
| 数据格式 | 复杂转换 | **直接dBm整数** | dBm×10 |
| dBm 范围 | [-75.8, -28.7] | **-101 ~ -30** | -101.5 ~ -30.5 |

**帧类型判断**:
- 65 bytes = 注册帧 (含UUID，无频谱数据)
- 1086 bytes = **频谱帧** (512点完整数据)

**解析算法**:
```python
def parse_streamsrc_spectrum(data: bytes) -> list:
    # 频谱从偏移48开始
    vals = struct.unpack('<h' * ((len(data) - 48) // 2), data[48:])
    return list(vals[7:7+512])  # 跳过7个元数据，取512点
```

**转换公式**:
```
streamsrc_dBm = raw_value              # 直接使用
rmcp_dBm = raw_value / 10.0          # 存储×10
```

**验证结果**:
- Pearson相关系数: **0.9997**
- 差值<1dB: **99.8%**
- **结论**: streamsrc与rmcp提供**完全相同的512点频谱数据**。

---

## 六、关键技术细节

### 注册帧是关键
必须发送注册帧（`REG_FRAME_TEMPLATE[:29] + taskid`），Atom 才发 streamsrc 数据。
不发送则连接成功但无数据（Atom 静默关闭连接）。

### SOAP 请求结构
必须对齐 `atom_streamsrc_listener.py` 的格式：
- URL: `POST /B_FScan`（不是 `POST /`）
- SOAPAction 头必须
- equpara: `<srrc:groupitems><srrc:groupitem><srrc:items><srrc:item><srrc:paraname>X</srrc:paraname><srrc:paravalue>Y</srrc:paravalue></srrc:item>...`

### 帧大小判断
`data[4] == 0x01` 判断是否为 65 字节帧，而不是 `data[19] == 0x26`。

---

## 七、生成文件

- `experimental/logs/streamsrc_raw_20260416_101328.log` — 428帧原始日志
- `experimental/logs/spectrum_20260416_101328.log` — 14完整频谱日志
- `rmcp_proxy/capture/raw_fscan_20260416_101230.log` — rmcp配对数据

---

**归档时间**: 2026-04-16
**验证状态**: ✅ 模拟重组算法与 listener 日志完全吻合
