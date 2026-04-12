# 任务：B_FScan 持续数据回调分析

> 创建日期：2026-04-11
> 状态：进行中

---

## 背景

TestTool 发送 B_FScanDF 请求后，会持续收到数据回调，直到发送 B_StopMeas 停止。需要分析：
1. rmcp_proxy 捕获的 DATA 帧结构
2. Atom 如何解析 DATA 帧并转发到 streamsrc

---

## 已确定事实

### 数据流

```
TestTool → SOAP Proxy → Real Atom → rmcp_proxy → Device
                     ↑                              ↓
                     ←←←←←← streamsrc (:18012) ←←←←←
```

### rmcp_proxy 捕获的 DATA 帧（20260411_1854 日志）

**B_FScanDF 请求后**，捕获到持续 DATA 帧：

| 帧类型 | nMsgType | 大小 | 数量 |
|--------|----------|------|------|
| REQUEST | 90 | 754 bytes | 1 |
| RESPONSE | 6 | 31 bytes | 1 |
| DATA | 0 | 31-1240 bytes | 51+ |

**时间间隔**：
- 最小: 109ms
- 最大: 18548ms
- 平均: 731ms

**帧结构示例**：
```
dwLength: 2911
nVersion: 7
nMsgType: 0 (DATA)
nFlags: 1
Hex: 5f0b0000f044edf3e1c9dc010007000104f0100100a1050000...
```

---

## 待解决问题

| # | 问题 | 说明 | 状态 |
|---|------|------|------|
| 1 | Atom 如何解析 DATA 帧 | nMsgType=0 帧的结构是什么？ | ✅ 已解决 |
| 2 | 数据转换公式 | raw int16 → dBm 的转换关系 | ✅ 已验证: /10 |
| 3 | streamsrc 如何转发 | Atom 内部如何将 DATA 帧转到 streamsrc (:18012) | 进行中 |
| 4 | streamsrc 协议格式 | TestTool 收到的是什么格式的数据？ | 进行中 |

## 数据转换公式验证（191028捕获 + 1910测试日志）

### 转换公式
```
dBm = raw_int16_value / 10
```

### 验证数据来源
- **rmcp_proxy捕获**: `capture_20260411_191028.json` (19:10:28)
- **TestTool日志**: `test_tool_log/20260411_1910.txt` (19:10:43)
- **SOAP请求**: B_FScan, startfreq=137MHz, stopfreq=173MHz, step=25kHz

### 帧结构
- RMCP header: 16 bytes (33 hex chars)
- Business header: 14 bytes (28 hex chars) + 4 bytes (8 hex chars) skip = 17 bytes? 
- 数据: 每帧跳过前4个int16值后为实际频谱数据

### 完整扫描周期验证
| 帧 | nOffset | 帧大小 | 数据点数 | 总计 |
|----|---------|--------|----------|------|
| 1 | 0 | 1053 bytes | 512 | |
| 2 | 512 | 1053 bytes | 512 | |
| 3 | 1024 | 863 bytes | 417 | |
| **总计** | - | - | **1441** | ✅ |

### 转换精度
- 误差范围: -0.2 ~ -0.9 dBm
- 原因: TestTool显示取整，内部计算为浮点数

---

## 任务分解

### 任务1：分析 DATA 帧结构

**目标**：解析 nMsgType=0 帧的 hex 数据

**步骤**：
1. 对比不同大小的 DATA 帧 (31, 863, 1053, 1240 bytes)
2. 提取帧头后的业务数据
3. 对比 TestTool 显示的频谱数据格式

**参考**：
- TestTool 显示格式：`PL:1062, DT:12, 频段序号:1, 信道总数:1441`
- rmcp_proxy DATA 帧：31-1240 bytes 不等

### 任务2：分析 streamsrc 数据流

**目标**：弄清楚 Atom 如何将 DATA 帧转发到 streamsrc

**步骤**：
1. 分析 Atom 内部协议转换逻辑
2. 确定 streamsrc 使用的协议格式
3. 验证 DATA 帧与 streamsrc 回调的对应关系

### 任务3：编写测试脚本

**目标**：自动化发送 B_FScan 请求，便于测试

**功能**：
- 发送 B_FScan/B_FScanDF 请求
- 自动记录时间戳
- 便于与 rmcp_proxy 日志对齐

---

## 任务1 结果：DATA 帧结构解析

### 帧结构（2026-04-11 18:54 日志分析）

| 字段 | 值 | 说明 |
|------|-----|------|
| nBdType | **0x0F (15)** | FSCAN业务数据类型 |
| nArrays | **512** | 每帧512个数据点 |
| nOffset | **0/512/1024** | 数据偏移，分3帧传输 |
| Payload | **int16 × 512** | 有符号16位整数 |

### 完整扫描周期

| 帧序号 | nOffset | 数据点数 |
|--------|---------|----------|
| 第1帧 | 0 | 512点 |
| 第2帧 | 512 | 512点 |
| 第3帧 | 1024 | 417点 |
| **总计** | - | **1441点** |

与 TestTool 显示的 `信道总数:1441` 一致 ✓

### 数据转换关系

**已验证公式**: `dBm = raw_int16_value / 10`

验证方法：
- 采集时间：2026-04-11 19:10:43 (191028捕获)
- TestTool日志：`test_tool_log/20260411_1910.txt`
- rmcp_proxy捕获：`capture_20260411_191028.json`

对比结果（所有1441个数据点验证通过）：

| 帧序号 | nOffset | 原始值示例 | 转换后 dBm | TestTool显示 | 误差 |
|--------|---------|-----------|------------|--------------|------|
| 第1帧 | 0 | -525 | -52.5 | -52 | -0.5 |
| 第1帧 | 1 | -755 | -75.5 | -75 | -0.5 |
| 第1帧 | 2 | -772 | -77.2 | -77 | -0.2 |
| 第2帧 | 512 | -569 | -56.9 | -56 | -0.9 |
| 第3帧 | 1024 | -797 | -79.7 | -79 | -0.7 |

误差范围：-0.2 ~ -0.9 dBm（由TestTool取整导致）

**转换公式**:
```python
def raw_to_dbm(raw_value):
    """rmcp_proxy raw int16 -> TestTool显示值 (dBm)"""
    return raw_value / 10.0
```

**注意**: 协议文档(06_RMCPTP_v2.0_无线电协议规范.md)描述 FSCAN 数据为"电平实际值*100"，
但实测结果显示转换公式为 raw / 10 = dBm，与文档不符。

可能原因：
1. 协议文档描述的是旧版本固件/软件
2. 测试设备使用不同的编码格式
3. 文档描述的是发送端编码，接收端做了额外转换

建议：以实测为准，转换公式为 `dBm = raw / 10`

---

## 参考日志

| 文件 | 说明 |
|------|------|
| `rmcp_proxy/capture/capture_20260411_183353.log` | B_FScanDF 请求及后续 DATA 帧 |
| `soap_proxy/logs/soap_proxy_20260411_1835.log` | SOAP 请求日志 |
| `rmcp_proxy/capture/capture_20260411_1854.*` | 最新捕获数据 |

---

**最后更新**: 2026-04-11
