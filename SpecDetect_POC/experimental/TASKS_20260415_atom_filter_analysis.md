# 任务清单 - Atom 滤波与变换分析

**创建时间**: 2026-04-15
**最后更新**: 2026-04-15 (分析进行中)
**目标**: 探究 Atom 对设备原始数据进行了怎样的滤波与变换，得到输出向 streamsrc 的结果

---

## 背景

### 问题描述

streamsrc (18012) 和 rmcp 收到的设备原始数据存在显著差异：

| 属性 | streamsrc (529) | rmcp |
|------|-----------------|------|
| 原始值范围 | [0, 24933] | [-1055, -289] |
| dBm 范围 | [-75.8, -28.7] | [-109.4, -22.7] |
| 值特征 | 大量重复值 | 变化剧烈 |
| 无效值 | -32768 | 无 |

### 待解决问题

1. **rmcp 收到的 device 数据，是如何做的数据块切分？** 每约 100ms 有一组数据
2. **Atom 对原始数据进行了怎样的滤波/变换？**
3. **streamsrc 数据与 rmcp 数据的对应关系是什么？**

---

## 分析任务

### Task #1: rmcp 数据块切分机制分析

**目标**: 理解设备数据如何被切分成块

**分析点**:
- 每 100ms 收到 512 电平数据
- 这 512 电平是一次 FFT 结果还是多次累加？
- 数据块大小是否固定？

### Task #2: streamsrc 分片帧拼接机制

**目标**: 理解 streamsrc 分片帧如何拼接成完整频谱

**streamsrc 协议特点**:
- 每帧 65 bytes，只包含 18 个电平（分片传输）
- 需要多个分片帧才能拼出完整频谱（529 电平需 ~30 帧）
- 时间间隔约 100ms 一帧

**分析点**:
- 拼接是依靠 **100ms 时间间隔** 还是 **数据中的标记**？
- 如果是时间间隔：每 100ms 的多个帧属于同一个频谱
- 如果是数据标记：帧中是否有频谱 ID 或序号标记

**待分析**:
1. 统计 100ms 时间间隔内的 streamsrc 帧数量
2. 检查帧中是否有频谱序号或频谱 ID 标记
3. 分析 offset 20-23 的值变化规律

### Task #3: rmcp vs streamsrc 数据匹配方式

**目标**: 探索 rmcp 和 streamsrc 发出的数据在 100ms 间隔间的匹配关系

**分析点**:
- rmcp 每 100ms 发出的数据与 streamsrc 的关系
- 同一时刻两个通道的数据是否有对应关系
- 时间戳对齐方式

**验证方法**:
1. 同步测试：同时启动 rmcp_proxy 和 streamsrc_listener
2. 对比同一 100ms 窗口内的两种数据
3. 检查数据特征是否有匹配（如峰值位置）

### Task #4: streamsrc vs rmcp 原始数据对比

**目标**: 找出两种数据的对应关系

**分析点**:
- 同一时刻的 streamsrc 分片帧 vs rmcp 完整帧
- streamsrc 分片重组后的完整数据 vs rmcp 数据
- 频率点对应关系（529 vs 512 电平）

### Task #5: Atom 内部变换推测

**目标**: 理解 Atom 对设备数据的处理逻辑

**可能处理**:
1. **归一化**: 0-24933 映射到固定 dBuV 范围
2. **底噪滤波**: 过滤低于某阈值的信号
3. **平滑处理**: 多帧平均
4. **单位转换**: dBuV → dBm 转换

---

## 待验证假设

### 假设1: streamsrc 数据经过了归一化处理

**依据**: streamsrc 原始值范围 [0, 24933] 集中在某些固定值

**验证方法**: 
- 统计 streamsrc 原始值分布
- 与 rmcp 原始值分布对比

### 假设2: streamsrc 进行了底噪滤波

**依据**: streamsrc 大量出现 -32768 (无效值) 和 -62.8 左右的值

