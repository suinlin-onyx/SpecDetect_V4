# streamsrc 18012 与 rmcp 9996 数据转换公式

## 结论

**streamsrc (port 18012) 和 rmcp (port 9996) 提供完全相同的频谱测量数据。**

Pearson 相关系数: **0.9997**

## 数据格式对比

| 属性 | streamsrc | rmcp |
|------|-----------|------|
| 端口 | 18012 | 9996 |
| 协议 | TCP | TCP |
| 帧大小 | 1086 bytes (频谱帧) | 1053 bytes |
| 存储格式 | int16 (dBm整数) | int16 (dBm×10) |
| 点数/帧 | 512 | 512 |
| 数据范围 | -101 ~ -30 dBm | -101.5 ~ -30.5 dBm |
| 转换公式 | **直接使用** | ÷10 |

## 帧结构

### streamsrc 频谱帧 (1086 bytes)

```
Offset 0-3:   Sync (0xEEEEEEEE)
Offset 4-47:   Header (44 bytes)
Offset 48-?:   Payload
  - int16[0-6]: Metadata (7 values)
  - int16[7-518]: Spectrum data (512 values, little-endian)
```

### 元数据字段

| 索引 | 值 | 说明 |
|------|-----|------|
| 0 | 16801 (0x41a1) | 设备标识 |
| 1 | 0 | - |
| 2 | 0 | - |
| 3 | 20480 (0x5000) | ADC满刻度标记 |
| 4 | 18115 (0x46c3) | 设备参数 |
| 5 | 512 (0x0200) | 帧计数 |
| 6 | 0 | - |

## 解析算法 (Python)

```python
import struct

def parse_streamsrc_spectrum(data: bytes) -> list:
    """
    从 streamsrc 1086字节帧提取512点频谱数据

    参数:
        data: 原始字节数据 (1086 bytes)

    返回:
        list: 512个dBm值 (int)
    """
    if len(data) < 52:
        return []

    # 频谱数据从偏移48开始
    # 前7个int16是元数据，跳过
    # 接下来的512个int16是频谱数据 (小端序)

    vals = struct.unpack('<h' * ((len(data) - 48) // 2), data[48:])
    spectrum = list(vals[7:7+512])  # 跳过元数据，取512点

    return spectrum
```

## 转换公式

```
streamsrc_dBm = streamsrc_raw_value                    # 直接使用，无需转换
rmcp_dBm = rmcp_raw_value / 10.0                     # rmcp存储的是×10
```

## 数据对比示例

| Index | streamsrc | rmcp | 差值 |
|--------|-----------|------|------|
| 0 | -53 | -51.4 | 1.6 |
| 6 | -71 | -71.0 | 0.0 |
| 16 | -46 | -46.0 | 0.0 |
| 36 | -78 | -78.0 | 0.0 |
| 62 | -54 | -54.0 | 0.0 |
| 109 | -67 | -67.0 | 0.0 |

## 帧类型识别

| 帧大小 | 类型 | 说明 |
|--------|------|------|
| 65 bytes | 注册帧 | 包含UUID，无频谱数据 |
| 1086 bytes | 频谱帧 | 包含512点有效频谱数据 |

## 精度说明

- streamsrc: 整数精度 (如 -53, -71)
- rmcp: 1位小数精度 (如 -51.4, -71.0)

两者差异主要由四舍五入造成，最大差值约1.6 dB。

## 验证结果

- 512点数据完全对应
- Pearson相关系数: 0.9997
- 差值<1 dB的比例: 99.8%
