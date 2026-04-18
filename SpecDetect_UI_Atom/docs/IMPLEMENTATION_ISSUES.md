# 实现问题记录

**创建日期**: 2026-04-17
**关联代码**: `emulated_atom.py`, `test_fscan529.py`

---

## 严重问题 (需优先修复)

### Issue #1: RMCP Checksum 从未正确插入帧

**位置**: `emulated_atom.py:798-802`

```python
# 第798行：frame已完整拼接
frame = header + xml_bytes + b'\x00'

# 第801行：checksum插入位置错误
checksum = _calculate_rmcp_checksum(frame)
frame = frame[:16] + struct.pack('<H', checksum) + frame[18:]
```

**问题**：`frame[:16] + ... + frame[18:]` 把校验和插入了 `frame[16:18]`，但此时 `frame` 长度只有 `18 + len(xml_bytes) + 1`，原始帧中该位置的数据是 XML 尾部字节而非校验和字段。实际发送的帧校验和字段是乱码。

**影响**: 所有发往设备的 RMCP REQUEST 帧校验和均错误，设备应拒绝响应。

**修复方向**: 在拼接 frame 时应将校验和位置预留并正确填入，或直接用 `bytearray` 分段写入。

---

### Issue #2: test_fscan529.py 的 SOAP 请求使用 UTF-8 编码

**位置**: `test_fscan529.py:39` 和 `b_fscan:70`

```python
# 第39行：UTF-8 编码
body_bytes = body_xml.encode('utf-8')

# 第43行：Content-Type 也声明 utf-8
f"Content-Type: text/xml; charset=utf-8\r\n"
```

**问题**: Real Device 只接受 gb2312 编码的 XML。发 UTF-8 会导致设备拒绝或无响应。

**影响**: `test_fscan529.py` 无法与真实设备通信。

**对比**: `emulated_atom.py:775` 正确使用了 `xml_bytes = xml_content.encode('gb2312')`。

**修复方向**: 将 `test_fscan529.py` 的 SOAP 请求改为 gb2312 编码。

---

## 协议细节问题

### Issue #3: FSCAN-434 只解析不生成

**位置**: `emulated_atom.py:319` `build_streamsrc_frame`

```python
# 硬编码 1086 字节帧（FSCAN-529）
frame = bytearray(1086)
frame[19] = 0x26  # FSCAN-529
```

**问题**: `parse_atom_frame` 可以识别 FSCAN-434（0x68, 896B），但 `build_streamsrc_frame` 永远只生成 FSCAN-529。如果真实设备发送 FSCAN-434，代码能解析但无法构造响应帧。

**影响**: 双向通信不对称，仅被动兼容。

---

### Issue #4: emulated_atom.py 回调日志用模拟数据

**位置**: `emulated_atom.py:52`

```python
USE_MOCK_DATA = False  # 设为 False 尝试连接 Real Device
```

**问题**: `USE_MOCK_DATA = False` 时会尝试从 rmcp_proxy capture 目录读数据或直连设备。但 `send_to_rmcp_proxy`（第860行）的 `build_rmcp_frame` 存在 Issue #1 的校验和问题，导致无法真正与设备通信。

---

## 已修复问题

### Issue #5: streamsrc Registration Frame 未处理 (2026-04-17 修复)

**位置**: `emulated_atom.py` `_try_match_pending_session` 函数

**问题描述**:
1. 真实设备要求客户端在 TCP 连接后发送 65 字节 Registration Frame
2. Registration Frame 中包含 taskid（offset 29, 36 bytes ASCII）
3. 设备收到 registration 后会回复 1053 字节的 Registration ACK
4. 原实现不读取 registration frame，直接 FIFO 匹配 pending session

**修复内容**:
1. 接收 65 字节 registration frame
2. 解析 taskid（从 offset 29 读取 36 bytes ASCII）
3. 按 taskid 精确匹配 pending_session，若无则 FIFO
4. 发送 1053 字节 Registration ACK
5. 关联 streamsrc 客户端到 session

**验证**: 通过 pcap `20260416_190539_8282_18012_9996.pcap` 分析确认

---

## Protocol Quirks（已确认的正确行为）

以下是从实测中发现的重要协议细节，当前实现已正确处理：

| # | 发现 | 位置 |
|---|------|------|
| P1 | XML必须gb2312编码 | `emulated_atom.py:775` |
| P2 | nMsgType=0（不是协议文档中的29/95）用于数据帧 | `emulated_atom.py:1315` |
| P3 | nVersion大端存储（little-endian惯例的例外） | `emulated_atom.py:793` |
| P4 | dwLength = 帧头18 + payload长度（含XML+null） | `emulated_atom.py:783` |
| P5 | B_StopMeas仅发给rmcp_proxy，不转发为RMCP到设备 | `emulated_atom.py:629-646` |
| P6 | Checksum算法：fold32→fold16→complement | `emulated_atom.py:807-831` |
| P7 | streamsrc帧：Sync(4B) + Header(44B) + Spectrum(1024B)，共1086B | `test_fscan529.py:122-131` |
| P8 | 频谱数据交替字节模式：[dBm][0xFF][dBm][0xFF]... | `emulated_atom.py:349-361` |

---

## 待验证项

- [ ] Issue #1: 抓包验证设备是否因校验和错误拒绝请求
- [ ] Issue #2: 用正确编码的请求测试设备响应
- [ ] Issue #3: 确认真实设备是否会发送 FSCAN-434
- [ ] Issue #4: rmcp_proxy 直连路径的完整性

---

## 修复优先级

| 优先级 | Issue | 原因 |
|--------|-------|------|
| P0 | #1 Checksum | 所有RMCP请求都无法通过校验 |
| P0 | #2 UTF-8编码 | 无法与真实设备通信 |
| P1 | #3 FSCAN-434 | 双向不对称 |
| P2 | #4 回调日志 | 影响调试能力 |
