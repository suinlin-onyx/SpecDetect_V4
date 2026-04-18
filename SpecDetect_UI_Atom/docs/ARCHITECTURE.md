# SpecDetect UI-Atom 整体架构

**创建日期**: 2026-04-13
**更新日期**: 2026-04-17 v3.1

---

## 1. 系统定位

SpecDetect_Atom 是一个**独立的应用程序**，复现荣新原子服务3.0的核心能力。

**兼容性要求**：老测试工具（荣新3.0测试工具）可直接接入，行为完全一致。

```
┌──────────────────────┐
│ 荣新3.0测试工具       │    当前实现目标
│ (老客户端)            │
└──────────┬───────────┘
           │  SOAP (8282)
           │  streamsrc (18012)  ← 双方配置一致，outputchannel确认
           ▼
┌──────────────────────────────────────────────┐
│              SpecDetect_Atom                  │
│              (独立服务)                        │
└──────────────────────┬───────────────────────┘
                       │  RMCPTP (1449)
                       ▼
            ┌──────────────────────┐
            │    Remote Device      │
            └──────────────────────┘
```

**预留扩展**（设计预留，当前不实现）：
- SpecDetect_Client (新Web UI客户端)
- 多端口Streaming + 动态端口分配
- 显式注册协议

---

## 2. 三层架构

```
┌─ Client Layer ───────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌──────────────────────────────────┐                                       │
│  │  荣新3.0测试工具                  │    (预留) SpecDetect_Client           │
│  │                                   │                                       │
│  │  1. SOAP请求 → Atom:8282         │                                       │
│  │  2. 读SOAP响应中的outputchannel   │                                       │
│  │  3. TCP连接streamsrc端口          │                                       │
│  │     (不发任何注册消息)             │                                       │
│  │  4. 被动接收1086字节帧            │                                       │
│  │  5. B_StopMeas停止               │                                       │
│  └──────────────────────────────────┘                                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                │ SOAP/HTTP                  │ TCP长连接
                ▼                            ▼
┌─ Service Layer (SpecDetect_Atom) ────────────────────────────────────────────┐
│                                                                              │
│  ┌────────────────────────┐        ┌────────────────────────┐               │
│  │ SOAPServer              │        │ StreamSrcServer         │               │
│  │ (原生socket, :8282)     │        │ (原生socket, :18012)    │               │
│  │                         │        │                         │               │
│  │ · 接收HTTP+SOAP请求     │        │ · 接受客户端TCP连接     │               │
│  │ · 解析SOAPAction+XML    │        │ · 隐式匹配pending会话   │               │
│  │ · 返回HTTP+SOAP响应     │        │ · 推送streamsrc帧       │               │
│  │   (含outputchannel)     │        │ · 检测死连接            │               │
│  └───────────┬─────────────┘        └─────────────▲──────────┘               │
│              │                                     │                         │
│              ▼                                     │                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      SessionManager                                  │    │
│  │                                                                      │    │
│  │  pending_sessions: OrderedDict[taskid → StreamSession]              │    │
│  │  active_sessions:  Dict[socket → StreamSession]                     │    │
│  │                                                                      │    │
│  │  · B_FScan到达 → 创建pending(taskid, streamsrc_client=None)         │    │
│  │  · 客户端TCP连接 → FIFO匹配最早的pending → active                   │    │
│  │  · B_StopMeas → 主动关闭session                                     │    │
│  │  · 客户端断开 → 关闭session + 发B_StopMeas到设备                     │    │
│  │  · 无数据30s → 关闭session                                          │    │
│  │  · pending超时30s → 清理                                             │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      FSCANProcessor                                  │    │
│  │                                                                      │    │
│  │  RMCP payload ──decode──→ SpectrumData ──encode──→ streamsrc frame  │    │
│  │  (int16 LE, dBm×10)       (协议无关)         (交替字节[dBm][0xFF])   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      RMCPClient                                      │    │
│  │                                                                      │    │
│  │  · TCP连接设备 (:1449)                                               │    │
│  │  · 发送RMCPTP请求帧 (帧头18B + SOAP XML payload)                     │    │
│  │  · 流式接收响应 (多帧, 每帧18B帧头 + FSCAN payload)                   │    │
│  │  · nCheckSum校验和计算                                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      DevicePreset                                    │    │
│  │  · 加载 config/devinfo/{mfid}_{equid}.xml                          │    │
│  │  · B_QueryDeviceInfo响应数据源                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Logger (统一日志)                                │    │
│  │  · DEBUG / INFO / WARNING / ERROR 级别控制                          │    │
│  │  · stdout + file 双输出                                              │    │
│  │  · [时间][模块][级别] 格式                                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                       │
                       │  RMCPTP / TCP
                       ▼
┌─ Device Layer ───────────────────────────────────────────────────────────────┐
│  Remote Device (100.72.95.36:1449)                                          │
│  · 接收RMCPTP请求 (nMsgType=90)                                             │
│  · 返回RMCPTP响应流 (nMsgType=0/29, FSCAN payload)                          │
│  · FSCAN: 512点/帧, int16 LE, dBm×10                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 通信协议

| 链路 | 协议 | 端口 | 说明 |
|------|------|------|------|
| Client → Atom | SOAP/HTTP POST | 8282 | 原生socket, 手动解析HTTP+XML |
| Atom → Client (响应) | HTTP response | 8282 | 含outputchannel(streaming端口) |
| Client ↔ Atom | TCP长连接 | 18012 | 客户端不发数据, Atom单向推送 |
| Atom → Device | RMCPTP/TCP | 1449 | 双向, 帧头18B + payload |

### 3.1 SOAP请求格式（Client → Atom）

```
POST /B_FScan HTTP/1.1
Host: 127.0.0.1:8282
Content-Type: text/xml; charset=utf-8
SOAPAction: B_FScan
Content-Length: ...

