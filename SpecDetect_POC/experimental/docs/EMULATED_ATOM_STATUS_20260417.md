# Emulated Atom 状态更新

**更新日期**: 2026-04-17

---

## 1. B_QueryDeviceInfo 接口分析

### 完整流程 (从 pcap 分析)

```
Client                         Atom                          Device
  │                              │                              │
  │  B_QueryDeviceInfo ────────→│                              │
  │                              │ 生成 taskid                   │
  │←── taskid + outputchannel ───│                              │
  │                              │                              │
  │  TCP connect streamsrc ─────→│                              │
  │  Registration Frame (65B) ──→│ (包含 taskid)                │
  │                              │ 关联会话                      │
  │                              │                              │
  │←── Registration ACK (1053B)─│ (RMCP frame)                 │
  │                              │                              │
  │←── streamsrc 数据流 ─────────│←── RMCP 数据 ──────────────│
  │     (1086B/896B frames)     │                              │
  │                              │                              │
  │  B_StopMeas ───────────────→│                              │
  │                              │ 关闭会话                      │
```

### Registration Frame 格式 (65 bytes)

| Offset | 大小 | 字段 | 说明 |
|--------|------|------|------|
| 00-03 | 4B | Sync | `0xEEEEEEEE` (固定) |
| 04-07 | 4B | Seq | 序列号 (uint32 LE) |
| 08-11 | 4B | Field1 | 固定值 `0x0000EA07` |
| 12-15 | 4B | Field2 | 固定值 `0x04101306` |
| 16-17 | 2B | Field3 | `0x4901` (uint16 LE) |
| 18-19 | 2B | Field4 | `0x2901` (uint16 LE) |
| 20-23 | 4B | Field5 | 固定值 `0x00000000` |
| 24-25 | 2B | TaskID Len | `0x2400` = 36 (little-endian) |
| **26-61** | **36B** | **TaskID** | **ASCII 字符串** |

### Registration ACK 格式 (1053 bytes)

- RMCP 帧格式 (18B header + 1035B data)
- dwLength: 1053
- nVersion: 7 (big-endian)
- nMsgType: 0
- nFlags: 1

---

## 2. taskid 格式分析

### 真实设备 taskid 格式

```
taskid: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
       ├──────┤ ├────┤ ├────┤ ├────┤ └──────────┘
       会话ID  变化  固定 状态   Atom ID
```

### 示例对比

| 分段 | pcap1 taskid | pcap2 taskid | 说明 |
|------|--------------|--------------|------|
| 第一段 | `40E7D024` | `DA13C5CE` | 每次会话不同 |
| 第二段 | `3984` | `3A5A` | 每次会话不同 |
| 第三段 | `11F1` | `11F1` | 固定 (协议版本?) |
| 第四段 | `8002` | `8000` | 会话状态? |
| **第五段** | **`00D8612F75B8`** | **`00D8612F75B8`** | **固定 = Atom ID** |

### 结论

- **第五段 `00D8612F75B8`** = Atom 自身的固定标识符
- **第一、二段** = 会话相关，每次会话生成
- **第三段 `11F1`** = 固定值，可能是协议版本标识

### 当前 emulated_atom 问题

```python
# 当前实现 (简化版)
taskid = f'EA-{int(time.time())}'
# 输出: EA-1776429788

# 应该改为 UUID 格式
# 输出: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

---

## 3. 已修复问题

### Issue #1: RMCP Checksum 插入位置错误 (已修复)
- **位置**: `emulated_atom.py:798-802`
- **问题**: checksum 插入位置错误导致帧结构错乱
- **修复**: 先预留位置再计算，正确插入

### Issue #2: test_fscan529.py UTF-8 编码 (已修复)
- **位置**: `test_fscan529.py`
- **问题**: 使用 UTF-8 而非 gb2312
- **修复**: 全部改为 gb2312

### Issue #5: streamsrc Registration Frame 处理 (已修复)
- **位置**: `_try_match_pending_session` 函数
- **问题**: 不读取 registration frame，直接 FIFO 匹配
- **修复**: 读取 65B frame，解析 taskid，精确匹配后再 FIFO

---

## 4. 已解决问题

### Issue #6: taskid 格式不一致 (2026-04-17 修复)

**问题**: emulated_atom 生成 `EA-{timestamp}`，测试工具可能校验 UUID 格式

**修复内容**:
- 新增 `generate_taskid()` 函数
- 格式: `XXXXXXXX-XXXX-11F1-XXXX-00D8612F75B8`
- 第一段: 基于时间戳
- 第二段: 随机数
- 第三段: 固定 `11F1`
- 第四段: 状态标志 (默认 `8002`)
- 第五段: Atom ID (固定 `00D8612F75B8`)

**示例**:
```
9B89A477-507E-11F1-8002-00D8612F75B8
```

---

## 5. 文件位置

| 文件 | 说明 |
|------|------|
| `emulated_atom.py` | 主代码 |
| `docs/EMULATED_ATOM_STATUS_20260417.md` | 本文档 |
| `docs/ARCHITECTURE.md` | 架构文档 |
| `docs/IMPLEMENTATION_ISSUES.md` | 问题记录 |

---

## 6. 2026-04-17 补充: B_QueryDeviceInfo 响应格式问题

### 问题发现

通过对比 pcap 发现：
1. **真实设备 B_QueryDeviceInfo 响应没有 outputchannel**
2. emulated_atom 错误地添加了 outputchannel
3. 响应结构与真实设备不一致

### 真实设备响应结构
```xml
<soapenv:Header>
  <srrc:ProviderResponse>
    <srrc:bizResCd>BIZ-000001</srrc:bizResCd>
    <srrc:bizResText>...</srrc:bizResText>
  </srrc:ProviderResponse>
</soapenv:Header>
<soapenv:Body>
  <srrc:responsebody>
    <srrc:result>
      <srrc:appid>123456</srrc:appid>
      <srrc:userid>RX_admin</srrc:userid>
      <srrc:mfid>...</srrc:mfid>
      <srrc:equid>...</srrc:equid>
      <srrc:taskid>...</srrc:taskid>
    </srrc:result>
  </srrc:responsebody>
</soapenv:Body>
```

**关键: 没有 outputchannel！**

### 修复内容

移除 outputchannel 注入，改为只注入 taskid。

---

## 7. 下一步任务

- [x] 研究 taskid 各段生成规则
- [x] 修正 taskid 生成函数
- [x] 移除 B_QueryDeviceInfo 响应中的 outputchannel (错误添加)
- [ ] 测试 B_QueryDeviceInfo + streamsrc 完整流程
- [ ] 验证 Registration ACK 格式正确
