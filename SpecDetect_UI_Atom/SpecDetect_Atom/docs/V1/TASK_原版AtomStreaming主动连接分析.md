# 原版Atom日志关键分析

## 1. B_FScan请求中的outputchannel

```xml
<srrc:outputchannel>
    <srrc:mode>sink</srrc:mode>
    <srrc:datachannel>stream</srrc:datachannel>
    <srrc:host>172.18.98.5</srrc:host>
    <srrc:port>8332</srrc:port>
    <srrc:stc>623041762</srrc:stc>
</srrc:outputchannel>
```

## 2. Atom主动连接到172.18.98.5

```
[2026-05-14 22:33:28.499022(4060)]  strOPCHost=172.18.98.5,strOPCPort=8332
[2026-05-14 22:33:28.533022(3624)] TpOpen[172.18.98.5:8332] succeed
```

## 3. Atom连接到设备

```
[2026-05-14 22:33:28.571022(3624)] TpOpen[172.18.114.196:9999] succeed
```

## 连接架构确认

```
┌─────────────────────────────────────────────────────────────────┐
│                          Atom                                   │
│  ┌──────────────────┐           ┌──────────────────────────┐   │
│  │ TpOpen[172.18.   │           │ TpOpen[172.18.114.196:  │   │
│  │     98.5:8332]   │           │     9999] succeed       │   │
│  │ succeed          │           │ (连接到设备)              │   │
│  └────────┬─────────┘           └────────────┬───────────┘   │
│           │                                    │              │
└───────────┼────────────────────────────────────┼──────────────┘
            │ TCP CLIENT                         │ TCP CLIENT
            │ (Atom主动   )                      │ (Atom主动连接)
            │ 连接外部地址                        │ 设备
            ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│  172.18.98.5:8332   │              │  172.18.114.196    │
│  (外部数据接收地址)   │              │  设备:9999          │
│  Atom推送streaming  │              │  设备发送streaming   │
│  数据到这个地址      │              │  数据给Atom         │
└─────────────────────┘              └─────────────────────┘
```

## 结论

**Atom确实是主动连接到172.18.98.5:8332的！**

| 连接 | 方向 | 角色 |
|------|------|------|
| Atom → 172.18.98.5:8332 | Atom主动连接 | TCP Client |
| Atom → 172.18.114.196:9999 | Atom主动连接 | TCP Client |
| 设备 → Atom | 设备主动连接 | TCP Server (Atom监听) |

## 数据流

1. 设备发送streaming数据到 Atom的9999端口
2. Atom接收数据后，转发到 172.18.98.5:8332

## 重要发现

**Transparent Proxy的监听模式无法管理Atom主动发起的 outbound 连接。**

原版Atom作为TCP客户端：
- 主动连接到outputchannel指定的外部地址
- 主动连接到设备地址
- 同时维护两个 outbound 连接

而当前Transparent Proxy设计为：
- 被动监听接收连接
- 无法拦截Atom主动发起的 outbound 连接

---

# 需要完成的任务

## 实现逻辑

### 模式1：请求不包含完整的outputchannel字段

**判断条件**：请求中不包含完整的 `outputchannel` 节点，或缺少以下任一字段：
- `mode`
- `datachannel`
- `host`
- `port`
- `stc`

**处理方式**：按现有逻辑处理
- 使用 `config.streamsrc_ip` 和 `config.streamsrc_port` 构建响应
- 保持被动监听模式（设备主动连接Atom的streaming端口）

### 模式2：请求包含完整的outputchannel字段

**判断条件**：请求中必须包含以下所有字段，且都有有效值：
```xml
<srrc:outputchannel>
    <srrc:mode>sink</srrc:mode>
    <srrc:datachannel>stream</srrc:datachannel>
    <srrc:host>172.18.98.5</srrc:host>
    <srrc:port>8332</srrc:port>
    <srrc:stc>623041762</srrc:stc>
</srrc:outputchannel>
```

**处理方式**：
1. **解析请求**：从请求中提取 `outputchannel.host` 和 `outputchannel.port`
2. **构建响应**：将请求中的 `host` 和 `port` 原样返回给客户端
3. **主动连接**：Atom作为TCP Client，主动连接到 `outputchannel.host:outputchannel.port`
4. **数据传输**：接收设备数据后，转发到已建立的连接

## 数据传输流程（模式2）

```
1. 客户端                    Atom                       设备
      │                       │                          │
      │── B_FScan请求 ───────>│                          │
      │  outputchannel:        │                          │
      │  host=172.18.98.5    │                          │
      │  port=8332            │                          │
      │                       │                          │
      │<── B_FScan响应 ───────│                          │
      │  (host/port不变)       │                          │
      │                       │                          │
      │                       │<── 设备连接 (RMCP) ──────│
      │                       │     设备发送streaming     │
      │                       │                          │
      │                       │══ TCP Client 连接 ══════>│
      │                       │   172.18.98.5:8332      │
      │                       │   转发streaming数据       │
      │                       │                          │
```

## 实现步骤

### Step 1: 修改SOAP解析器
- 文件：`src/atom/soap/parser.py`
- 添加解析 `outputchannel.mode`、`host`、`port`、`datachannel`、`stc`

### Step 2: 修改service.py
- 文件：`src/atom/service.py`
- 判断请求是否包含完整outputchannel
- 如果包含，使用请求中的host/port构建响应

### Step 3: 实现StreamForwarder
- 文件：`src/atom/stream/forwarder.py`（新建）
- `StreamForwarder.connect(host, port)` - 主动连接到指定地址
- `StreamForwarder.send(data)` - 发送数据
- `StreamForwarder.close()` - 关闭连接

### Step 4: 集成到session
- 文件：`src/atom/service.py`
- 在 `_start_fscan_receive` 中创建到outputchannel地址的连接
- 将接收到的RMCP数据通过该连接转发
