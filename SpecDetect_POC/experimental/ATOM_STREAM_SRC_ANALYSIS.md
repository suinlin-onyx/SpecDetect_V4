# Atom streamsrc 协议分析文档

**创建时间**: 2026-04-15
**依据**: GWJ004/GWJ006 SOAP协议文档, RMCPTP v2.0 协议文档
**目标**: 理解 Atom 收到设备数据后如何在 streamsrc 中回传

---

## 一、协议链路梳理

```
设备 (Device) --RMCPTP--> Atom --SOAP/stream--> TestTool/客户端
                      |
                      +-- streamsrc (18012) --> 数据回调
```

### 1.1 Device → Atom 数据通道

**协议**: RX-RMCPTP v2.0
**端口**: 设备连接到 Atom (目标端口待确认)
**数据**: FSCAN 频段扫描数据

### 1.2 Atom → streamsrc 数据通道

**协议**: Atom 内部私有协议
**端口**: 18012
**数据**: 分片传输的频谱数据

---

## 二、RMCPTP 协议 (Device → Atom)

### 2.1 FSCAN 业务数据类型

| 字段 | 类型 | 说明 |
|------|------|------|
| nBdType | byte | 业务数据类型 = 15 (FSCAN) |
| nFlags | short | 业务数据标志 |
| nArrays | long | 动态数组数目 |
| nOffset | long | 相对首索引偏移（频率索引） |

### 2.2 FSCAN 电平数据

- **单位**: 实际值 × 100 (如 -70.5 dBm 存储为 -7050)
- **类型**: INT16, little-endian
- **无效值**: 无统一标记（由设备定义）

### 2.3 RMCPTP 帧头 (18 bytes)

| 字节位置 | 字段 | 类型 | 说明 |
|:--------:|------|------|------|
| 1-4 | dwLength | DWORD | 报文总长度 |
| 5-12 | tmStamp | FILETIME | 报文时间戳 |
| 13-14 | nVersion | WORD | 版本号 (=7) |
| 15 | nDataType | BYTE | 报文数据类型 |
| 16 | nFlags | BYTE | 报文标志 |
| 17-18 | nCheckSum | WORD | 头校验和 |

---

## 三、SOAP Stream 协议 (GWJ004)

### 3.1 频谱数据格式 (spectrum)

**返回方式**: stream (异步 TCP 流)

| 名称 | 类型 | 字节数 | 说明 |
|------|------|--------|------|
| 频率总数量 | UINT32 | 4 | 总频率点个数 n |
| 起始频率 | FLOAT64 | 8 | 测量起始频率, 单位 Hz |
| 步进 | FLOAT32 | 4 | 频率点间隔, 单位 Hz |
| 频率序号 | UINT32 | 4 | 当前帧的起始点序号 |
| 频率数量 | UINT32 | 4 | 当前帧频率数量 m |
| 频谱数据 | INT16 | 2×m | 单位 0.1 dBμV |

**分片机制**: 通过 "频率序号" 和 "频率数量" 字段实现分片传输

### 3.2 无效值标记

根据 GWJ006 数据存储结构文档:
- **无效值**: 0xEFFF (十进制 61439)
- **说明**: 当电平值为 0xEFFF 时表示此值无效

---

## 四、streamsrc 协议分析

### 4.1 streamsrc 帧格式 (65 bytes)

```
Offset 0-3:   0xEEEEEEEE (帧头标记)
Offset 4-27:  24字节头
Offset 28+:   电平数据 (18 × 2 bytes)
```

### 4.2 streamsrc 帧结构 (65 bytes)

```
Offset 0-3:   0xEEEEEEEE (帧头标记)
Offset 4-11:  FILETIME 时间戳 (8 bytes)
Offset 12-15: 4 bytes (用途未知)
Offset 16-17: 帧序号 (uint16)
Offset 18:    FSCAN 类型低字节
  - 0x26 = FSCAN-529
  - 0x68 = FSCAN-434
Offset 19:    帧序列号 (0x00-0x03)
Offset 20:    FSCAN 类型 (4=FSCAN-529, 3=FSCAN-434)
Offset 21-27: 用途未知
Offset 28-63: 电平数据 (18 × 2 bytes, signed short)
```

### 4.3 streamsrc 帧类型判断

根据 offset 19 和 offset 20 的组合:

