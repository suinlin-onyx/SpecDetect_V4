# SpecDetect_UI_Atom 整体架构

**创建日期**: 2026-04-13
**更新日期**: 2026-04-18

---

## 2.1 系统定位

SpecDetect_UI_Atom 是一个**独立应用程序**，复现荣新原子服务3.0的核心能力。

**兼容性要求**：老测试工具（荣新3.0测试工具）可直接接入，行为完全一致。

```
┌──────────────────────┐
│ 荣新3.0测试工具       │
│ (老客户端)            │
└──────────┬───────────┘
           │  SOAP (8282)
           │  streamsrc (18012)  ← 双方配置一致，outputchannel确认
           ▼
┌──────────────────────────────────────────────┐
│              SpecDetect_Atom                  │
│              (独立服务)                        │
└──────────────────────────────────────────────┘
           │
           │  RMCPTP (1449)
           ▼
┌──────────────────────┐
│    Remote Device      │
└──────────────────────┘
```

---

## 2.2 三层架构

```
┌─ Client Layer ───────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌──────────────────────────────────┐                                       │
│  │  荣新3.0测试工具                  │                                       │
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
│  │ SOAPServer             │        │ StreamSrcServer        │               │
│  │ (原生socket, :8282)    │        │ (原生socket, :18012)  │               │
│  │                        │        │                        │               │
│  │ · 接收HTTP+SOAP请求    │        │ · 接受客户端TCP连接   │               │
│  │ · 解析SOAPAction+XML   │        │ · 隐式匹配pending会话 │               │
│  │ · 返回HTTP+SOAP响应    │        │ · 推送streamsrc帧     │               │
│  │   (含outputchannel)   │        │ · 检测死连接          │               │
│  └───────────┬────────────┘        └─────────────▲──────────┘               │
│              │                                     │                         │
│              ▼                                     │                         │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                      SessionManager                          │            │
│  │                                                              │            │
│  │  pending_sessions: Dict[taskid → StreamSession]             │            │
│  │  active_sessions:  Dict[socket → StreamSession]             │            │
│  │                                                              │            │
│  │  · B_FScan到达 → 创建pending(taskid, streamsrc_client=None)│            │
│  │  · 客户端TCP连接 → FIFO匹配最早的pending → active          │            │
│  │  · B_StopMeas → 主动关闭session                            │            │
│  │  · 客户端断开 → 关闭session + 发B_StopMeas到设备           │            │
│  │  · 无数据30s → 关闭session                                │            │
│  │  · pending超时30s → 清理                                   │            │
│  └────────────────────────────┬────────────────────────────────┘            │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      FSCANProcessor                               │       │
│  │                                                                      │       │
│  │  RMCP payload ──decode──→ SpectrumData ──encode──→ streamsrc帧    │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      RMCPClient                                    │       │
│  │                                                                      │       │
│  │  · TCP连接设备 (:1449)                                              │       │
│  │  · 发送RMCPTP请求帧 (帧头18B + SOAP XML payload)                   │       │
│  │  · 流式接收响应 (多帧, 每帧18B帧头 + FSCAN payload)                 │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└───────────────────────────────────────────────────────────────────────────────┘
                       │
                       │  RMCPTP / TCP
                       ▼
┌─ Device Layer ───────────────────────────────────────────────────────────────┐
│  Remote Device (100.72.95.36:1449)                                          │
│  · 接收RMCPTP请求 (nMsgType=90)                                             │
│  · 返回RMCPTP响应流 (nMsgType=0/29, FSCAN payload)                          │
│  · FSCAN: 512点/帧, int16 LE, dBm×10                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.3 Session 生命周期

### 2.3.1 状态机

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

### 2.3.2 结束场景

| 场景           | 触发             | closing 行为                                |
| ------------ | -------------- | ----------------------------------------- |
| B_StopMeas   | SOAP请求到达       | 转发StopMeas到设备 → 关闭RMCP → 关闭streamsrc → 清理 |
| TCP断联        | 检测到客户端断开       | 发StopMeas到设备 → 关闭RMCP → 清理                |
| 无数据30s       | active但设备无数据推送 | 发StopMeas到设备 → 关闭RMCP → 关闭streamsrc → 清理  |
| pending超时30s | 无客户端连接         | 直接清理                                      |

### 2.3.3 隐式匹配规则

```
pending_sessions: Dict[taskid → StreamSession]

匹配算法 (FIFO):
  1. 客户端TCP连接到达
  2. 取pending_sessions中最早的session
  3. session.streamsrc_client = client_socket
  4. 移到active_sessions
  5. 若pending为空 → 创建孤立session
```

---

## 2.4 完整数据流

### 2.4.1 B_FScan 流程

```
Client                          Atom                              Device
  │                               │                                 │
  │ 1.SOAP B_FScan ──────────────→│                                 │
  │   (HTTP POST :8282)           │ 解析SOAPAction + equpara         │
  │   funcid=12                   │ 生成taskid                       │
  │←── 2.SOAP响应 ────────────────│                                 │
  │   (taskid + outputchannel)    │ 创建pending_session(taskid)      │
  │                               │                                 │
  │   sleep(~1s)                  │ 3.构建RMCPTP REQUEST帧           │
  │                               │   (帧头18B + SOAP XML gb2312)   │
  │                               │──── RMCPTP(nMsgType=90) ───────→│
  │                               │                                 │
  │ 4.TCP connect(:18012) ───────→│                                 │
  │   (不发任何数据)               │ accept → FIFO匹配pending         │
  │                               │ session.state = active           │
  │                               │                                 │
  │                               │←─── RMCPTP响应(nMsgType=0) ────│
  │                               │     (nBdType=0x0F, 512点)       │
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
  │                               │ 主动关闭session                 │
```

> **注**: funcid 与 nBdType 是两个独立标识符，详见 [3_PROTOCOL.md](3_PROTOCOL.md#36-funcid-与-nbdtype-映射关系-实测确认)

---

## 2.5 子项路径映射

### 2.5.1 SpecDetect_Atom

详细架构设计：

→ [../SpecDetect_Atom/docs/](../SpecDetect_Atom/docs/)

### 2.5.2 SpecDetect_Client

当前状态：预留，未实现

---

## 2.6 相关文档

| 文档                                                 | 说明      |
| -------------------------------------------------- | ------- |
| [1_REQUIREMENTS.md](1_REQUIREMENTS.md)             | 需求概述    |
| [3_PROTOCOL.md](3_PROTOCOL.md)                     | 协议细节    |
| [4_IMPLEMENTATION.md](4_IMPLEMENTATION.md)         | 实现文档    |
| [5_ISSUES.md](5_ISSUES.md)                         | 问题记录    |
| [../SpecDetect_Atom/src/](../SpecDetect_Atom/src/) | Atom源代码 |
