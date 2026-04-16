# streamsrc 帧类型与 GWJ004-2015 关联分析

## 摘要

根据 GWJ004-2015 5.2 节定义的 STC (Synchronous Transfer Code) 概念，解释了 streamsrc 65字节注册帧的作用。

## GWJ004-2015 核心概念

### 5.2 服务终结点编码规则

| 概念 | 类型 | 说明 |
|------|------|------|
| STC | UINT32 (4字节) | 同步传输编码，唯一标识一路数据传输通路 |
| TS | 9字节 | 数据帧时间戳 |

> 来源: GWJ004-2015 第5.2节，p1139

### 数据帧结构

```
Offset 0-3:   STC (Synchronous Transfer Code)
Offset 4-12:  TS (Timestamp)
Offset 13+:   Payload
```

## streamsrc 帧类型映射

| streamsrc | GWJ004概念 | 说明 |
|-----------|------------|------|
| 0xEEEEEEEE | STC | 帧同步标识，标识数据传输通道 |
| 65 bytes | 通道建立帧 | 注册/会话建立，通知Atom准备发送数据 |
| 1086 bytes | 数据传输帧 | 512点频谱数据 |

### 注册帧 (65 bytes)

**作用**: 会话/通道建立

```
Offset 0-3:   0xEEEEEEEE (STC同步标识)
Offset 4-27:  24字节头部 (包含类型标识offset 19=0x26/0x68)
Offset 28-37: vals[0:5] = [256, 1441, 0, 0, -32768]  ← 元数据
Offset 38-63: vals[5:17] = 13个int16  ← 频谱样本
```

**验证结果** (429帧):
- SYNC: 0xEEEEEEEE (100%)
- 元数据: [256, 1441, 0, 0, -32768] (100%)
- 无一帧例外

### 频谱帧 (1086 bytes)

**作用**: 传输512点频谱数据

```
Offset 0-3:   0xEEEEEEEE (STC同步标识)
Offset 4-47:  44字节头部
Offset 48+:   Payload
  - int16[0-6]: Metadata [16801, 0, 0, 20480, 18115, 512, 0]
  - int16[7-518]: 512点频谱数据 (小端序int16)
```

## 协议流程

```
Client                          Atom
  |                               |
  |-------- 注册帧 (65B) -------->|
  |      (包含STC通道标识)         |
  |                               |
  |<------ 频谱帧 (1086B) --------|
  |      (512点数据)              |
  |                               |
```

**关键发现**: 必须先发送注册帧，Atom才会发送频谱帧。不发送注册帧则连接成功但无数据。

## 解析代码

```python
from streamsrc_parser import StreamsrcParser

parser = StreamsrcParser()

# 判断帧类型
if parser.is_registration_frame(data):
    reg = parser.parse_registration_frame(data)
    print(f"SYNC: 0x{reg['sync']:08X}")
    print(f"元数据: {reg['metadata']}")
elif parser.is_spectrum_frame(data):
    spectrum = parser.parse_spectrum(data)
    print(f"512点, 范围 {min(spectrum)}~{max(spectrum)} dBm")
```

## 验证日志

- `experimental/logs/streamsrc_raw_20260415_232120.log` - 429帧纯注册帧
- `experimental/verify_registration_parser.py` - 验证脚本

## 结论

1. **GWJ004 STC** 解释了 streamsrc 0xEEEEEEEE 同步头的意义
2. **65字节注册帧** = 通道建立，Atom收到后才发送数据
3. **1086字节频谱帧** = 512点有效数据
4. 两者结合构成完整的数据传输协议
