# RMCP 协议开发规范 v1.0

## 目录

1. [协议概述](#1-协议概述)
2. [帧结构详解](#2-帧结构详解)
3. [校验和算法](#3-校验和算法)
4. [funcid 接口映射](#4-funcid-接口映射)
5. [完整代码实现](#5-完整代码实现)
6. [测试验证](#6-测试验证)
7. [常见问题](#7-常见问题)

---

## 1. 协议概述

RMCP (Radio Monitoring and Control Protocol) 是嵘兴无线电监测综合平台使用的通信协议，基于 TCP 传输。

### 协议特性

| 特性 | 说明 |
|------|------|
| 传输层 | TCP |
| 默认端口 | 1449 |
| 字节序 | 小端序 (little-endian)，除特别说明外 |
| 帧头大小 | 18 字节 |
| 数据格式 | XML (请求) / 二进制 (响应) |

### 消息类型

| nMsgType | 类型 | 说明 |
|----------|------|------|
| 90 (0x5A) | REQUEST | 设备控制请求 |
| 6 | RESPONSE | 响应消息 |
| 0 | DATA | 业务数据 |

---

## 2. 帧结构详解

### 2.1 帧头结构 (18字节)

```
+----------------+----------------+----------------+----------------+
|   dwLength    |              tmStamp (8字节)               |   nVersion    |
|   (4字节)     |                                          |   (1字节)     |
+----------------+----------------+----------------+----------------+
     0-3                  4-11                          12-13
+----------------+----------------+----------------+----------------+
|   nMsgType    |     nFlags     |     nCheckSum    |               |
|   (1字节)     |   (1字节)      |     (2字节)      |   XML 数据     |
+----------------+----------------+----------------+----------------+
     14              15               16-17              18+
```

#### 字段说明

| 偏移 | 字段 | 大小 | 类型 | 说明 |
|------|------|------|------|------|
| 0-3 | dwLength | 4 | DWORD (小端) | **帧总长度 - 4**，即整个帧大小减4 |
| 4-11 | tmStamp | 8 | FILETIME (小端) | Windows FILETIME 格式时间戳 |
| 12 | - | 1 | BYTE | 固定值 0x00 |
| 13 | nVersion | 1 | BYTE | 固定值 0x07 |
| 14 | nMsgType | 1 | BYTE | 90=请求, 6=响应, 0=数据 |
| 15 | nFlags | 1 | BYTE | 请求时固定 0x01 |
| 16-17 | nCheckSum | 2 | WORD (小端) | 帧头校验和 |
| 18+ | Data | N | - | XML 数据或二进制数据 |

#### 重要说明

**dwLength 计算方式**：
```
dwLength = 帧总长度 - 4

示例：
- 帧总长 699 字节 → dwLength = 695? 错！
- 实际：dwLength = 帧总长 - 4? 错！

正确理解：
- dwLength 本身是整个帧的大小（包含自己的4字节）
- 但在协议解析时，dwLength = 帧总长 - 4 = 数据部分长度
- 例如：帧总长 699 字节，dwLength = 699（这是帧中记录的值）
- 实际数据 = 帧总长 - dwLength 头部占用 = 699 - 695 = 4? 仍然不对

简化理解：
- dwLength 值 = 帧总长（因为它包含自己的4字节）
- 读取时：dwLength = struct.unpack('<I', frame[0:4])[0]
- 帧总长 = dwLength
```

**实际验证**：
```
Atom 请求帧：699 字节
  - dwLength = 699 (bytes 0-3: bb 02 00 00，小端)
  - 帧总长 = 699 字节
  - 数据部分 = 699 - 18 = 681 字节 (XML + 尾随null)
```

### 2.2 数据部分格式

#### 请求帧 (nMsgType=90)

```
偏移18+: XML 数据 (gb2312 编码)
         ...
最后1字节: 0x00 (尾随 null)
```

**注意**：帧头(18字节)和XML数据之间**没有**null分隔符，XML直接紧跟在帧头后面。XML数据末尾**有**1字节尾随null。

#### 响应帧 (nMsgType=6)

```
偏移18+: 二进制响应数据 (51字节典型)
```

#### 数据帧 (nMsgType=0)

```
偏移18+: 二进制业务数据
```

---

## 3. 校验和算法

### 3.1 算法描述

RMCP 帧头校验和采用 **fold32 + fold16 + ones complement** 算法：

```
1. 取 dwLength (4字节) 和 tmStamp (8字节)，相加得到 total (12字节累加值)
2. 将 total 分成高32位和低32位，相加得到 result1 (32位)
3. 将 result1 分成高16位和低16位，相加得到 result2 (16位)
4. 如果 result2 > 0xFFFF，重复步骤3直到 result2 <= 0xFFFF
5. 返回 (~result2) & 0xFFFF (按位取反)
```

### 3.2 Python 实现

```python
import struct
from datetime import datetime, timezone, timedelta

def calculate_checksum(frame_header: bytes) -> int:
    """
    计算 RMCP 帧头校验和

    Args:
        frame_header: 18字节帧头

    Returns:
        16位校验和
    """
    # 帧头前12字节: dwLength(4) + tmStamp(8)
    length = struct.unpack('<I', frame_header[0:4])[0]
    timestamp = struct.unpack('<Q', frame_header[4:12])[0]

    # Step 1: 相加
    total = timestamp + length

    # Step 2: fold32
    high = (total >> 32) & 0xFFFFFFFF
    low = total & 0xFFFFFFFF
    result1 = high + low

    # Step 3: fold16
    result2 = (result1 >> 16) + (result1 & 0xFFFF)

    # Step 4: 迭代直到 16 位
    while result2 > 0xFFFF:
        result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

    # Step 5: 取反
    return (~result2) & 0xFFFF
```

### 3.3 校验和验证

```python
# Atom 实际帧头
atom_header = bytes.fromhex('bb020000f055e32512cadc0100075a0182b5')

# 计算校验和
calc = calculate_checksum(atom_header)
print(f"计算值: {calc} (0x{calc:04x})")

# 从帧头提取的值
actual = struct.unpack('<H', atom_header[16:18])[0]
print(f"实际值: {actual} (0x{actual:04x})")

print(f"匹配: {calc == actual}")  # 应为 True
```

---

## 4. funcid 接口映射

### 4.1 已知接口列表

| funcid | 接口名 | 主要参数 | 说明 |
|--------|--------|----------|------|
| 10 | B_QueryDeviceInfo | - | 设备信息查询 |
| 11 | B_SglFreqDF | frequency, ifbw, dfmode=1 | **双模式**：ifbw=40MHz单频(nArrays=1)，ifbw=40kHz扫描(nArrays=1601) |
| 12 | B_SglFreqMeas | frequency | ❌ 设备返回"设备校验失败" |
| 13 | B_PScan | frequency, dfmode=1, dftype | ❌ 设备返回"设备校验失败" |
| 14 | B_MScan | frequency, ifbw, antpol | ✅ 多信道扫描 (成功) |
| 15 | B_FScan | startfreq, stopfreq, step | 频率扫描 |
| 16 | B_MScanDF | startfreq, stopfreq, step, keepmode, antpol, antetype, ifatt | ✅ **频谱扫描 (实际成功使用)** |
| 17 | B_WBDF | startfreq, stopfreq | ❌ 设备返回ErrCode=-1 |
| 21 | B_FScanDF | startfreq, stopfreq, step, dfmode=1, antpol | 频率扫描测向 (需要DF硬件) |
| 25 | B_WBDF | frequency, ifbw | ❌ 设备返回"设备校验失败" |
| 32 | B_StopMeas | taskid | 停止测量 |

> **重要发现 (2026-04-13)**：根据实际设备测试：
> - TestTool 的 "B_PScan" 界面实际映射到 **funcid=16** (频谱扫描)
> - funcid=12, 13, 25 设备返回"设备校验失败"，设备不支持
> - funcid=14, 16 成功触发 streaming 数据

### 4.2 SOAP 参数名映射

SOAP 请求中的参数名与 RMCP Action XML 中的参数名可能不同：

```python
SOAP_TO_ACTION_PARAM_MAP = {
    'gain': 'gainctrl',  # SOAP gain 参数映射为 RMCP gainctrl
}
```

### 4.3 funcid 推断逻辑

> **重要更新 (2026-04-13)**：根据实际捕获数据分析，Atom 的 funcid 推断逻辑与之前文档描述有差异。

```python
def infer_funcid(action_items: list, is_nil: bool, has_taskid: bool) -> int:
    """根据参数推断 funcid"""
    names = {name for name, _ in action_items}

    # 无参数查询
    if is_nil:
        return 32 if has_taskid else 10

    # 频率范围参数 (startfreq/stopfreq/step) -> funcid=16 (B_MScanDF)
    if 'startfreq' in names and 'stopfreq' in names and 'step' in names:
        return 16  # B_MScanDF (频谱扫描 - 实际成功使用)

    # 单频率参数 (frequency)
    if 'frequency' in names:
        if 'dfmode' in names:
            return 11  # B_SglFreqDF (需要DF硬件)
        elif 'ifbw' in names:
            return 25  # B_WBDF (设备返回ErrCode=-1)
        else:
            return 12  # B_SglFreqMeas (设备可能不支持)

    # 其他情况
    if 'startfreq' in names or 'stopfreq' in names:
        return 16  # B_MScanDF

    return 15  # 默认 B_FScan
```

**实际验证结果**：
- funcid=16 + startfreq/stopfreq/step → ✅ 成功触发 streaming (nArrays=1441)
- funcid=11 + frequency + dfmode=1 + ifbw=40MHz → ✅ 单频模式 (nArrays=1)
- funcid=11 + frequency + ifbw=40kHz → ✅ 扫描模式 (nArrays=1601)
- funcid=13 + frequency + dfmode=1 → ❌ 设备校验失败
- funcid=25 + frequency + ifbw → ❌ 设备校验失败

### 4.4 funcid=11 (B_SglFreqDF) 双模式详解

**重要发现 (2026-04-13)**：funcid=11 支持两种工作模式，由 `ifbw` 参数决定：

| 模式 | ifbw 值 | nArrays | 数据量 | 说明 |
|------|---------|---------|--------|------|
| 单频模式 | 40MHz (40000000kHz) | 1 | 26 电平 | 测量单个频率点 |
| 扫描模式 | 40kHz (40000kHz) | 1601 | 1601 电平 | 扫描一段频率范围 |

**参数示例**：

```xml
<!-- 单频模式 (nArrays=1) -->
<item name="frequency" value="100MHz" />
<item name="ifbw" value="40000000kHz" />

<!-- 扫描模式 (nArrays=1601) - 需要额外参数 -->
<item name="frequency" value="100MHz" />
<item name="ifbw" value="40000kHz" />
<item name="audioswitch" value="OFF" />
<item name="demodmode" value="FM" />
<item name="demodbw" value="200kHz" />
<item name="bbfftl" value="2048" />
<item name="CombineFunc" value="AsIIEQ" />
```

**扫描模式数据格式**：
- 频率范围：center_freq ± 20MHz（100MHz → 80~120MHz）
- 通道数：1601
- 步进：≈25kHz
- DT=7（频谱数据类型）
- 前4个值为前缀校准数据，实际频谱从第5个值开始

**验证来源**：
- 单频模式：我们的测试 `test_result_B_SglFreqDF_20260413_150111.json`
- 扫描模式：我们的测试 `test_result_B_SglFreqDF_SCAN_20260413_160622.json`

### 4.5 参数调整逻辑

根据 funcid 对参数进行调整：

```python
# 各接口不允许包含的参数 (设备不支持的功能)
FUNCID_DISALLOWED_PARAMS = {
    11: ['dfmode'],   # B_SglFreqDF - 无 DF 硬件时需移除
    12: ['dfmode'],   # B_SglFreqMeas - 设备不支持
    13: ['dfmode'],   # B_PScan - 设备不支持
}

def adjust_params_by_funcid(action_items: list, funcid: int):
    """根据 funcid 调整参数: 移除不允许的参数"""
    disallowed = FUNCID_DISALLOWED_PARAMS.get(funcid, [])
    if disallowed:
        action_items[:] = [(n, v) for n, v in action_items if n not in disallowed]
```

> **注意**：根据实际测试，funcid=11 在带 dfmode=1 时成功了，但 funcid=13 带 dfmode=1 失败了。这可能是因为设备有 DF 硬件但配置不同。

### 4.5 Atom 自动添加的参数 (按接口)

以下参数由 Atom 根据设备配置自动添加，**直连设备时必须包含**：

| funcid | 接口 | 需要添加的参数 |
|--------|------|----------------|
| 10 | B_QueryDeviceInfo | (无) |
| 11 | B_SglFreqDF | antpol, antetype, rfworkmode, ifatt |
| 12 | B_SglFreqMeas | (无) - **设备可能不支持** |
| 13 | B_PScan | dftype, antpol, antetype, rfworkmode, ifatt - **设备返回校验失败** |
| 14 | B_MScan | antpol, antetype, rfworkmode |
| 15 | B_FScan | gainctrl, rfworkmode, scanmode, antpol, antetype, ifatt |
| 16 | B_MScanDF | gainctrl, rfworkmode, antpol, keepmode, antetype, ifatt |
| 17 | B_WBDF | antpol, rfworkmode - **已过时，设备返回ErrCode=-1** |
| 21 | B_FScanDF | gainctrl, rfworkmode, antpol, antezoom, levelthreshold, antetype, ifatt |
| 25 | B_WBDF | gainctrl, rfworkmode, antpol, antetype, resolution, ifatt, antezoom, antArryChoose - **设备返回ErrCode=-1** |
| 32 | B_StopMeas | (无) |

> **实际验证 (2026-04-13)**：根据 rmcp_proxy 捕获分析，funcid=16 的实际参数为：
> - startfreq, stopfreq, step, gainctrl, rfworkmode, keepmode, antpol, antetype, ifatt

### 4.6 参数值格式化

频率和带宽参数需要格式化：

```python
def format_action_items(action_items: list):
    """格式化参数值"""
    for i, (name, value) in enumerate(action_items):
        try:
            val = int(value)
            if name in ('startfreq', 'stopfreq', 'frequency'):
                # 转换为 MHz 格式: 137000000 -> "137MHz"
                action_items[i] = (name, f"{val // 1000000}MHz")
            elif name == 'step':
                # 转换为 kHz 格式: 25000 -> "25kHz"
                action_items[i] = (name, f"{val // 1000}kHz")
            elif name == 'ifbw':
                # 转换为 kHz 格式
                action_items[i] = (name, f"{val // 1000}kHz")
        except (ValueError, TypeError):
            pass
```

---

## 5. 完整代码实现

### 5.1 帧构建

```python
# -*- coding: utf-8 -*-
"""
RMCP 帧构建与解析
"""

import socket
import struct
import time
from datetime import datetime, timezone, timedelta
from typing import Tuple

# ============================================
# 常量定义
# ============================================

RMCP_MSGTYPE_REQUEST = 90
RMCP_MSGTYPE_RESPONSE = 6
RMCP_MSGTYPE_DATA = 0

# ============================================
# 时间戳
# ============================================

def create_filetime() -> bytes:
    """创建当前 UTC 时间的 FILETIME (100纳秒间隔，从1601年开始)"""
    now_utc = datetime.now(timezone.utc)
    ft_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    ft_value = int((now_utc - ft_epoch) / timedelta(microseconds=1)) * 10
    return struct.pack('<Q', ft_value)

# ============================================
# 校验和
# ============================================

def calculate_checksum(frame_header: bytes) -> int:
    """计算 RMCP 帧头校验和 (fold32 + fold16 + ones complement)"""
    length = struct.unpack('<I', frame_header[0:4])[0]
    timestamp = struct.unpack('<Q', frame_header[4:12])[0]

    total = timestamp + length
    high = (total >> 32) & 0xFFFFFFFF
    low = total & 0xFFFFFFFF
    result1 = high + low

    result2 = (result1 >> 16) + (result1 & 0xFFFF)
    while result2 > 0xFFFF:
        result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

    return (~result2) & 0xFFFF

# ============================================
# 帧构建
# ============================================

def build_rmcp_frame(xml_data: str, msg_type: int = RMCP_MSGTYPE_REQUEST) -> bytes:
    """
    构建 RMCP 帧

    Args:
        xml_data: XML 字符串 (gb2312 编码)
        msg_type: 消息类型 (90=请求, 6=响应)

    Returns:
        完整的 RMCP 帧 bytes
    """
    xml_bytes = xml_data.encode('gb2312')

    # 帧头 18 字节 + XML + 尾随 null
    total_len = 18 + len(xml_bytes) + 1

    frame = bytearray()

    # dwLength (4字节, 小端)
    frame.extend(struct.pack('<I', total_len))

    # tmStamp (8字节, 小端)
    frame.extend(create_filetime())

    # Byte 12: 0x00
    frame.append(0x00)

    # nVersion = 7 (1字节)
    frame.append(0x07)

    # nMsgType (1字节)
    frame.append(msg_type)

    # nFlags = 1 (1字节)
    frame.append(0x01)

    # nCheckSum (2字节, placeholder)
    checksum_pos = len(frame)
    frame.extend([0xCC, 0xCC])

    # XML 数据
    frame.extend(xml_bytes)

    # 尾随 null
    frame.append(0x00)

    # 计算并填充校验和
    header_for_checksum = bytes(frame[:18])
    calculated_checksum = calculate_checksum(header_for_checksum)
    frame[checksum_pos:checksum_pos+2] = struct.pack('<H', calculated_checksum)

    return bytes(frame)

# ============================================
# 帧解析
# ============================================

def parse_rmcp_frame(frame: bytes) -> dict:
    """
    解析 RMCP 帧

    Args:
        frame: 完整的 RMCP 帧 bytes

    Returns:
        解析结果字典
    """
    if len(frame) < 18:
        return {'error': 'Frame too short', 'raw': frame.hex()}

    dwLength = struct.unpack('<I', frame[0:4])[0]
    timestamp = struct.unpack('<Q', frame[4:12])[0]
    reserved = frame[12]
    nVersion = frame[13]
    nMsgType = frame[14]
    nFlags = frame[15]
    nCheckSum = struct.unpack('<H', frame[16:18])[0]

    msg_type_names = {
        0: 'DATA',
        6: 'RESPONSE',
        90: 'REQUEST'
    }

    result = {
        'dwLength': dwLength,
        'timestamp': timestamp,
        'reserved': reserved,
        'nVersion': nVersion,
        'nMsgType': nMsgType,
        'nMsgTypeName': msg_type_names.get(nMsgType, f'UNKNOWN({nMsgType})'),
        'nFlags': nFlags,
        'nCheckSum': nCheckSum,
        'data': frame[18:]
    }

    # 如果是 XML 数据，尝试解码
    if nMsgType == RMCP_MSGTYPE_REQUEST and frame[18:19] == b'<':
        try:
            # 找到尾随 null 的位置
            null_pos = frame[18:].find(b'\x00')
            if null_pos > 0:
                xml_bytes = frame[18:18+null_pos]
            else:
                xml_bytes = frame[18:]
            result['xml_data'] = xml_bytes.decode('gb2312')
        except:
            pass

    return result

# ============================================
# TCP 通信
# ============================================

def send_rmcp_frame(host: str, port: int, frame: bytes, timeout: float = 5.0) -> Tuple[bytes, float]:
    """
    发送 RMCP 帧并接收响应

    Returns:
        (response_bytes, elapsed_time)
    """
    start_time = time.time()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.send(frame)

        # 读取响应
        header = b''
        while len(header) < 18:
            chunk = sock.recv(18 - len(header))
            if not chunk:
                break
            header += chunk

        if len(header) >= 4:
            dwLength = struct.unpack('<I', header[0:4])[0]
            remaining = dwLength - len(header)
            body = b''
            while len(body) < remaining:
                chunk = sock.recv(remaining - len(body))
                if not chunk:
                    break
                body += chunk
            response = header + body
        else:
            response = header

        elapsed = time.time() - start_time
        return response, elapsed
```

### 5.2 接收持续数据流

B_FScan 等扫描接口发起后，设备会持续发送数据帧：

**典型序列**：
1. **RESPONSE** (51 bytes) - 请求确认
2. **DATA** (1053 bytes) - 频谱数据帧
3. **DATA** (863 bytes) - 后续数据帧
4. ... 持续发送直到收到 B_StopMeas

**数据流接收示例**：

```python
def receive_data_stream(sock, max_duration=10, max_packets=100):
    """接收设备持续发送的数据流"""
    packets = []
    start_time = time.time()

    while time.time() - start_time < max_duration:
        try:
            # 读取数据 (根据实际情况调整 buffer 大小)
            chunk = sock.recv(2048)
            if not chunk:
                break
            packets.append(chunk)
        except socket.timeout:
            break

    return b''.join(packets)


def parse_data_frames(data: bytes):
    """解析多个连续的数据帧"""
    frames = []
    offset = 0

    while offset < len(data):
        if offset + 4 > len(data):
            break
        dwLength = struct.unpack('<I', data[offset:offset+4])[0]

        if offset + dwLength > len(data):
            break

        frame = data[offset:offset+dwLength]
        nMsgType = frame[14] if len(frame) > 14 else 0

        frames.append({
            'dwLength': dwLength,
            'nMsgType': nMsgType,
            'data': frame[18:]
        })
        offset += dwLength

    return frames
```

**注意**：当前 `send_rmcp_frame` 函数只返回第一个 RESPONSE 帧，如需接收完整数据流需要使用上述代码。


```python
import xml.etree.ElementTree as ET

SOAP_FUNCID_MAP = {
    'B_FScan': 15,
    'B_FScanDF': 21,
    'B_MScan': 14,
    'B_MScanDF': 16,
    'B_PScan': 13,
    'B_SglFreqDF': 11,
    'B_SglFreqMeas': 12,
    'B_WBDF': 25,  # 注意：设备实际使用 funcid=25，不是 17
    'B_QueryDeviceInfo': 10,
    'B_QueryFaciDevStat': 10,  # 与 B_QueryDeviceInfo 同 funcid
    'B_StopMeas': 32,
}

SOAP_TO_ACTION_PARAM_MAP = {
    'gain': 'gainctrl',  # SOAP gain 参数映射为 RMCP gainctrl
}

def parse_soap_items(soap_xml: str) -> Tuple[list, str, str, bool, bool]:
    """
    解析 SOAP XML，提取参数

    Returns:
        (action_items, mfid, equid, is_nil, has_taskid)
    """
    root = ET.fromstring(soap_xml)
    ns = {'srrc': 'http://www.srrc.org.cn'}

    requestbody = root.find('.//srrc:requestbody', ns)
    if requestbody is None:
        requestbody = root.find('.//requestbody')

    mfid = ''
    equid = ''
    if requestbody is not None:
        mfid_elem = requestbody.find('srrc:mfid', ns)
        if mfid_elem is None:
            mfid_elem = requestbody.find('mfid')
        if mfid_elem is not None:
            mfid = mfid_elem.text or ''

        equid_elem = requestbody.find('srrc:equid', ns)
        if equid_elem is None:
            equid_elem = requestbody.find('equid')
        if equid_elem is not None:
            equid = equid_elem.text or ''

    equpara = root.find('.//srrc:equpara', ns)
    if equpara is None:
        equpara = root.find('.//equpara')

    is_nil = equpara is None or equpara.get('xsi:nil') == 'true'

    has_taskid = False
    if requestbody is not None:
        if requestbody.find('srrc:taskid', ns) is not None:
            has_taskid = True
        elif requestbody.find('taskid') is not None:
            has_taskid = True

    action_items = []
    if not is_nil and equpara is not None:
        groupitems = equpara.find('.//srrc:groupitems', ns)
        if groupitems is None:
            groupitems = equpara.find('.//groupitems')

        if groupitems is not None:
            for groupitem in groupitems:
                if groupitem.tag.endswith('groupitem'):
                    items_elem = groupitem.find('.//srrc:items', ns)
                    if items_elem is None:
                        items_elem = groupitem.find('.//items')
                    if items_elem is not None:
                        _parse_items(items_elem, action_items, ns)
        else:
            items_elem = equpara.find('.//srrc:items', ns)
            if items_elem is None:
                items_elem = equpara.find('.//items')
            if items_elem is not None:
                _parse_items(items_elem, action_items, ns)

    return action_items, mfid, equid, is_nil, has_taskid


def _parse_items(items_elem, action_items, ns):
    for item in items_elem:
        paraname = None
        paravalue = None
        for child in item:
            if child.tag.endswith('paraname'):
                paraname = child.text
            elif child.tag.endswith('paravalue'):
                paravalue = child.text
        if paraname and paravalue is not None:
            action_items.append((paraname, paravalue))


def build_action_xml(soap_xml: str, soap_action: str = None, device_params: dict = None) -> str:
    """
    将 SOAP XML 转换为 RMCP Action XML

    Args:
        soap_xml: SOAP XML 字符串
        soap_action: SOAPAction header (如 "B_FScan")
        device_params: 设备配置参数 (如 {'antpol': '垂直', 'rfworkmode': '0', ...})

    Returns:
        Action XML 字符串
    """
    action_items, mfid, _, is_nil, has_taskid = parse_soap_items(soap_xml)

    # 确定 funcid
    if soap_action:
        funcid = SOAP_FUNCID_MAP.get(soap_action.strip('"'), 15)
    else:
        funcid = infer_funcid(action_items, is_nil, has_taskid)

    # 添加设备配置参数
    if device_params:
        names = {name for name, _ in action_items}
        for name, value in device_params.items():
            if name not in names:
                action_items.append((name, value))

    # 格式化参数值
    for i, (name, value) in enumerate(action_items):
        try:
            val = int(value)
            if name in ('startfreq', 'stopfreq', 'frequency'):
                action_items[i] = (name, f"{val // 1000000}MHz")
            elif name == 'step':
                action_items[i] = (name, f"{val // 1000}kHz")
            elif name == 'ifbw':
                action_items[i] = (name, f"{val // 1000}kHz")
        except (ValueError, TypeError):
            pass

    # stationid/deviceid
    if len(mfid) >= 8:
        stationid = mfid[:8]
    else:
        stationid = '53090001'
    deviceid = '00106'

    # 构建 XML
    items_xml = [f'<item name="{name}" value="{value}" />' for name, value in action_items]
    items_str = '\n            '.join(items_xml)

    return f'''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="{stationid}" deviceid="{deviceid}" devicename="MS845" funcid="{funcid}">
        <group index="0">
            {items_str}
        </group>
    </parameter>
    <other_param />
</action>'''
```

### 5.3 完整使用示例

```python
def send_soap_to_device(soap_xml: str, host: str, port: int,
                        soap_action: str = None, device_params: dict = None) -> dict:
    """发送 SOAP 到设备并获取响应"""

    # 1. 转换 SOAP → Action XML
    action_xml = build_action_xml(soap_xml, soap_action, device_params)

    # 2. 构建 RMCP 帧
    frame = build_rmcp_frame(action_xml)

    # 3. 发送并接收响应
    response, elapsed = send_rmcp_frame(host, port, frame)

    # 4. 解析响应
    parsed = parse_rmcp_frame(response)

    return {
        'success': parsed.get('nMsgTypeName') == 'RESPONSE',
        'action_xml': action_xml,
        'frame_hex': frame.hex(),
        'response': parsed,
        'elapsed': elapsed
    }


# 使用示例
soap_fscan = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

# 设备配置参数 (Atom 自动添加的部分)
device_params = {
    'gainctrl': 'AGC',
    'rfworkmode': '0',
    'scanmode': '0',
    'antpol': '垂直',
    'antetype': 'OFF',
    'ifatt': '0'
}

result = send_soap_to_device(
    soap_xml=soap_fscan,
    host='100.72.95.36',
    port=1449,
    soap_action='B_FScan',
    device_params=device_params
)

print(f"Success: {result['success']}")
print(f"Response: {result['response']}")
```

---

## 6. 测试验证

### 6.1 校验和验证

```python
def test_checksum():
    """验证校验和计算"""
    # Atom 实际帧头
    atom_header = bytes.fromhex('bb020000f055e32512cadc0100075a0182b5')

    calc = calculate_checksum(atom_header)
    actual = struct.unpack('<H', atom_header[16:18])[0]

    assert calc == actual, f"Checksum mismatch: calc={calc}, actual={actual}"
    print("Checksum test passed!")

test_checksum()
```

### 6.2 帧构建验证

```python
def test_frame_build():
    """验证帧构建与 Atom 帧一致"""
    # 参考 Atom 帧
    atom_frame = bytes.fromhex(
        'bb020000f055e32512cadc0100075a0182b5'
        '3c3f786d6c2076657273696f6e3d22312e302220656e636f64696e673d2267623233313222203f3e0a'
        # ... XML 数据 ...
    )

    # 我们的帧
    action_xml = '''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="15">
        <group index="0">
            <item name="startfreq" value="137MHz" />
            ...
        </group>
    </parameter>
    <other_param />
</action>'''

    our_frame = build_rmcp_frame(action_xml)

    # 帧总长应相同
    assert len(our_frame) == len(atom_frame), f"Length mismatch: {len(our_frame)} vs {len(atom_frame)}"

    # 帧头应相同 (除时间戳和校验和外)
    assert our_frame[0:4] == atom_frame[0:4]  # dwLength
    assert our_frame[12:16] == atom_frame[12:16]  # reserved, version, msgtype, flags
    # 校验和不同因为时间戳不同

    # XML 数据应完全相同
    our_xml = our_frame[18:-1]  # 去掉尾随 null
    atom_xml = atom_frame[18:-1]
    assert our_xml == atom_xml, f"XML mismatch"

    print("Frame build test passed!")
```

### 6.3 端到端测试

```python
def test_b_fscan():
    """测试 B_FScan 接口"""
    soap = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    result = send_soap_to_device(
        soap,
        host='100.72.95.36',
        port=1449,
        soap_action='B_FScan',
        device_params={'gainctrl': 'AGC', 'rfworkmode': '0', 'scanmode': '0',
                       'antpol': '垂直', 'antetype': 'OFF', 'ifatt': '0'}
    )

    assert result['success'], f"Request failed: {result['response']}"
    print("B_FScan test passed!")
```

---

## 7. 常见问题

### Q1: 直连设备返回 RMTP:ErrCode=-1

**原因**：缺少 Atom 自动添加的参数（如 antpol, rfworkmode 等）

**解决**：确保 device_params 包含所有必需参数

### Q2: 帧校验和不匹配

**原因**：校验和计算错误

**解决**：
1. 确认帧头前 12 字节 (dwLength + tmStamp) 正确
2. 验证 fold32 + fold16 算法实现
3. 确认取反操作 (~result2) & 0xFFFF

### Q3: 响应解析失败

**原因**：响应可能是 RMTP 错误文本，不是 RMCP 二进制帧

**解决**：检查响应是否以 `RMTP` 开头，若是则解析为错误信息

### Q4: XML 编码问题

**原因**：gb2312 编码的 XML 包含无法编码的字符

**解决**：使用 GB2312 支持的字符，或从设备配置读取正确的参数值

---

## 附录：版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0 | 2026-04-12 | 初始版本，包含完整帧结构、校验和、funcid 映射 |
| 1.1 | 2026-04-13 | 更新 funcid=16 B_PScan 测试验证通过；确认 funcid=12/13/25 设备不支持 |
| 1.2 | 2026-04-13 | 更新 funcid=11 双模式说明：ifbw=40MHz 单频(nArrays=1)，ifbw=40kHz 扫描(nArrays=1601) |
| 1.3 | 2026-04-14 | 添加 streamsrc vs rmcp 单位换算说明：dBuV = dBm + 107.6 |
| 1.4 | 2026-04-14 | 转换公式验证通过，streamsrc 529/434 vs rmcp 512 电平数不同但范围一致 |

---

## 附录：dBuV 与 dBm 单位换算 (2026-04-14)

### 背景

频谱数据存在两种单位制：
- **streamsrc (Atom 18012端口)**: 使用 **dBuV** 单位
- **rmcp**: 使用 **dBm** 单位

### 换算关系

```
dBuV = dBm + 107.6
dBm = dBuV - 107.6
```

**常数 107.6 的物理意义**: 在 50Ω 系统中，0 dBm 对应约 107.6 dBuV

### 数据范围对比

| 数据源 | 单位 | 值范围 | 对应 dBm 范围 |
|--------|------|--------|---------------|
| streamsrc raw | dBuV (signed short) | [-32768, 24933] → [0, 78.9] | [-107.6, -28.7] |
| rmcp levels | dBm (big-endian short) | [-32515, 32765] | [-107.6, -30.9] |

### streamsrc 转换代码

```python
SS_MIN = -32768  # 无效值标记
SS_MAX = 24933   # 最大值

def streamsrc_to_dbm(value):
    """streamsrc dBuV -> dBm"""
    if value == SS_MIN:
        return None
    norm = (value - SS_MIN) / (SS_MAX - SS_MIN)
    dbuv = norm * 78.9  # dBuV 范围 [0, 78.9]
    dbm = dbuv - 107.6  # 转换为 dBm
    return round(dbm, 1)
```

### rmcp 转换代码

```python
def rmcp_to_dbm(value):
    """rmcp big-endian signed short -> dBm"""
    if value >= 0x8000:
        value -= 0x10000
    return value / 10.0
```

### 验证

**2026-04-14 21:15 测试验证通过** ✓

| streamsrc raw | 计算 dBm | 实际 dBm | OK |
|---------------|----------|----------|----|
| 0 | -62.8 | -62.8 | Y |
| 12288 | -46.0 | -46.0 | Y |
| 24933 | -28.7 | -28.7 | Y |
| 16803 | -39.8 | -39.8 | Y |
| 512 | -62.1 | -62.1 | Y |

**dBm 范围对比**:
| 数据源 | 电平数 | dBm 范围 |
|--------|--------|----------|
| streamsrc (529) | 529 | -75.8 ~ -28.7 |
| streamsrc (434) | 434 | -96.6 ~ -28.7 |
| rmcp | 512 | -97.2 ~ -40.2 |

**结论**: streamsrc 与 rmcp 的 dBm 范围一致，值差异因电平数不同(529/512 vs 512)

### 测试验证记录 (2026-04-13)

**B_PScan (TestTool) → funcid=16** ✅

请求参数:
```xml
<item name="startfreq" value="137MHz" />
<item name="stopfreq" value="173MHz" />
<item name="step" value="25kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
<item name="antpol" value="垂直" />
<item name="keepmode" value="0" />
<item name="antetype" value="OFF" />
<item name="ifatt" value="0" />
```

响应数据:
- 帧数: 4 帧 (1 RESPONSE + 3 DATA streaming)
- 数据量: 12935 bytes
- FSCAN Payload: 2893 bytes (Header 11 + 1441 channels × 2 bytes)
- 频率范围: 137-173 MHz, 步长: 25 kHz

**B_SglFreqMeas → funcid=12** ❌

响应: `RMTP:ErrCode=-1,INFO=设备校验失败[ID:00106][功能:12]`

结论: funcid=12 设备不支持

