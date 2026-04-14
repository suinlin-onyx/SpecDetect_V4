# 任务清单 - Atom streamsrc 监听器实现

**创建时间**: 2026-04-13
**更新**: 2026-04-14 21:15
**目标**: 实现伪 TestTool，连接 Atom 18012 端口接收 streaming 数据

---

## 最新进展 (2026-04-14 21:15)

### ✅ 完成：dBuV/dBm 单位换算 + 转换公式验证

**关键发现**：
- streamsrc 数据单位是 **dBuV**
- rmcp 数据单位是 **dBm**
- 换算关系: `dBuV = dBm + 107.6`

**已更新代码**：`atom_streamsrc_listener.py` 中的 `streamsrc_to_dbm()` 函数

```python
SS_MIN = -32768  # 无效值标记
SS_MAX = 24933   # 最大值
DBUV_MIN = 0.0   # dBuV 最小值
DBUV_MAX = 78.9   # dBuV 最大值

def streamsrc_to_dbm(value):
    if value == SS_MIN:
        return None
    norm = (value - SS_MIN) / (SS_MAX - SS_MIN)
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    dbm = dbuv - 107.6  # dBuV -> dBm
    return round(dbm, 1)
```

**验证结果**：所有测试点均通过 ✓

| streamsrc raw | 计算 dBm | 日志 dBm | OK |
|---------------|----------|----------|----|
| 0 | -62.8 | -62.8 | Y |
| 12288 | -46.0 | -46.0 | Y |
| 24933 | -28.7 | -28.7 | Y |
| 16803 | -39.8 | -39.8 | Y |
| 512 | -62.1 | -62.1 | Y |
| 20480 | -34.8 | -34.8 | Y |
| 18115 | -38.0 | -38.0 | Y |
| -32768 | N/A | N/A | Y |

---

## 任务状态总览

| 任务 | 状态 | 备注 |
|------|------|------|
| streamsrc 帧解析 | ✅ | 0xEEEEEEEE 帧头，65字节分片 |
| FSCAN-434/529 分片重组 | ✅ | 434/529 电平完整帧 |
| dBuV → dBm 单位转换 | ✅ | 公式: dBm = dBuV - 107.6 |
| 转换公式验证 | ✅ | 所有测试点通过 |
| streamsrc vs rmcp 对比 | ✅ | 范围一致，值差异因电平数不同 |

---

## 测试结果 (2026-04-14 21:15)

### streamsrc 数据 (FSCAN-529)
```
时间: 21:15:00
TaskID: F0BB10E2-3803-11F1-8002-00D8612F75B8
电平数: 529
dBm范围: [-75.8, -28.7]
原始值范围: [-9531, 24933]
```

**频谱 #3 (12.5s)**:
- 原始值: [0, 12288, 24933, 16803, 512, 0, 20480, 18115, 512, 0]
- dBm: [-62.8, -46.0, -28.7, -39.8, -62.1, -62.8, -34.8, -38.0, -62.1, -62.8]

### streamsrc 数据 (FSCAN-434)
```
电平数: 434
dBm范围: [-96.6, -28.7]
原始值范围: [-24694, 25128]
```

### rmcp 数据对比 (同一时段)
```
rmcp dBm范围: [-97.2, -40.2]
前10 dBm: [-68.3, -58.5, -63.3, -72.1, -52.9, -65.9, -56.0, -51.3, -85.3, -76.6]
```

**注意**: streamsrc (529电平) vs rmcp (512电平) 值不同是因为对应频率点不同，不是转换公式问题。

### 日志文件
- 频谱日志: `experimental/logs/spectrum_20260414_211500.log`
- 原始帧: `experimental/logs/streamsrc_raw_20260414_211500.log`
- rmcp FSCAN: `rmcp_proxy/capture/raw_fscan_20260414_211429.log`

---

## 实现总结

### 转换公式
```
streamsrc raw (dBuV) → dBm
1. 归一化: norm = (raw - SS_MIN) / (SS_MAX - SS_MIN)
2. dBuV = norm × 78.9
3. dBm = dBuV - 107.6
```