<soapenv:Envelope xmlns:soapenv="..." xmlns:srrc="...">
<soapenv:Body><srrc:requestbody>
  <srrc:appid>123456</srrc:appid>
  <srrc:userid>RX_admin</srrc:userid>
  <srrc:mfid>53090001140012</srrc:mfid>
  <srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
  <srrc:equpara>
    <srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
    <srrc:items>
      <srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
      <srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
      <srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
    </srrc:items></srrc:groupitem></srrc:groupitems>
  </srrc:equpara>
  <srrc:outputchannel>
    <srrc:mode>source</srrc:mode>
    <srrc:datachannel>stream</srrc:datachannel>
  </srrc:outputchannel>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>
```

### 3.2 SOAP响应格式（Atom → Client）

```xml
<soapenv:Envelope xmlns:soapenv="..." xmlns:srrc="...">
<soapenv:Body><srrc:responsebody>
  <srrc:result><srrc:success>true</srrc:success></srrc:result>
  <srrc:taskid>EA-1713340800</srrc:taskid>
  <srrc:outputchannel>
    <srrc:mode>source</srrc:mode>
    <srrc:datachannel>stream</srrc:datachannel>
    <srrc:host>127.0.0.1</srrc:host>
    <srrc:port>18012</srrc:port>
    <srrc:stc>12345678</srrc:stc>
  </srrc:outputchannel>
</srrc:responsebody></soapenv:Body></soapenv:Envelope>
```

`outputchannel.port` 是端口分配机制。当前双方配置一致，响应中确认。预留未来动态分配能力。

### 3.3 Streaming连接

```
客户端:
  1. 读SOAP响应 → 取outputchannel.port (18012)
  2. TCP connect到该端口
  3. 发送 Registration Frame (65 bytes) - 包含 taskid
  4. 接收 Registration ACK (1053 bytes)
  5. 被动接收 streamsrc 帧流 (1086 bytes/帧)

Atom:
  1. accept连接
  2. 接收并解析 Registration Frame
  3. 发送 Registration ACK (1053 bytes RMCP frame)
  4. FIFO匹配最早的pending session (按 taskid 或 FIFO)
  5. 单向推送streamsrc帧
  6. 检测客户端断开 → 清理session
