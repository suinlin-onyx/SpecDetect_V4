# Source 与 Sink 模式

## 概述

B_FScan/B_PScan/B_MScan/B_SglFreqMeas 请求中的 `outputchannel` 节点定义数据推送方向。

| 模式   | 含义               | Atom 角色    |
| ------ | ------------------ | ------------ |
| source | 设备指定推送地址（默认） | 服务端，监听 port |
| sink   | 请求方指定推送地址     | 客户端，连接 host:port |

---

## Source 模式（默认）

### 判断条件

请求报文中**不包含** `outputchannel`，或者 `outputchannel.mode` **不为** `sink`。

### 行为

Atom 作为**服务端**：
1. 监听 `streamsrc_port`（默认 18012）
2. 等待 Proxy 连接
3. 数据通过 streamsrc 推送

### 请求示例

```xml
<B_FScan>
  <taskid>xxx</taskid>
  <!-- 无 outputchannel，或 mode != sink -->
</B_FScan>
```

### 响应示例

```xml
<outputchannel mode="source" datachannel="stream">
  <host>127.0.0.1</host>
  <port>18012</port>
  <stc>1234567890</stc>
</outputchannel>
```

---

## Sink 模式

### 判断条件

请求报文中**包含** `outputchannel` 且 `outputchannel.mode` **等于** `sink`。

```xml
<outputchannel mode="sink">
  <host>172.18.98.5</host>
  <port>8332</port>
</outputchannel>
```

### 行为

Atom 作为**客户端**：
1. 解析请求中的 `outputchannel{host, port}`
2. 主动 TCP 连接到 `host:port`
3. 不监听 streamsrc_port

### 连接架构

```
Atom（客户端）──── TCP ────→ outputchannel.host:port
                          （通常是 Proxy 的 port+1）
```

### 请求示例

```xml
<B_FScan>
  <taskid>xxx</taskid>
  <outputchannel mode="sink">
    <host>172.18.98.5</host>
    <port>8332</port>
  </outputchannel>
</B_FScan>
```

### 响应示例

```xml
<outputchannel mode="sink">
  <host>172.18.98.5</host>
  <port>8332</port>
  <stc>1234567890</stc>
</outputchannel>
```

---

## 实现要点

### Source 模式

- 监听 `streamsrc_port`
- 等待 Proxy 连接
- 数据通过 streamsrc 推送

### Sink 模式

- **不监听** streamsrc_port
- 解析请求中 `outputchannel.host` 和 `outputchannel.port`
- 主动 TCP 连接到目标地址
- 数据直接发送到 socket

### 解析逻辑

```python
# 伪代码
outputchannel = request.get('outputchannel', {})
mode = outputchannel.get('mode', 'source')

if mode == 'sink':
    # Sink 模式
    sink_host = outputchannel.get('host')
    sink_port = outputchannel.get('port')
    atom_connect_to_sink(sink_host, sink_port)
else:
    # Source 模式（默认）
    atom_listen_on_streamsrc_port()
```

---

## 文档版本

- 版本：1.0
- 日期：2026-05-20