| offset 19 | offset 20 | 类型 | 说明 |
|-----------|-----------|------|------|
| 0x26 | 4 | FSCAN-529 | 频段扫描 529 电平 |
| 0x68 | 3 | FSCAN-434 | 频段扫描 434 电平 |
| 0x26 | 0 | STATUS | 状态帧 |

### 4.4 streamsrc 帧电平数据特点

**重要发现**:
- 每个 65 字节帧包含 **18 个电平** (36 bytes)
- **前 5 个值** `[256, 1441, 0, 0, -32768]` 可能是**帧头/元数据**
- **后 13 个值** 是实际的频谱数据
- `-32768` 是无效值标记

**帧序列**:
- offset 18 在 0x00-0x03 之间循环
- 同一 FSCAN 类型的多帧组合传输完整频谱

### 4.3 streamsrc 数据特点

- **分片传输**: 每帧仅 18 个电平
- **完整频谱**: 需要多个分片帧拼接 (529 电平 ≈ 30 帧)
- **时间间隔**: 约 100ms 一帧
- **无效值**: -32768 (0x8000)

### 4.4 streamsrc 数据转换

**原始值范围**: [0, 24933]
**dBuV 范围**: [0, 78.9]
**dBm 转换**: dBm = dBuV - 107.6

```python
SS_MIN = -32768  # 无效值标记
SS_MAX = 24933   # 最大值
DBUV_MIN = 0.0   # dBuV 最小值
DBUV_MAX = 78.9  # dBuV 最大值

def streamsrc_to_dbm(value):
    if value == SS_MIN:
        return None
    norm = (value - SS_MIN) / (SS_MAX - SS_MIN)
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    dbm = dbuv - 107.6
    return round(dbm, 1)
```

---

## 五、Atom 数据处理流程推测

### 5.1 数据流

```
Device (RMCPTP) → Atom → streamsrc (18012)
                      ↓
                SOAP 响应
```

### 5.2 Atom 内部处理推测

基于协议文档分析，Atom 收到设备数据后:

1. **接收 RMCPTP 数据**
   - 解析 FSCAN 业务数据
   - 提取电平值 (原始值 × 100)

2. **数据格式转换**
   - RMCPTP 电平单位: dBm (× 100)
   - streamsrc 电平单位: dBuV (× 10)
   - **转换关系**: dBuV = dBm + 107.6

3. **分片处理**
   - streamsrc 每帧 18 电平
   - 可能按照固定频率间隔分片
   - 或按时间周期分片

### 5.3 关键疑问

1. **streamsrc 分片拼接机制**
   - 依靠 100ms 时间间隔判断属于同一频谱？
   - 还是帧中包含频谱 ID/序号标记？

2. **529 vs 512 电平差异**
   - streamsrc FSCAN-529: 529 电平
   - RMCPTP FSCAN: 512 电平
   - 差异 17 电平来自哪里？

3. **无效值转换**
   - RMCPTP: 无统一无效标记
   - streamsrc: -32768 (0x8000)
   - 转换规则是什么？

---

## 六、协议对比总结

| 属性 | RMCPTP (Device→Atom) | streamsrc (Atom→回调) |
|------|---------------------|----------------------|
| 帧头 | 18 bytes | 0xEEEEEEEE + 24 bytes |
| 电平数 | 512 | 529 / 434 |
| 分片 | nOffset 字段 | 每帧 18 电平 |
| 无效值 | 无统一 | -32768 |
| 电平单位 | dBm (×100) | dBuV (需转换) |
| 时间戳 | FILETIME | FILETIME (offset 4-11) |

---

## 七、待验证点

1. **streamsrc 帧中是否有频谱 ID 标记**
   - 需要分析 offset 20-27 的值变化规律

2. **529 vs 512 电平的对应关系**
   - 同一频率范围，不同分割方式？
   - 还是完全不同？

3. **无效值映射规则**
   - RMCPTP 中无效数据如何转换为 streamsrc 的 -32768？

---

## 参考文档

- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\soap协议\GWJ004-2015超短波监测管理一体化服务接口规范 数据服务部分.md`
- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\soap协议\GWJ006-2016超短波频段监测基础数据存储结构技术规范.md`
- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\无线电协议2.0\RX-RMCPTP_通信协议v2.0_通用协议_整理.md`
- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\无线电协议2.0\无线电管理综合平台.通信协议v2.0_通用协议.html`
