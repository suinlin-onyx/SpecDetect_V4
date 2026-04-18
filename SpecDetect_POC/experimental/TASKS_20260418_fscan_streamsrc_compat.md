# TASKS 2026-04-18: FSCAN StreamSrc 数据兼容性修复

## 🔴 今日最高优先级目标
**调整 streamsrc 回显帧格式，兼容 test tool (即协议文档 GWJ004-5.17)**

### 目标完成情况：90%
- ✅ test tool 可正常连接 emulated_atom
- ✅ B_FScan 请求可收到回调
- ✅ 频谱数据可显示
- ❌ 帧格式与协议文档仍有差异，需优化

### 剩余差异
| 字段 | 协议规定 | 我们的实现 | 状态 |
|------|---------|----------|------|
| PL (Payload Length) | 4 bytes | 缺失 | 待添加 |
| E (扩展头长度) | 1 byte | 缺失 | 待添加 |
| DL (数据长度) | 4 bytes | 缺失 | 待添加 |

## 对照数据来源
| 来源 | 路径 |
|------|------|
| 我们的帧 (test tool 连 emulated_atom) | `experimental/logs/debug/sent_fscan_*.bin` |
| 真实 Atom 帧 (transparent proxy 抓取) | `soap_proxy/logs/stream_18013_233548_132113.bin` |
| 协议规范 | `GWJ004-2015超短波监测管理一体化服务接口规范 数据服务部分.docx` |

## 前置状态
- FSCAN 连接已建立，Registration ACK 正确，帧正在发送
- 问题：test tool 收不到数据，怀疑帧结构或频率不一致

## 任务清单

### 1. 抓包对比真实 Atom 与 emulated_atom 的 streamsrc 数据
- [x] 对比真实 FSCAN 帧 vs 我们发送的帧
  - 帧头结构 (sync, ver, stc, ts, indicator)
  - metadata 字段 (meta[0]=16801 vs 16804 等)
  - spectrum 数据编码方式
  - 帧长 (1086 vs 896)

### 2. 确认帧结构差异
- [x] 对比 streamsrc 帧头24字节 + 私有元数据20字节 + 频谱数据
- [x] metadata[0] 值：真实设备用 16801 (固定)
- [x] metadata[5] 值：512 (FSCAN-529)
- [x] 确认 frame_counter 循环问题 (int16 已确认)
- [x] offset 20 type indicator: FSCAN-529=0x04, FSCAN-434=0x03

### 3. 确认推送频率
- [ ] 真实 Atom FSCAN 推送频率是多少？
- [ ] 我们的是否一致？
- [ ] test tool 是否对频率有要求？

### 4. 修复帧格式 (今日重点)
- [ ] **添加 PL 字段**: 在 TS 后添加 4 bytes Payload Length
- [ ] **添加 E 字段**: 在 PL 后添加 1 byte 扩展头长度 (E=0 表示无扩展)
- [ ] **确认 DT/DL 位置**: 真实帧中 DT/DL 在 offset 48-52 区域
- [ ] **验证 STC 来源**: 真实帧 STC=0，我们的应与 SOAP 响应中一致
- [ ] **帧结构验证通过**: FSCAN-529=1086字节, FSCAN-434=896字节
- [ ] **test tool 验证**: 修复后 test tool 能正常显示数据

### 5. 清理调试代码
- [ ] 移除调试用的帧保存逻辑 (debug_dir)
- [ ] 保留还是删除 USE_MOCK_DATA 开关？