```

#### Registration Frame 格式 (65 bytes)

| Offset | 大小 | 字段 | 说明 |
|--------|------|------|------|
| 00-03 | 4B | Sync | 0xEEEEEEEE (固定) |
| 04-07 | 4B | Seq | 序列号 (uint32 LE) |
| 08-11 | 4B | Field1 | 固定值 |
| 12-15 | 4B | Field2 | 固定值 |
| 16-17 | 2B | Field3 | (uint16 LE) |
| 18-19 | 2B | Field4 | (uint16 LE) |
| 20-23 | 4B | Field5 | 固定值 |
| 24-25 | 2B | TaskID Len | 固定值 36 |
| 26-61 | 36B | TaskID | ASCII 字符串 |

#### Registration ACK 格式 (1053 bytes)

RMCP 帧格式：
- dwLength (4B LE): 1053
- tmStamp (8B LE): FILETIME 时间戳
- nVersion (2B BE): 7
- nMsgType (1B): 0
- nFlags (1B): 1
- nCheckSum (2B LE): 校验和
- Data (1035B): 协议数据

---

## 4. Session 生命周期

### 4.1 状态机

```
                      B_FScan到达
                          │
                          ▼
                    ┌──────────┐
                    │ pending   │──── 30s未匹配 ────→ 清理
                    └─────┬────┘
                          │ 客户端TCP连接 (FIFO匹配)
                          ▼
                    ┌──────────┐
                    │ active   │
                    └─────┬────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
         B_StopMeas    TCP断联      无数据30s
            │             │             │
            ▼             ▼             ▼
                    ┌──────────┐
                    │ closing  │
                    │          │
                    │ · 发StopMeas到设备
                    │ · 关闭RMCP连接
                    │ · 关闭streamsrc连接
                    │ · 移除session
                    └─────┬────┘
                          ▼
                       closed
```

### 4.2 结束场景

| 场景 | 触发 | closing 行为 |
|------|------|-------------|
| B_StopMeas | SOAP请求到达 | 转发StopMeas到设备 → 关闭RMCP → 关闭streamsrc → 清理 |
| TCP断联 | 3s周期检测到客户端断开 | 发StopMeas到设备 → 关闭RMCP → 清理 |
| 无数据30s | active但设备无数据推送 | 发StopMeas到设备 → 关闭RMCP → 关闭streamsrc → 清理 |
| pending超时30s | 无客户端连接 | 直接清理 |

### 4.3 隐式匹配规则

```
pending_sessions: OrderedDict[taskid → StreamSession]

匹配算法 (FIFO):
  1. 客户端TCP连接到达
  2. 取pending_sessions中最早的session
  3. session.streamsrc_client = client_socket
  4. 移到active_sessions
  5. 若pending为空 → 创建孤立session
```

---

## 5. 完整数据流

### 5.1 B_FScan 流程

```
Client                          Atom                              Device
  │                               │                                 │
  │ 1.SOAP B_FScan ──────────────→│                                 │
  │   (HTTP POST :8282)           │ 解析SOAPAction + equpara         │
  │                               │ 生成taskid                      │
  │←── 2.SOAP响应 ────────────────│                                 │
  │   (taskid + outputchannel)    │ 创建pending_session(taskid)     │
  │                               │                                 │
  │   sleep(~1s)                  │ 3.构建RMCPTP REQUEST帧          │
  │                               │   (帧头18B + SOAP XML gb2312)   │
  │                               │──── RMCPTP(nMsgType=90) ───────→│
  │                               │                                 │
  │ 4.TCP connect(:18012) ───────→│                                 │
  │   (不发任何数据)               │ accept → FIFO匹配pending        │
  │                               │ session.state = active          │
  │                               │                                 │
  │                               │←─── RMCPTP响应(nMsgType=0) ────│
  │                               │     (FSCAN payload, 512点)      │
  │                               │                                 │
  │                               │ 5.FSCANProcessor                │
  │                               │   decode_from_rmcp(payload)     │
  │                               │     → SpectrumData (512 dBm)    │
  │                               │   encode_for_streamsrc(data)    │
  │                               │     → 1086B streamsrc帧         │
  │                               │                                 │
  │←── 6.streamsrc帧(1086B) ──────│                                 │
  │        ...持续推送...          │←─── ...持续接收...──────────────│
  │                               │                                 │
  │ 7.SOAP B_StopMeas ──────────→│                                 │
  │←── SOAP响应 ─────────────────│── RMCPTP(StopMeas) ────────────→│
  │                               │ 主动关闭session                  │
