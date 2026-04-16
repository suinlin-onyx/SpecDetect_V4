# 协议规则汇总 - Atom 实现依据

**创建时间**: 2026-04-15
**依据**: GWJ004/GWJ006 SOAP协议文档, RMCPTP v2.0 协议文档
**目标**: 从协议文档中提取 Atom streamsrc 实现的规则依据

---

## 一、核心协议规则

### 1.1 GWJ004 数据帧格式 (SOAP Stream)

**帧头结构 (32 bytes):**

| 字段 | 类型 | 字节数 | 说明 |
|------|------|--------|------|
| LEADER | UINT32 | 4 | 帧头标记 = 0xEEEEEEEE |
| VER | UINT16 | 2 | 版本号 = 01.00 |
| STC | UINT32 | 4 | **同步传输编码** - 唯一标识一路数据通道 |
| TS | TIMESTAMP | 9 | 时间戳 (年+月+日+时+分+秒+毫秒) |
| PL | UINT32 | 4 | 载荷长度 |
| EL | UINT8 | 1 | 扩展帧头长度 (默认0) |

**数据子体结构 (8 + N bytes):**

| 字段 | 类型 | 字节数 | 说明 |
|------|------|--------|------|
| DT | UINT8 | 1 | 数据结果类型 |
| DL | UINT32 | 4 | 数据长度 |
| DATA | - | N | 实际数据 |

**关键规则:**
- **分片传输**: 通过 DT+DL+DATA 嵌套结构实现
- **STC 标识通道**: 每个数据流有唯一 STC 值
- **LEADER 标记**: 0xEEEEEEEE 作为帧同步标记

---

### 1.2 GWJ004 频谱数据格式 (Spectrum)

**spectrum 类型 (DT值待查):**

| 字段 | 类型 | 字节数 | 说明 |
|------|------|--------|------|
| 频率总数量 | UINT32 | 4 | 总频率点个数 n |
| 起始频率 | FLOAT64 | 8 | 测量起始频率, 单位 Hz |
| 步进 | FLOAT32 | 4 | 频率点间隔, 单位 Hz |
| **频率序号** | UINT32 | 4 | **当前帧的起始点序号** |
| **频率数量** | UINT32 | 4 | **当前帧频率数量, m** |
| 频谱数据 | INT16 | 2×m | 单位 0.1 dBμV |

**分片规则:**
- `频率序号` 标识当前帧的起始点在完整频谱中的位置
- `频率数量` 标识当前帧包含的频率点个数
- 接收端通过 `频率序号` 和 `频率数量` 拼接完整频谱

**无效值 (GWJ006):**
- **0xEFFF** (十进制 61439) 表示无效电平

---

### 1.3 RMCPTP 业务数据结构

**业务数据头 (12 bytes):**

```cpp
typedef struct tagRmcpBusinessData
{
    BYTE   nBdType;     // 业务数据类型
    SHORT  nFlags;      // 业务数据标志
    DWORD  nArrays;      // 业务数组个数
    DWORD  nOffset;     // 业务数组偏移
} RMCPBUSINESSDATA;
```

**FSCAN (类型 0x0F = 15):**

| 字段 | 说明 |
|------|------|
| 静态部分 | nBdType=15, nArrays (频段数) |
| 动态部分 | 每段: startfreq, endfreq, Step, nPoints |

**关键字段:**
- **nOffset**: 业务数组偏移 = 相对首索引的偏移量
- 用于分片传输时标识当前数据块在完整数据中的位置

**电平值存储:**
- 实际值 × 100 (如 -70.5 dBm 存储为 -7050)
- INT16, little-endian

---

## 二、streamsrc 协议与协议文档的对应关系

### 2.1 streamsrc 帧结构 vs GWJ004 帧结构

| streamsrc | GWJ004 | 说明 |
|-----------|--------|------|
| 0xEEEEEEEE (offset 0-3) | LEADER | 帧同步标记 |
| offset 4-11 (FILETIME) | TS | 时间戳 |
| offset 12-15 | - | 用途未知 (可能 PL 或扩展) |
| offset 16-17 | - | 帧序号? |
| offset 18 | - | FSCAN 类型低字节 |
| offset 19 | - | 帧序列号 (0x00-0x03) |
| offset 20 | - | FSCAN 类型 (4=FSCAN-529, 3=FSCAN-434) |
| offset 21-27 | - | 用途未知 |
| offset 28+ | DATA | 频谱数据 (18 × 2 bytes) |

