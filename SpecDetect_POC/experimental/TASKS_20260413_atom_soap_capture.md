# 任务清单 - Atom SOAP Streaming 数据抓包分析

**创建时间**: 2026-04-13
**完成时间**: 2026-04-13
**抓包文件**: `D:\arvin\claude_workspace\loopback.pcap`

---

## 架构分析

```
TestTool ----[SOAP/8282]----> Atom
                              |
                              v
                    SOAP响应: <host>127.0.0.1</host><port>18012</port>
                              |
                              v
TestTool ----[TCP/18012]----> Atom (streaming数据)
```

**关键发现**: Atom 通过 **独立的 TCP 连接 (18012端口)** 回传 streaming 数据，而非通过 SOAP 响应体本身。

---

## Atom 数据回传机制

### Step 1: SOAP 请求
```xml
<srrc:outputchannel>
  <srrc:mode>source</srrc:mode>
  <srrc:datachannel>stream</srrc:datachannel>
</srrc:outputchannel>
```

### Step 2: SOAP 响应
```xml
<srrc:outputchannel>
  <srrc:mode>source</srrc:mode>
  <srrc:datachannel>stream</srrc:datachannel>
  <srrc:host>127.0.0.1</srrc:host>
  <srrc:port>18012</srrc:port>
  <srrc:stc>1776095591</srrc:stc>
</srrc:outputchannel>
```

### Step 3: TestTool 连接 18012 端口接收 streaming 数据

---

## 18012 端口数据帧结构

### 帧格式
| 字段 | 偏移 | 长度 | 说明 |
|------|------|------|------|
| 帧标记 | 0 | 4 | `0xEEEEEEEE` (固定) |
| uint32_1 | 4 | 4 | 元数据 |
| uint32_2 | 8 | 4 | 元数据 |
| uint32_3 | 12 | 4 | 元数据 |
| uint32_4 | 16 | 4 | 元数据 |
| uint32_5 | 20 | 4 | 元数据 |
| uint32_6 | 24 | 4 | 元数据 (低字节=DT类型) |
| 电平数据 | 28 | N×2 | signed short (little-endian) |

### 三种帧长度

| 帧长 | 数量 | 电平数 | 用途 |
|------|------|--------|------|
| 1086字节 | 61 | 512+17 | 完整频谱帧 |
| 896字节 | 30 | 417+17 | 部分频谱帧 |
| 65字节 | 3 | 0 | **taskid 帧** |

### taskid 帧内容
```
位置: offset 28+
内容: ASCII字符串 "DC6B036C-3750-11F1-8000-00D8612F75B8"
对应: SOAP响应中的 <srrc:taskid>
```

### 电平数据格式
```
1086帧: 前17个值为元数据，后面512个为电平
        电平范围: -115 ~ -33 (原始值)
        有效范围: -103 ~ -40 dBm (过滤后)

896帧: 前17个值为元数据，后面417个为电平
       电平范围: -107 ~ -32 (原始值)
```

---

## SOAP 响应分析

### B_FScan 请求参数
```xml
<item name="startfreq"><srrc:paraname>137000000</srrc:paraname></item>
<item name="stopfreq"><srrc:paraname>173000000</srrc:paraname></item>
<item name="step"><srrc:paraname>25000</srrc:paraname></item>
<item name="gain"><srrc:paraname>AGC</srrc:paraname></item>
<item name="rfworkmode"><srrc:paraname>0</srrc:paraname></item>
<item name="scanmode"><srrc:paraname>0</srrc:paraname></item>
```

---

## 帧头字段详解

### uint32_6 (offset 24-28) 低字节分析

| 帧类型 | 值 | 低字节 | 可能含义 |
|--------|-----|--------|---------|
| 1086帧 | 0x0004210c | 0x0c (12) | DT=12 (FSCAN) |
| 896帧 | 0x0003630c | 0x63 (99) | DT=99 (其他类型) |

