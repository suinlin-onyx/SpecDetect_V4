# SglFreqMeas streamsrc 帧对齐任务 [已完成]

**创建日期**: 2026-04-25
**完成日期**: 2026-04-25
**方案**: 与真实设备二进制抓包逐字节对齐，修正帧结构

---

## 问题描述

测试工具连接 Atom 后显示 "没有收到"，无法解析 SglFreq streamsrc 帧。

## 根因分析

通过对比真实设备二进制抓包 (`stream_B_SglFreqMeas_18013_150706_378968.bin`) 发现以下不匹配：

### 1. build_pscan_spectrum_frame (3256B 频谱帧)

| 字段 | 原值 | 设备值 | 修复后 |
|------|------|--------|--------|
| fscan_type (offset 20-23) | 0x04000000 | 0x0C000000 | 0x0C000000 |
| metadata 长度 | 21字节 (offset 29-49) | 25字节 (offset 29-53) | 25字节 |
| 频谱起始偏移 | 50 | 54 | 54 |
| DL | 155 | 3227 | 3227 |
| n_points 写入位置 | offset 26-29 (BE) | offset 30-33 + 50-53 (LE) | 30-33 + 50-53 |
| 频谱编码 | int16 LE | int16 LE | int16 LE |

### 2. build_pscan_itu_frame (36B ITU帧)

| 字段 | 原值 | 设备值 | 修复后 |
|------|------|--------|--------|
| ITU值编码 | float64 BE (offset 27-35) | float32 LE (offset 32-35) | float32 LE |
| item_count 位置 | offset 26 | offset 30 | offset 30 |
| 固定值位置 | 无 | offset 31 = 0x01 | offset 31 = 0x01 |

### 3. build_uuid_frame (65B UUID帧)

- 新增函数，客户端连接后首帧发送
- indicator = 0x0129（与设备一致）
- UUID 从 offset 29 开始，36字节 ASCII

## 验证结果

```
=== Frame Comparison (设备 vs Atom) ===
Frame size: 3256B = 3256B
fscan_type: 0x0C = 0x0C
DT: 7 = 7
DL: 3227 = 3227
Metadata[29:54]: 完全一致
Spectrum points: 1601/1601 匹配
```

## 修改文件

| 文件 | 改动 |
|------|------|
| `src/atom/stream/frame.py` | 修复 spectrum/itu/uuid 帧构建 |
| `src/atom/stream/__init__.py` | 导出 build_uuid_frame |
| `src/atom/stream/server.py` | sglfreq 模式推送逻辑、UUID帧发送 |
| `src/atom/service.py` | sglfreq 事件驱动队列、三帧循环推送 |
| `src/atom/rmcp/frame.py` | IFANALYSIS 解析优化 |
| `src/atom/rmcp/client.py` | 小修 |
| `src/preset/templates/B_SglFreqMeas.xml` | 模板更新 |

## 帧格式参考 (设备实测)

### 频谱帧 (3256B)
```
offset 0-3:   sync (0xEEEEEEEE, BE)
offset 4-5:   VER = 1 (LE)
offset 6-9:   STC (LE)
offset 10-17: timestamp (8B)
offset 18-19: indicator = 0x01A0 (BE)
offset 20-23: fscan_type = 0x0C000000
offset 24:    DT = 7
offset 25-28: DL = 3227 (LE)
offset 29-53: metadata (25B)
offset 54+:   spectrum (1601 × int16 LE = 3202B)
```

### 电平帧 (40B)
```
offset 4-5:   VER = 16 (LE)
offset 18-19: indicator = 0x0110 (BE)
offset 24:    DT = 101
offset 38:    level (uint8)
```

### ITU帧 (36B)
```
offset 4-5:   VER = 16 (LE)
offset 18-19: indicator = 0x010C (BE)
offset 24:    DT = 8
offset 32-35: ITU值 (float32 LE)
```

## Commit

```
fix: SglFreq streamsrc帧与真实设备完全对齐
```