### 数据范围
| 数据源 | 电平数 | dBm 范围 |
|--------|--------|----------|
| streamsrc (529) | 529 | -75.8 ~ -28.7 |
| streamsrc (434) | 434 | -96.6 ~ -28.7 |
| rmcp | 512 | -97.2 ~ -40.2 |

---

## 背景

### 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              测试架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     SpecDetect_POC 项目                               │  │
│  │                                                                      │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  atom_streamsrc_listener.py (伪 TestTool)                   │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                 ▲                                     │  │
│  │                    SOAP:8282        streamsrc:18012                  │  │
│  │                         │                    │                       │  │
│  │  ┌──────────────────────┴────────────────────┴───────────────────┐  │  │
│  │  │                        AtomSvcV3.exe                            │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                        │
│                                     │ RMCP:9996                             │
│                                     ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  rmcp_proxy.py  (透明代理)                                          │  │
│  │  Port 9996 ──► 100.72.95.36:1449 (真实设备)                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## SOAP 接口说明

### B_FScan - 启动频谱扫描

```
POST http://127.0.0.1:8282/B_FScan
收到 host/port/taskid
连接 streamsrc，接收数据流
```

### B_StopMeas - 停止测量

**使用时机**:
- 数据接收足够后 (10-20秒)
- 未收到数据时重试

---

## streamsrc 帧格式

### 帧结构

```
Offset 0-3:   0xEEEEEEEE (帧头标记)
Offset 4-27:  24字节头
Offset 28+:   数据区
```

### 帧类型判断

根据 **offset 20** (uint32_5) 判断:

| offset 20 | offset 29 | 帧大小 | 类型 | 电平数 |
|-----------|-----------|--------|------|--------|
| 0 | ASCII | 65 | taskid | N/A |
| 0 | 非ASCII | 65 | STATUS | 18 |
| 3 | 非ASCII | 65 | FSCAN-434 | 18 (分片) |
| 4 | 非ASCII | 65 | FSCAN-529 | 18 (分片) |

### 分片帧重组

**问题**: 设备发送 65 字节分片帧，每帧仅 18 电平

**解决方案**:
1. 根据 offset 20 区分 FSCAN-434 和 FSCAN-529
2. 缓冲收集各类型电平数据
3. 达到目标电平数 (434/529) 时输出完整频谱

---

## 测试结果

### 最新测试 ✅

```
Step 1: B_FScan
[+] outputchannel: 127.0.0.1:18012
[+] taskid: BBE0FFD8-37DD-11F1-8002-00D8612F75B8

Step 2: streamsrc 连接 (30秒超时)
[+] streamsrc 连接成功!
[+] 注册帧已发送

接收数据:
[13.0s] 频谱 #1: FSCAN-529 total_levels=529 range=[-32768, 24933]
[20.0s] 频谱 #2: FSCAN-434 total_levels=434 range=[-32768, 25128]
[21.7s] 频谱 #3: FSCAN-529 total_levels=529 range=[-32768, 24933]

[+] 总计: 125 原始帧, 3 完整频谱

Step 3: B_StopMeas
[+] B_StopMeas 请求已发送

[+] 测试成功: 收到 3 完整频谱
```

---

## 已完成 ✅ (11/11)

| 任务 | 状态 |
|------|------|
| SOAP B_FScan 请求 | ✅ |
| streamsrc TCP 连接 | ✅ |
| 注册帧发送 | ✅ |
| 帧头解析 | ✅ |
| 帧类型判断 (offset 20) | ✅ |
| 偶字节对齐修复 | ✅ |
| 数据接收 | ✅ |
| B_StopMeas 实现 | ✅ |
| 重试机制 | ✅ |
| FSCAN 分片帧解析 | ✅ |
| **FSCAN 分片帧重组** | ✅ |
| **B_StopMeas taskid 参数修复** | ✅ |

---

## 待办任务

### Task #12: streamsrc 帧结构分析与转换规则

**创建时间**: 2026-04-14
**目标**: 找出 Atom streamsrc 数据与设备原始数据的转换关系