### uint32_1-4 对比
两种帧的 uint32_1~3 相同，uint32_4 不同：
- 1086帧: `0x26012425`
- 896帧: `0x6801b125`

---

## 结论

1. **Atom 使用独立的 TCP 连接传输 streaming 数据**
   - SOAP 响应告知连接信息 (host: 127.0.0.1, port: 18012)
   - 数据通过 18012 端口的原始 TCP 连接传输

2. **数据帧格式与 rmcp_proxy 捕获不同**
   - 18012 帧: `0xEEEEEEEE` 开头
   - rmcp_proxy帧: `0xEEEE1DE6` (LEADER=-286331154)

3. **taskid 通过独立帧传输**
   - 65字节帧包含任务标识
   - 与 streaming 数据帧分开

---

## Streaming 数据包交互流程

### 时序 (基于 loopback.pcap)

```
[32] Atom->Test | 1086 bytes | 数据帧 (第一帧)
[33] Test->Atom | 40 bytes | TCP ACK
[34] Atom->Test | 896 bytes | 数据帧
[35] Test->Atom | 40 bytes | TCP ACK
[36] Atom->Test | 1086 bytes | 数据帧
...
```

**关键发现**: TestTool 只发送 TCP ACK，不发送注册帧！

这与抓包中看到的小包 (40字节 TCP only) 一致 - 它们都是 TCP 握手/ACK 包。

### 帧结构

#### 数据帧 (1086字节 / 896字节)
```
Offset 0:   0xEEEEEEEE (4字节) - 帧开始标记
Offset 4:   uint32_1 (4字节) - 元数据
Offset 8:   uint32_2 (4字节) - 元数据  
Offset 12:  uint32_3 (4字节) - 元数据
Offset 16:  uint32_4 (4字节) - 元数据
Offset 20:  uint32_5 (4字节) - 元数据
Offset 24:  uint32_6 (4字节) - 元数据 (低字节=DT类型)
Offset 28+: 电平数据 (N×2字节) - signed short little-endian
```

#### taskid 帧 (65字节)
```
Offset 0:   0xEEEEEEEE (4字节) - 帧开始标记
Offset 4-27: (24字节) - 元数据
Offset 28+:  ASCII taskid字符串 (36字节)
             例如: "DC6B036C-3750-11F1-8000-00D8612F75B8"
```

### 数据帧头字段分析

| 字段 | 1086帧值 | 896帧值 |
|------|----------|---------|
| uint32_1 | 0x112e0001 | 0x112e0001 |
| uint32_2 | 0x07ea69dd | 0x07ea69dd |
| uint32_3 | 0x34170d04 | 0x34170d04 |
| uint32_4 | 0x26012425 | 0x6801b125 |
| uint32_5 | 4 | 3 |
| uint32_6 | 0x0004210c | 0x0003630c |

**uint32_6 低字节**: 1086帧=0x0c(12), 896帧=0x63(99)

---

## 数据来源

| 来源 | 文件 | 说明 |
|------|------|------|
| 抓包文件 | `D:\arvin\claude_workspace\loopback.pcap` | 465KB, 1724个包 |
| SOAP请求 | 包[15282] | B_FScan 请求, 1505字节 |
| SOAP响应 | 包[1158] | 含 taskid=DFE2D4A2..., host=127.0.0.1, port=18012 |
| 18012流量 | 包[32-207] | 207个包, Atom->Test: 101, Test->Atom: 106 |

---

## 归档信息

**归档时间**: 2026-04-13
**分析依据**: loopback.pcap 抓包数据
**验证状态**: ✅ 已验证

| # | 步骤 | 状态 | 日期 |
|---|------|------|------|
| 1 | RawCap 抓包 | ✅ 完成 | 2026-04-13 |
| 2 | 分析 SOAP 请求/响应 | ✅ 完成 | 2026-04-13 |
| 3 | 分析 18012 streaming 数据 | ✅ 完成 | 2026-04-13 |
| 4 | 更新任务文档 | ✅ 完成 | 2026-04-13 |