```

### 5.2 数据转换链

```
Device                         Atom                              Client

RMCPTP帧                  RMCPClient.receive_stream()
(18B帧头 + payload)              │
                                  ▼
                          FSCANProcessor.decode_from_rmcp()
                          payload: nBdType=0x0F, counters, levels(dBm×10)
                                  │
                                  ▼
                          SpectrumData { levels: [float dBm × 512] }
                          (协议无关中间表示)
                                  │
                                  ▼
                          FSCANProcessor.encode_for_streamsrc()
                                  │
                                  ▼
                          streamsrc帧 (1086B)                ──→  Client
                          [0:3]   0xEEEEEEEE (sync)
                          [4:5]   VER=0x0100
                          [6:9]   STC
                          [10:17] TS (FILETIME)
                          [18]    FrameSeq
                          [19]    0x26 (FSCAN-529)
                          [48:61] Metadata (7×int16)
                          [62:]   交替字节 [dBm][0xFF]×512
```

---

## 6. 模块结构

```
SpecDetect_Atom/
│
├── main.py                              # 服务入口, 组装各模块并启动
│
├── log/
│   └── logger.py                        # 统一日志
│                                          #   全局单例, DEBUG/RELEASE级别控制
│                                          #   stdout + file 双输出
│                                          #   格式: [时间][模块][级别] 消息
│
├── soap/
│   ├── server.py                        # SOAPServer
│   │                                      #   TCP监听(:8282), accept→线程分发
│   │                                      #   _handle_fscan()  业务编排
│   │                                      #   _handle_stopmeas()
│   │                                      #   _handle_query_device()
│   ├── parser.py                        # SOAP解析
│   │                                      #   HTTP header/body拆分
│   │                                      #   SOAPAction提取
│   │                                      #   lxml XML → equpara参数
│   └── builder.py                       # SOAP响应构建
│                                          #   build_response(taskid, port)
│                                          #   build_stopmeas_xml()
│                                          #   build_query_device_xml()
│
├── streaming/
│   └── streamsrc_server.py              # StreamSrcServer + StreamSrcFrame
│                                          #   TCP监听(:18012), accept→隐式匹配
│                                          #   push_frame(bytes)
│                                          #   3s周期死连接检测
│                                          #   StreamSrcFrame dataclass
│
├── session/
│   ├── session.py                       # StreamSession dataclass
│   │                                      #   taskid, state, created_at
│   │                                      #   streamsrc_client, rmcp_client
│   │                                      #   last_data_time
│   └── session_manager.py               # SessionManager
│                                          #   pending/active 管理
│                                          #   create_pending, match_pending(FIFO)
│                                          #   close_session → closing流程
│                                          #   cleanup_stale(30s), cleanup_idle(30s)
│
├── protocol/
│   ├── rmcp_client.py                   # RMCPClient + RMCPHeader dataclass
│   │                                      #   connect/disconnect
│   │                                      #   send, receive_stream → yield payload
│   ├── rmcp_frame.py                    # RMCPTP帧操作
│   │                                      #   build_request_frame(xml, funcid)
│   │                                      #   calculate_checksum
│   │                                      #   parse_header → RMCPHeader
│   └── fscan_processor.py              # FSCANProcessor + SpectrumData dataclass
│                                          #   decode_from_rmcp → SpectrumData
│                                          #   encode_for_streamsrc → 1086B
│                                          #   (预留) decode_from_streamsrc
│
├── preset/
│   └── device_preset.py                 # DevicePreset
│                                          #   load devinfo XML
│                                          #   B_QueryDeviceInfo数据源
│
└── config/
    └── settings.json
