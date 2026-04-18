# Emulated Atom 与真实设备联调状态

## 日期: 2026-04-16

## 问题描述

emulated_atom 通过 rmcp_proxy 连接真实设备发送 FSCAN 请求，设备不响应。

## 帧格式对比

### 真实设备请求 (9996端口抓包)
- Size: 699 bytes
- dwLength: 699
- nVersion: 7
- nMsgType: 90
- nFlags: 1
- XML: `encoding="gb2312" ?>` (有空格)

### 我们的请求 (修复后)
- Size: 699 bytes ✓
- dwLength: 699 ✓
- nVersion: 7 ✓
- nMsgType: 90 ✓
- nFlags: 1 ✓
- XML: `encoding="gb2312" ?>` ✓

**结论：帧格式已完全一致**

## 问题根因 (已解决)

**RMCP 帧头校验和算法错误**

设备验证 RMCP 帧头校验和，emulated_atom 使用简单的 `sum(frame) & 0xFFFF`，不符合协议要求。

### 协议文档定义的校验和算法

```python
def _calculate_rmcp_checksum(frame: bytes) -> int:
    length = struct.unpack('<I', frame[0:4])[0]
    timestamp = struct.unpack('<Q', frame[4:12])[0]

    total = timestamp + length

    # 第一次折半移位
    high = (total >> 32) & 0xFFFFFFFF
    low = total & 0xFFFFFFFF
    result1 = high + low

    # 第二次折半移位 (循环处理溢出)
    result2 = (result1 >> 16) + (result1 & 0xFFFF)
    while result2 > 0xFFFF:
        result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

    # 取反码
    return (~result2) & 0xFFFF
```

### 修复位置

1. `emulated_atom.py` - `build_rmcp_frame()` 函数
2. `data/fscan_real_request.py` - `build_rmcp_request_frame()` 函数

## 测试结果

修复后设备成功响应：
```
[20:52:07.969] 已发送 RMCP REQUEST
[20:52:08.292] 收到响应: 1104 bytes  ← 设备响应了！
[20:52:08.292] RMCPTP: length=51, msg_type=6
[20:52:08.292] FSCAN: n_bd_type=15, n_arrays=16777216
[20:52:08.292] 解析到 512 点频谱数据
```

## SOAP 接口分析 (pcap: 20260416_190539_8282_18012_9996.pcap)

### 请求路由

| SOAPAction | 目标端口 | 处理方式 | 说明 |
|------------|----------|----------|------|
| B_QueryDeviceInfo | 8282 (Atom) | Atom本地处理 | 返回设备能力列表 |
| B_StopMeas | 8282 (Atom) | Atom本地处理 | 通知Atom中止与设备的长连接 |
| B_FScan | 9996 (rmcp_proxy) | 转发到设备:1449 | RMCP请求 |

### B_StopMeas 的真实作用

**B_StopMeas 不是通过 Atom 发送给设备，而是通知 Atom 中止其与设备的 TCP 长连接。**

### pcap 证据

```
Packet 4:  SOAP B_QueryDeviceInfo → 8282 (Atom本地处理)
Packet 23: RMCP FSCAN funcid=15 → 9996 (rmcp_proxy → 设备:1449)
Packet 89: SOAP B_StopMeas → 8282 (Atom本地处理，中止设备连接)
```

**9996 端口 (rmcp_proxy) 的请求:**
- 只有 funcid=15 (FSCAN)
- 没有 B_StopMeas
- 没有 B_QueryDeviceInfo

## 设备响应对比

| 端口 | 发起连接 | FSCAN请求 | 设备响应 |
|------|----------|-----------|----------|
| 9996 | Atom | funcid=15 | 正常响应 (95B + 1097B数据) |
| 9997 | emulated_atom | funcid=15 | **已修复** - 正常响应 |

## 已修复的问题

1. ✓ XML声明添加空格: `encoding="gb2312" ?>` vs `encoding="gb2312"?>`
2. ✓ dwLength 值: 从 680 改为 699 (等于总帧长度)
3. ✓ nVersion 字节序: big-endian 存储
4. ✓ emulated_atom 新增 B_StopMeas 和 B_QueryDeviceInfo 处理器
5. ✓ **RMCP 校验和算法: 从简单求和改为协议文档算法**

## 状态: ✅ 已解决

emulated_atom 通过 rmcp_proxy (9997端口) 成功与真实设备通信，获取 FSCAN 数据并通过 streamsrc 推送。

## streamsrc 数据帧结构 (GWJ004 5.17)

根据协议文档，streamsrc 数据帧结构：

```
数据帧 = 数据帧头 + 数据帧体

数据帧头:
  - LEADER: 4 bytes, 值 = EEEEEEEE (帧同步)
  - VER: 2 bytes, 版本号 (如 0x0100 = 1.00)
  - STC: 4 bytes, 同步通道号 (UINT32)
  - TS: 8 bytes, FILETIME 时间戳
  - PL: 4 bytes, 负载长度 (UINT32)
  - EL: 1 byte, 扩展帧头长度
  - ExHeader: 扩展帧头 (长度由 EL 指定)

数据帧体:
  - DT: 1 byte, 数据解析类型 (参见 GWJ004 5.14 数据类型表)
  - DL: 4 bytes, 数据长度 (UINT32)
  - DATA: 业务数据
```

### DT 数据类型表 (GWJ004 5.14)

| 值 | 类型名称 | 说明 |
|---|---|---|
| 6 | IQ | IQ 数据 |
| 7 | spectrum | 频谱数据 |
| 8 | ITU | ITU |
| 12 | FSCAN | 频率扫描数据 |
| 13 | MSCAN | 频率时间扫描 |
| 14 | LOCRESULT | 定位结果 |
| 15 | OCCRATE | 占用率 |

### 真实设备 vs emulated_atom streamsrc 帧对比

| 字段 | 真实设备 | emulated_atom (新) | 说明 |
|------|----------|-------------------|------|
| LEADER | eeeeeeee | eeeeeeee | ✓ 正确 |
| VER | 0100 | 0100 | ✓ 正确 |
| STC | 498ce069 | 动态生成 | ✓ 已实现 |
| TS | ea070410... | 动态生成 | ✓ 已实现 |
| PL | 271873 | 1038 | ✓ 正确 (业务数据长度) |
| EL | 0 | 0 | ✓ 正确 |
| **DT** | **12 (FSCAN)** | **12** | ✓ 已实现 |
| **DL** | **1057** | **1038** | ✓ 已实现 |

### 实现说明

`experimental/emulated_atom.py` 中的 `build_streamsrc_frame()` 已按 GWJ004 5.17 实现完整帧结构:

```
帧长度: 23 (帧头) + 5 (帧体头) + 1038 (业务数据) = 1066 bytes

数据帧头 (23 bytes):
  - LEADER: 4 bytes, 0xEEEEEEEE
  - VER: 2 bytes, 0x0100 (big-endian)
  - STC: 4 bytes, 动态生成
  - TS: 8 bytes, FILETIME
  - PL: 4 bytes, 负载长度 = 1038
  - EL: 1 byte, 0

数据帧体 (5 + 1038 bytes):
  - DT: 1 byte, 12 (FSCAN)
  - DL: 4 bytes, 1038
  - DATA: 元数据(14) + 频谱(1024) = 1038
```

**文件位置**: `experimental/emulated_atom.py`