**关键发现:**
- streamsrc 的帧结构与 GWJ004 的帧头有相似之处 (LEADER + 时间戳)
- 但 streamsrc 是 Atom 内部私有协议，不完全遵循 GWJ004
- offset 18/19/20 组合标识 FSCAN 类型和帧序列

### 2.2 streamsrc 数据分片 vs GWJ004 分片

| 属性 | streamsrc | GWJ004 |
|------|-----------|--------|
| 每帧电平数 | 18 | m (可变) |
| 分片标识 | offset 19 (序列号) | 频率序号 + 频率数量 |
| 完整频谱 | 529 电平 (~30帧) | n 频率点 |
| 无效值 | -32768 (0x8000) | 0xEFFF |

---

## 三、Atom 数据处理规则 (推测)

### 3.1 RMCPTP → streamsrc 转换

**输入 (Device → Atom via RMCPTP):**

| 属性 | 值 |
|------|-----|
| 协议 | RX-RMCPTP v2.0 |
| nDataType | 0 (业务数据) |
| nBdType | 15 (FSCAN) |
| nArrays | 频段数 |
| nOffset | 数组偏移 |
| 电平单位 | dBm × 100 |

**处理步骤 (推测):**

1. **接收 RMCPTP 数据**
   - 解析业务数据头 (nBdType, nFlags, nArrays, nOffset)
   - 提取电平值数组 (实际值 = 存储值 / 100)

2. **数据格式转换**
   - dBm → dBuV: dBuV = dBm + 107.6
   - 单位转换: dBuV × 10 = 存储值 (0.1 dBμV)
   - 归一化处理: [原始值范围] → [0, 24933]

3. **分片封装**
   - 每 18 电平封装为一帧
   - 添加 0xEEEEEEEE 帧头
   - 添加 FILETIME 时间戳
   - 标识 FSCAN 类型和帧序列

**转换公式 (dBm → streamsrc 原始值):**

```
dBm → dBuV: dBuV = dBm + 107.6
dBuV → 存储: store = dBuV × 10  (因为 GWJ004 单位是 0.1 dBμV)
但 streamsrc 原始值范围是 [0, 24933]
所以可能是: store = (dBm + 107.6) × 10 = (dBm + 107.6) × 10
然后做归一化映射到 [0, 24933]
```

### 3.2 关键疑问

1. **streamsrc 的 529 vs RMCPTP 的 512**
   - RMCPTP FSCAN 描述中 nPoints 是频段内的点数
   - streamsrc 固定 529 电平/完整频谱
   - 差异可能来自不同的扫频参数设置

2. **nOffset 在 streamsrc 中的对应**
   - RMCPTP 有 nOffset 字段标识分片偏移
   - streamsrc 的帧序列号 (offset 19) 可能起同样作用
   - 但 streamsrc 的完整帧判断可能依靠 100ms 时间间隔

3. **无效值转换**
   - RMCPTP 无统一无效值
   - streamsrc 使用 -32768 (0x8000)
   - Atom 可能将低于某阈值的值映射为 -32768

---

## 四、协议规则索引

| 规则描述 | 来源文档 | 章节 |
|----------|----------|------|
| LEADER = 0xEEEEEEEE | GWJ004 | 5.17 |
| STC 唯一标识通道 | GWJ004 | 5.17 |
| 频率序号/数量 分片 | GWJ004 | spectrum 格式 |
| 无效值 0xEFFF | GWJ006 | 数据存储结构 |
| dBuV = dBm + 107.6 | GWJ006 | 单位转换 |
| nOffset 数组偏移 | RMCPTP | 4.3 业务数据 |
| 电平值 × 100 | RMCPTP | 4.3.1 |
| nBdType = 15 (FSCAN) | RMCPTP | 4.1 |

---

## 五、待验证点

1. **streamsrc 的 DT 值**: GWJ004 中 spectrum 的 DT 类型码是什么?
2. **streamsrc 的 STC**: 是否有类似 STC 的通道标识字段?
3. **nOffset 在 streamsrc 中的对应**: 是 offset 19 的帧序列还是其他字段?
4. **归一化算法**: streamsrc 的 [0, 24933] 范围是如何计算的?

---

## 参考文档

- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\soap协议\GWJ004-2015超短波监测管理一体化服务接口规范 数据服务部分.md`
- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\soap协议\GWJ006-2016超短波频段监测基础数据存储结构技术规范.md`
- `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\无线电协议2.0\RX-RMCPTP_通信协议v2.0_通用协议_整理.md`