**验证方法**:
- 分析 -62.8 这个频繁出现的值
- 确认是否为系统底噪

### 假设3: streamsrc 与 rmcp 的时间戳对应

**依据**: rmcp 早于 streamsrc 约 6 秒

**验证方法**:
- 同步测试，同时启动两个监听
- 确认是否为同一采样数据

---

## 输出要求

1. **Atom 变换流程图**: 设备原始数据 → Atom 处理 → streamsrc 输出
2. **转换公式**: 从 rmcp 原始值推导 streamsrc 原始值
3. **时间同步方案**: 如何对齐两个数据源

---

## 新增需求: 获取完整频谱数据

### 频谱数据获取方式对比

**路径A (当前问题)**:
- SOAP → streamsrc (18012)
- 压缩数据 (~529点, ~10级精度)
- 特点: 有损压缩, 底噪钳制, 量化丢失

**路径B (期望)**:
- SOAP → GWJ004 完整数据
- 完整 1441 点, 整数 dBm 精度
- 数据格式: LEADER|VER|STC|TS|PL|EL|DT|DL|SPECTRUM_DATA
- 帧结构: 512+512+417 分三帧, ~330ms/扫描周期

### 核心区别
- `streamsrc`: Atom 私有压缩协议, 65字节/帧, 18电平/帧
- `GWJ004`: 国标完整数据格式, 1441点全量

---

## 分析进度

### 完成: 协议文档分析

**创建文档**: `experimental/PROTOCOL_RULES_SUMMARY.md`

**协议规则索引:**

| 规则 | 来源 | 章节 |
|------|------|------|
| LEADER = 0xEEEEEEEE | GWJ004 | 5.17 |
| STC 唯一标识通道 | GWJ004 | 5.17 |
| 频率序号/数量 分片 | GWJ004 | spectrum 格式 |
| 无效值 0xEFFF | GWJ006 | 数据存储结构 |
| dBuV = dBm + 107.6 | GWJ006 | 单位转换 |
| nOffset 数组偏移 | RMCPTP | 4.3 业务数据 |
| 电平值 × 100 | RMCPTP | 4.3.1 |
| nBdType = 15 (FSCAN) | RMCPTP | 4.1 |

**关键发现:**
- streamsrc 帧结构 (0xEEEEEEEE + 24字节头) 与 GWJ004 帧头相似
- streamsrc 分片机制 (offset 19 序列号) 与 RMCPTP nOffset 不同
- streamsrc 无效值 -32768 与 GWJ006 的 0xEFFF 不同

### Task #1 完成: rmcp 数据块切分机制 ✅

**来源**: `rmcp_proxy/capture/raw_fscan_20260414_215655.log` (1935行)
**发现**:
- FSCAN 1441点 = 512+512+417 分三帧，~110ms/帧，~330ms/组
- Payload 结构: byte 0=nBdType(0x0F), byte 3-6=nArrays(512/417), byte 7-10=帧序号
- 帧大小 [1053, 1053, 863] bytes 循环，验证总点数 1441 = 512+512+417
- 扫描频率 ~3Hz

### Task #2 完成: streamsrc 分片帧拼接机制 ✅

**来源**: `logs/streamsrc_raw_20260415_163535.log` (31帧)
**发现**:
- 帧结构: offset 0-3=LEADER(0xEEEEEEEE), 4-11=FILETIME(会话级), 12-15=常数, 16-19=标识, 19=类型(0x26/0x68), 20-23=类型码(4/3)
- 数据区: 5 int16 元数据 [256, 1441, 0, 0, -32768] + 13 int16 频谱电平
- **拼接机制: 时间驱动，无帧内序列号**，~110ms 间隔区分频谱边界
- 每帧有效电平: 13 个
- 交替模式: [529][529][434] 循环，30帧/FSCAN-529