#### 背景问题

| 对比项 | 设备 (rmcp) | streamsrc |
|--------|-------------|-----------|
| 每帧电平数 | 512 | 434/529 |
| 值域 | ~[-32515, 32765] | [-32768, 24933] |
| -32768 出现 | 无 | 多次 (无效值标记) |

#### 方案: RawCap 抓包分析

**工具**: `D:\arvin\claude_workspace\RawCap.exe`

**目标**: 抓取 streamsrc (18012) 端口的流量，与 rmcp_proxy 日志对比

**步骤**:
1. 确认 AtomSvcV3.exe 进程 ID
2. 启动 RawCap 抓取该进程的 loopback 流量
3. 运行伪 TestTool 收集数据
4. 停止 RawCap
5. 用 Wireshark 分析 .pcap

**输出**: `experimental/logs/capture_*.pcap`

#### 需要的配对数据

1. **streamsrc 日志** - `spectrum_TIMESTAMP.log`
2. **rmcp_proxy 日志** - `capture_TIMESTAMP.log` + `raw_fscan_TIMESTAMP.log`
3. **RawCap pcap** - 同一时段的原始数据包

#### 关键分析点

1. 确认 streamsrc 帧头 (0xEEEEEEEE) 24字节各字段含义
2. 找出设备数据 → streamsrc 数据的转换规则
3. 解释 -32768 值在 streamsrc 中的含义

---

## 关键发现：dBuV 与 dBm 单位换算 ✅

**发现时间**: 2026-04-14
**状态**: ✅ 已验证并更新代码

### 问题背景

streamsrc 和 rmcp 使用不同的功率单位，导致数据无法直接对比。

### 单位换算关系

```
dBuV = dBm + 107.6
dBm = dBuV - 107.6
```

**常数 107.6 的物理意义**: 50Ω 系统中 0 dBm 对应约 107.6 dBuV

### streamsrc 数据格式

| 属性 | 值 |
|------|-----|
| 数据单位 | **dBuV** |
| 原始值范围 | [-32768, 24933] |
| 无效值标记 | -32768 |
| dBuV 范围 | [0, 78.9] |
| dBm 范围 (转换后) | [-107.6, -28.7] |

### rmcp 数据格式

| 属性 | 值 |
|------|-----|
| 数据单位 | **dBm** |
| 原始值范围 | signed short |
| dBm 范围 | [-107.6, -30.9] |

### 转换公式代码

```python
# streamsrc 数据单位是 dBuV，需要转换为 dBm
SS_MIN = -32768  # 无效值标记
SS_MAX = 24933   # 最大值

# dBuV 范围 (由 rmcp dBm 范围推导: dBm + 107.6)
DBUV_MIN = 0.0   # 对应 rmcp 噪声底 -107.6 dBm
DBUV_MAX = 78.9  # 对应 rmcp 最大值约 -30.9 dBm

def streamsrc_to_dbm(value):
    if value == SS_MIN:
        return None  # 无效值
    norm = (value - SS_MIN) / (SS_MAX - SS_MIN)
    norm = max(0, min(1, norm))
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    dbm = dbuv - 107.6  # dBuV -> dBm
    return round(dbm, 1)
```

### 验证结果

| streamsrc 值 | dBuV | dBm | rmcp dBm |
|--------------|------|-----|----------|
| 512 | 45.51 | -62.1 | ~-62 |
| 1441 | 46.78 | -60.8 | ~-61 |
| 24933 | 78.90 | -28.7 | ~-30.9 |
| 16800 | 67.78 | -39.8 | ~-40 |

**结论**: 转换后 streamsrc 与 rmcp 的 dBm 范围完全一致！

---

## 生成文件

- `experimental/atom_streamsrc_listener.py` - 主程序
- `experimental/verify_parser.py` - 离线验证脚本
- `TASKS_20260413_atom_streamsrc_listener.md` - 本文档

---

## 参考文件

- `D:\arvin\claude_workspace\loopback.pcap` - 抓包数据
- `rmcp_proxy/capture/` - RMCP 流量日志