## 参考文件
- 透明代理日志: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\logs\`
- 我们发送的帧: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\experimental\logs\debug\`
- 真实 streamsrc 帧: `stream_18013_233548_132113.bin` (7482 bytes)

## 待讨论问题
1. soap_proxy 是否需要长期保留调试帧功能？
2. 帧格式差异是否需要完全匹配还是只需关键字段匹配？

---

## 协议理解 (5.3 结果返回方式) - 待验证 ⚠️

### 文档原文
返回结果方式可以服务方提供指定，也可以服务消费方指定，在通道信息中给出标注：

#### a) outputchannel mode (数据通道指向方式)
- `--sink` — 消费者方指定
- `--source` — 服务提供方指定

#### b) outputchannel type (数据通道类型)

| 序号 | 返回方式 | 关键字 | 说明 |
|------|---------|--------|------|
| 1 | XML | - | 同步返回，参数包含在响应消息中，以 XML 格式返回 |
| 2 | stream | host, port, **stc** | 异步返回，使用 TCP/IP socket 传递实时数据 |
| 3 | URL | host, port, URI | 异步返回 |
| 4 | FTP | host, port, file, user, password | 异步返回 |
| 5 | database | - | 异步返回 |

### 关键理解

1. **stc (stream 唯一标识)**: 当 type=stream 时，需要在 outputchannel 中提供 **stc** 字段作为该 stream 的唯一标识

2. **STC 与数据帧的关系** (推测，待验证):
   - SOAP 响应中 outputchannel.stc 是 session 标识符
   - streamsrc 数据帧中的 STC 应该与 SOAP 响应中的 stc 一致
   - test tool 可能验证两者匹配性

3. **当前实现**:
   - `_handle_fscan` 生成 `stc = int(time.time())` 放入 SOAP 响应
   - 数据帧使用从 session 获取的相同 stc (修复已应用)
   - **待验证**: stc 的具体格式 (Unix timestamp? 其他?)

### 协议帧结构 (5.17 数据帧格式) - 待验证 ⚠️

根据协议文档 5.17 节，streamsrc 帧结构如下：

```
┌─────────────────────────────────────────────────────────────┐
│                     Frame Header                             │
├──────────┬─────────┬──────────┬───────────┬────────────────┤
│ LEADER   │ VER     │ STC      │ TS        │ PL      │ E     │
│ 4 bytes  │ 2 bytes │ 4 bytes  │ 9 bytes   │ 4 bytes │ 1 byte│
└──────────┴─────────┴──────────┴───────────┴─────────┴────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Payload                                  │
├──────────┬─────────┬──────────────────────────────────────┤
│ DT       │ DL      │ DATA                                  │
│ 1 byte   │ 4 bytes │ variable                              │
└──────────┴─────────┴──────────────────────────────────────┘
```

#### 帧头各字段说明:

| 字段 | 长度 | 类型 | 说明 |
|------|------|------|------|
| **LEADER** | 4 bytes | - | 同步字，值=0xEEEEEEEE |
| **VER** | 2 bytes | UINT8 | 协议版本，格式xx.yy，当前01.00 |
| **STC** | 4 bytes | UINT32 | 同步通道号，标识一路数据流 |
| **TS** | 9 bytes | - | 时间戳 |
| **PL** | 4 bytes | UINT32 | 负载长度 |
| **E** | 1 byte | UINT8 | 扩展头长度指示，255=有扩展 |

#### TS 时间戳格式 (9 bytes):

| 子字段 | 长度 | 范围 | 说明 |
|--------|------|------|------|
| 年 | 2 bytes (UINT16) | [2000,2100] | 年份 |
| 月 | 1 byte (UINT8) | [1,12] | 月份 |
| 日 | 1 byte (UINT8) | [1,31] | 日期 |
| 时 | 1 byte (UINT8) | [0,23] | 小时 |
| 分 | 1 byte (UINT8) | [0,59] | 分钟 |
| 秒 | 1 byte (UINT8) | [0,59] | 秒 |
| 毫秒 | 2 bytes (UINT16) | [0,999] | 毫秒 |

#### Payload 格式:

| 字段 | 长度 | 类型 | 说明 |
|------|------|------|------|
| **DT** | 1 byte | UINT8 | 数据类型 (见5.13类型表) |
| **DL** | 4 bytes | UINT32 | 数据长度 |
| **DATA** | variable | - | 有效数据 |

#### 数据类型 (5.13):

| 值 | 类型 |
|----|------|
| 12 | FSCAN (频谱扫描) |

### 待验证项 ⚠️
- [x] stc 格式: 协议规定为 UINT32 (4 bytes)
- [x] timestamp 格式: 协议规定为 9 bytes (年+月+日+时+分+秒+毫秒)
- [ ] **关键差异**: 真实设备 TS 是 8 bytes，但我们生成的是 8 bytes，**协议规定是 9 bytes**
- [ ] **关键差异**: 协议有 PL (Payload Length) 字段，我们的帧没有
- [ ] offset 21-47 区域的数据结构 (可能是 ExHeader)
- [ ] 帧序列号 (offset 18) 的递增规则?

### 当前帧结构 vs 协议规定

**真实 Atom 帧结构 (从 transparent_20260418_093737.log 捕获)**:
- 帧大小: 7482 bytes = 6 帧 × 1086 bytes + 186 bytes (最后一个不完整?)
- 帧间隔: 约 200ms

| 字段 | 协议规定 | 真实Atom帧 | 我们的实现 | 状态 |
|------|---------|-----------|----------|------|
| LEADER | 4 bytes | eeee eeee ✅ | eeee eeee ✅ | ✅ 匹配 |
| VER | 2 bytes | 0100 ✅ | 0100 ✅ | ✅ 匹配 |
| STC | 4 bytes | 00000000 | 从session获取 | ⚠️ 待验证 |
| TS | 9 bytes | **8 bytes (FILETIME)** | 8 bytes (FILETIME) | ⚠️ 待确认 |
| **PL** | 4 bytes | **存在** | **缺失** | ❌ 关键差异 |
| **E** | 1 byte | **存在** | **缺失** | ❌ 关键差异 |
| DT | 1 byte | offset ~48 | offset 19 | ❌ 位置不同 |
| DL | 4 bytes | 存在 | **缺失** | ❌ 关键差异 |

### 真实 Atom 帧解析 (1086 bytes FSCAN-529)

```
Offset 0-3:   LEADER = 0xEEEEEEEE
Offset 4-5:   VER = 0x0100
Offset 6-9:   STC = 0x00000000 (little-endian)
Offset 10-17: TS = FILETIME (8 bytes, little-endian)
Offset 18-19: Indicator = 0x0026
Offset 20-23: Type indicator = 0x04000000 (FSCAN-529)
Offset 24-61: Private metadata (38 bytes)
Offset 62+:   Spectrum data (交替字节模式)
```

### 关键发现

1. **PL 和 E 字段**: 真实帧确实有 PL (Payload Length) 和 E (扩展头长度) 字段
2. **帧序列**: 7482 / 1086 ≈ 6.89，说明有 6 个完整帧 + 1 个不完整帧
3. **STC 为 0**: 真实设备帧的 STC 为 0，可能表示默认值或未设置

### 相关代码变更
- `build_soap_response`: 添加 priority, executetime, equpara 参数
- `build_streamsrc_frame`: 使用传入的 stc 而非重新生成
- `_handle_fscan`: 将 stc 保存到 session.fscan_params
- `_start_fscan_push`: 从 session 获取 stc 传递给帧构建