### Task #3 完成: rmcp vs streamsrc 数据匹配 ✅

**来源**: 配对日志 `raw_fscan_20260415_163533.log` ↔ `streamsrc_raw_20260415_163535.log`
**发现**:
- 时间对齐: Δ<1ms，两者同时开始（16:35:36.085/086）
- 数据精度: rmcp 702级@0.1dB → streamsrc ~10级@1dB（压缩70倍）
- dBm范围: rmcp [-115.4, -15.4] → streamsrc [-75.8, -28.7]（动态范围压缩）
- 噪声地板: streamsrc raw=0 占30.7% → -62.8 dBm（地板钳制）
- streamsrc 是 rmcp 的**有损压缩版本**，同源于 Device 信号

### Task #5 完成: Atom 内部变换推测 ✅

**来源**: 同上配对日志 + 统计分析
**发现**:
- streamsrc 输出分布: 9个有效电平@1dB精度，总动态范围47dB
- Atom 变换算法:
  1. 地板钳制: 输入 < -62.8 dBm → 输出 = -62.8 dBm（影响54.9%数据）
  2. 分段量化: 近地板段(-76~-62dB)约1-3dB步进，高电平段(-46~-29dB)约3-5dB步进
  3. 私有编码: 映射为 streamsrc 私有 raw 值（非直接 dBuV 线性编码）
- 关键洞察: streamsrc 不是 rmcp 线性压缩，而是**非均匀量化 + 地板钳制**

### Task #4 完成: FSCAN-529 字节级结构解析 ✅

**来源**: `logs/streamsrc_raw_20260416_101328.log` (428 帧) + 重组验证
**依据**: 对齐 `atom_streamsrc_listener.py` 精确重组算法，结果完全吻合

**65字节帧结构 (528 bytes header + 37 bytes data + padding)**:
```
Offset 0-3:   0xEEEEEEEE (LEADER, 固定)
Offset 4-27:  24 bytes header (包含 offset 19=0x26/0x68 标识类型)
Offset 28-29: vals[0] = 256         ← 元数据: FFT窗口参数 (428/428帧完全固定)
Offset 30-31: vals[1] = 1441       ← 元数据: 总信道数 (137~173MHz/25kHz)
Offset 32-33: vals[2] = 0          ← 元数据: 保留
Offset 34-35: vals[3] = 0          ← 元数据: 保留
Offset 36-37: vals[4] = -32768     ← 元数据: 无效值标记 (固定)
Offset 38-65: vals[5:17] = 12 vals ← 频谱数据 (每帧13个有效值)
Offset 66-64: 3 bytes padding/校验
```

**重组算法**:
- `buffer_529.extend(result['levels'])` — 拼接所有 FSCAN-529 帧的 18 int16
- 每当 buffer ≥ 529: 切片前 529 值输出，剩余留在 buffer
- FSCAN-529 需要 ≈30 帧 (30×18=540) 才能触发一次输出
- FSCAN-434 需要 ≈25 帧 (25×18=434)

**关键发现: 元数据分散拼接**:
```
[帧1: META5 + 频谱12] + [帧2: META5 + 频谱13] + ...
→ buffer = [M1,M2,M3,...,数据拼, M_帧N,M_帧N+1,...]
→ 输出: [META_帧1前5, 频谱13_帧1, 频谱12_帧2, META_帧2前5, 频谱13_帧2, 频谱12_帧3, ...]
→ META值穿插在频谱数据中!
```

