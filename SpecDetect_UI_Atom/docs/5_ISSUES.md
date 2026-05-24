# SpecDetect_UI_Atom 问题记录

**创建日期**: 2026-04-17
**更新日期**: 2026-04-18

---

## 5.1 严重问题 (已忽略)

以下问题经评估后标记为已忽略，不影响当前实现：

| # | 问题 | 状态 | 原因 |
|---|------|------|------|
| #1 | RMCP Checksum 插入位置错误 | ⚠️ 已忽略 | emulated_atom 使用 rmcp_proxy 转发，checksum 由 rmcp_proxy 计算 |
| #2 | SOAP 请求使用 UTF-8 编码 | ⚠️ 已忽略 | emulated_atom 正确使用 gb2312，test_fscan529.py 是独立测试脚本 |
| #3 | FSCAN-434 只解析不生成 | ⚠️ 已忽略 | Real Atom 只发送 FSCAN-529，不需要生成 FSCAN-434 |
| #4 | 回调日志用模拟数据 | ⚠️ 已忽略 | USE_MOCK_DATA 标志已正确处理 |

---

## 5.2 已修复问题

### Issue #5: streamsrc Registration Frame 未处理 (2026-04-17)

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

**验证**: 通过 pcap 分析确认

---

## 5.3 协议确认行为

以下是从实测中发现的重要协议细节，当前实现已正确处理：

| # | 发现 | 位置/处理 |
|---|------|----------|
| P1 | XML必须gb2312编码 | emulated_atom.py 正确处理 |
| P2 | nMsgType=0（不是29/95）用于数据帧 | emulated_atom.py 正确处理 |
| P3 | nVersion大端存储 | emulated_atom.py 正确处理 |
| P4 | dwLength = 帧头18 + payload | emulated_atom.py 正确处理 |
| P5 | B_StopMeas仅发给rmcp_proxy | emulated_atom.py 正确处理 |
| P6 | Checksum算法：fold32→fold16→complement | rmcp_proxy 处理 |
| P7 | streamsrc帧：1086B | emulated_atom.py 正确处理 |
| P8 | 频谱数据交替字节模式：[dBm][0xFF]... | emulated_atom.py 正确处理 |

---

## 5.4 待验证项

| # | 验证项 | 状态 |
|---|--------|------|
| V1 | rmcp_proxy 直连设备路径完整性 | ✅ 已验证 |
| V2 | 多客户端并发连接 | 待验证 |
| V3 | 长时运行稳定性 | 待验证 |

---

## 5.5 相关文档

| 文档 | 说明 |
|------|------|
| [1_REQUIREMENTS.md](1_REQUIREMENTS.md) | 需求概述 |
| [2_ARCHITECTURE.md](2_ARCHITECTURE.md) | 架构设计 |
| [3_PROTOCOL.md](3_PROTOCOL.md) | 协议细节 |
| [4_IMPLEMENTATION.md](4_IMPLEMENTATION.md) | 实现文档 |