```

### 6.1 与 emulated_atom.py 的对应

| 新模块 | emulated_atom.py 来源 | 改进 |
|--------|----------------------|------|
| soap/server.py | `EmulatedAtomService` (start, _handle_*) | 独立类, 职责清晰 |
| soap/parser.py | `parse_soap_request()` | 独立可测试 |
| soap/builder.py | `build_soap_response()` 等 | outputchannel可配 |
| streaming/streamsrc_server.py | `StreamSrcServer` | 提取到独立文件 |
| session/session.py | `StreamSession` | dataclass化 |
| session/session_manager.py | `SessionManager` + `pending_sessions` | 合并管理, 新增idle超时 |
| protocol/rmcp_client.py | `RMCPClient` + `send_to_rmcp_proxy()` | 合并, 流式接收 |
| protocol/rmcp_frame.py | `build_rmcp_frame()` + checksum | 独立模块 |
| protocol/fscan_processor.py | `_parse_single_fscan_frame()` + `build_streamsrc_frame()` | SpectrumData中间层 |
| log/logger.py | 散落的 `log()` + `RMCPFrameLogger` | 统一日志系统 |

---

## 7. 配置

```json
{
  "atom": {
    "host": "0.0.0.0",
    "soap_port": 8282,
    "streamsrc_port": 18012
  },
  "device": {
    "host": "100.72.95.36",
    "port": 1449
  },
  "preset": {
    "devinfo_dir": "../config/devinfo"
  },
  "session": {
    "stale_timeout_sec": 30,
    "idle_timeout_sec": 30,
    "dead_check_interval_sec": 3
  },
  "log": {
    "level": "DEBUG",
    "dir": "logs",
    "console": true,
    "file": true
  }
}
```

---

## 8. 数据格式

### 8.1 RMCP FSCAN Payload (来自设备)

```
byte[0]      nBdType = 0x0F (15 = FSCAN)
byte[1:2]    reserved
byte[3:10]   counters[4] (4 × int16 LE), counters[0] = nArrays
byte[11:]    levels (int16 LE, dBm×10, 每帧512点)
```

### 8.2 streamsrc Frame (1086B, 推送至客户端)

```
Offset 0-3:    Sync      = 0xEEEEEEEE (4B LE)
Offset 4-5:    VER       = 0x0100 (2B BE)
Offset 6-9:    STC       (4B LE)
Offset 10-17:  TS        = FILETIME (8B LE)
Offset 18:     FrameSeq  (1B)
Offset 19:     Indicator = 0x26 (FSCAN-529)
Offset 20-47:  Reserved  = 0x00
Offset 48-61:  Metadata[7] (7 × int16 LE) = [16801, 0, 0, 20480, 18115, 512, 0]
Offset 62-1085: 交替字节 [dBm_byte][0xFF] × 512
                dBm编码: 负值 → 256+dBm, 正值 → dBm
```

### 8.3 RMCPTP帧头 (18B)

```
Offset 0-3:    dwLength  (uint32 LE)
Offset 4-11:   tmStamp   (uint64 LE, FILETIME)
Offset 12-13:  nVersion  (uint16 BE, =7)
Offset 14:     nMsgType  (uint8, 90=REQUEST, 0/29=DATA)
Offset 15:     nFlags    (uint8)
Offset 16-17:  nCheckSum (uint16 LE)

Checksum: fold(tmStamp+dwLength) → ~result & 0xFFFF
```

---

## 9. 预留扩展点

| 扩展点 | 预留方式 | 触发条件 |
|--------|---------|---------|
| 多端口Streaming | config.streaming.ports改为数组 | 多客户端并发 |
| 动态端口分配 | outputchannel.port动态生成 | SpecDetect_Client接入 |
| 显式注册协议 | StreamSrcServer新增register处理 | 精确session匹配 |
| 引用计数 | SessionManager新增ref_count | 多客户端共享Device连接 |
| SpecDetect_Client | SpecDetect_Client/ 目录预留 | Web UI需求 |

---

## 10. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-13 | 初始架构设计 |
| 1.1 | 2026-04-16 | 补充streamsrc、实验成果 |
| 2.0 | 2026-04-17 | 三层架构, 多路设计 |
| 3.0 | 2026-04-17 | 基于现状重设计: 原生socket, 隐式匹配, 单端口, 预留扩展 |
| 3.1 | 2026-04-17 | Session生命周期完善(B_StopMeas主动关闭, 无数据30s超时), 模块拆分定稿, 统一日志 |