**428帧重组结果**:
- FSCAN-529: 9 完整帧 (帧#44,88,133,176,220,265,308,353,397 触发)
- FSCAN-434: 5 完整帧
- 总计: 14 完整频谱 ✅ 与 spectrum_log 完全吻合

**重建后的元数据头定位**:
| 元数据值 | 含义 | 定位 |
|---------|------|------|
| 256 | FFT 窗口参数 | buffer每18值的首位置附近 |
| 1441 | 总信道数 (137~173MHz/25kHz) | 同上 |
| 0, 0 | 保留 | 同上 |
| -32768 | 无效值标记 | 同上 |
| 其余12值 | 该帧的13个频谱电平 | 填充在 META 值周围 |

### Task #B 完成: streamsrc vs rmcp 数据对比 ✅

**来源**: streamsrc `streamsrc_raw_20260416_101328.log` ↔ rmcp `raw_fscan_20260416_101230.log`（同一时段）

**关键发现**:

| 属性 | streamsrc FSCAN-529 | rmcp FSCAN |
|------|---------------------|-----------|
| 总 buffer | 529 int16/帧 | 512 电平/帧 |
| 有效频谱点 | **379**（去元数据后） | **512** |
| 压缩比 | ~3.8:1 | 1:1 |
| 覆盖范围 | ~9.5 MHz（137~146.5MHz） | 36 MHz（137~173MHz） |
| 帧速率 | ~3 Hz | ~3 Hz（每扫描周期） |
| 精度 | ~16 级量化 | 702 级 |
| 元数据分布 | 每 18 值固定穿插 | 无 |

**数据关系**: streamsrc 是 rmcp 的**实时压缩监测版本**，同源于 Device 信号但用途不同。

### 进行中: Task #4 streamsrc vs rmcp 原始数据对比

**待查**:
- streamsrc 私有 raw 编码的查表映射（需逆向 raw→dBuV 关系）
- Atom 量化算法的具体阈值（需更多样本验证）

### 新建文档
- `STREAMSRC_OFFSET_V1.md` — offset 4-11=会话级FILETIME, offset 19=类型, offset 20-23=类型码
- `DATA_FLOW_END_TO_END.md` — 段2已更新（1441分片、nOffset切分）
- `ANALYSIS_DATA_COMPARISON.md` — streamsrc量化分析

### Task #6 完成: 1441点完整数据获取 ✅

**来源**: `raw_fscan_20260416_101230.log` (rmcp) + nOffset 字段
**关键发现**:

1. **streamsrc 18012 不是 GWJ004 通道** — 90s 测试捕获 644 帧，**全部 65 字节**，无 896/1086 大帧
2. **rmcp 数据可重组 1441 点** — RMCPTP 业务头的 nOffset 字段 (0/512/1024) 正确分片：
   - nOffset=0 → 512 点
   - nOffset=512 → 512 点
   - nOffset=1024 → 417 点
   - **合计 = 1441 点/扫描周期**
3. **成功重组 140 个完整 1441 点扫描**

**重组算法**:
```python
# 按时间顺序，每3帧凑成一个扫描
# nOffset=0(512) + nOffset=512(512) + nOffset=1024(417) = 1441
spectrum = frames[offset_0] + frames[offset_512] + frames[offset_1024]
```

**streamsrc vs rmcp 对比**:

| 属性 | streamsrc | rmcp |
|------|-----------|------|
| 点数/扫描 | 379 (压缩) | 1441 (完整) |
| dBm 范围 | [-75.8, -28.7] | [-108.7, -29.6] |
| 用途 | 实时监测 | 完整存档 |

**结论**: GWJ004 完整数据不在 streamsrc 18012 端口，通过 rmcp_proxy 的 nOffset 字段可正确重组。

---

## 参考文件

- `experimental/TOOLS_AND_LOGS.md` - 工具与日志路径汇总
- `experimental/ATOM_STREAM_SRC_ANALYSIS.md` - **Atom streamsrc 协议分析** (基于 GWJ004/GWJ006/RMCPTP 文档)
- `experimental/logs/streamsrc_raw_20260414_215726.log` - streamsrc 原始帧日志
- `rmcp_proxy/capture/raw_fscan_20260414_215655.log` - rmcp 原始数据
- `experimental/TASKS_20260413_atom_streamsrc_listener.md` - streamsrc 协议分析
