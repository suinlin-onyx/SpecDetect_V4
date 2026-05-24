# Source 与 Sink 模式 Stream 连接机制

## 概述

outputchannel 的 mode 字段定义了两种数据推送模式：

| 模式     | 含义          | 设备/Atom 角色             |
| ------ | ----------- | ---------------------- |
| source | 服务提供方指定推送地址 | Atom 作为服务端，等待 Proxy 连接 |
| sink   | 服务消费方指定推送地址 | Atom 作为客户端，主动连接 Proxy  |

---

# Source 模式

## 角色定义

| 角色      | 端口    | 角色类型       |
| ------- | ----- | ---------- |
| Atom/设备 | 18012 | 服务端，监听连接   |
| Proxy   | 18013 | 劫持端口，代理服务器 |
| 请求侧（UI） | -     | 客户端，发起连接   |

## 连接架构

```
请求侧（客户端） ────────────── TCP 连接(1) ──────────────→ Proxy（服务器:18013）
                                                                  │
                                                                  │ TCP 连接(2)
                                                                  ↓
                                                        Atom/设备（服务器:18012）
```

## 流程说明

1. 请求侧发起 B_FScan 请求（无 outputchannel，默认 source 模式）
2. Proxy 转发请求到 Atom/设备
3. 设备处理请求，作为服务端监听 port=18012
4. 设备回调 outputchannel{host=127.0.0.1, port=18012}
5. Proxy 解析 port=18012，启动代理监听 18013，修改响应 port=18013
6. Proxy 转发修改后的响应给请求侧
7. 请求侧作为客户端连接 Proxy 的 18013
8. Proxy 作为客户端连接到 Atom/设备 的 18012
9. Proxy 双向透传

## 核心代码

```python
def start_stream_proxy(listen_host, listen_port, target_port, interface_name):
    """启动 streamsrc 透明代理"""
    # 1. Proxy 绑定并监听 listen_port (18013)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((listen_host, listen_port))  # 18013
    server_socket.listen(5)

    while True:
        # 2. 等待请求侧连接 Proxy 的 18013
        client_socket, client_addr = server_socket.accept()

        # 3. Proxy 作为客户端连接到 Atom 的 target_port (18012)
        target_socket = socket.create_connection(('127.0.0.1', target_port))  # 18012

        # 4. 双向透传数据
        def forward(src, dst, direction):
            while True:
                data = src.recv(8192)
                if not data:
                    break
                dst.sendall(data)

        t1 = threading.Thread(target=forward, args=(client_socket, target_socket, "C->S"))
        t2 = threading.Thread(target=forward, args=(target_socket, client_socket, "S->C"))
        t1.start()
        t2.start()
```

## 日志示例

```
[STREAM/B_MScan] Proxy registered: 18013 -> 18012
[STREAM/B_MScan] Proxy started: 127.0.0.1:18013 -> 127.0.0.1:18012
[STREAM/B_MScan] >>> ('127.0.0.1', 47953) -> 18013
```

---

# Sink 模式

## 角色定义

| 角色    | 端口/地址                       | 角色类型           |
| ----- | --------------------------- | -------------- |
| Atom  | -                           | 客户端，主动连接 Proxy |
| Proxy | proxy_ip:port+1             | 服务器，劫持端口       |
| 外部目标  | host:port（原始 outputchannel） | 目标地址           |

## 连接架构

```
Atom（客户端） ────────────── TCP 连接(1) ──────────────→ Proxy（服务器:port+1）
                                                                  │
                                                                  │ TCP 连接(2)
                                                                  ↓
                                                        原始 outputchannel 的 host:port
                                                        （如 172.18.98.5:8332）
```

## 流程说明（正确顺序）

1. Proxy收到B_FScan请求（outputchannel{mode=sink, host=172.18.98.5, port=8332}）
2. Proxy**立即**作为客户端连接 172.18.98.5:8332（外部目标）
3. Proxy开始监听 port+1 (8333)
4. Proxy修改请求中outputchannel为{host=proxy_ip, port=8333}，透明转发给Atom
5. Atom收到请求，**立即**作为客户端连接 proxy_ip:8333
6. Proxy双向透传：Atom ↔ 172.18.98.5:8332

### 关键点
- **先连接外部目标，再监听本地端口**
- Atom和Proxy通常在同一台机器（用于测试抓包）
- Proxy在收到Atom连接前已建立到外部的连接，确保透传不断开

## 错误流程（旧版）

```
1. Proxy监听8333
2. 等待Atom连接
3. Atom连接后，再连接外部目标
4. 问题：Atom发送数据时，外部连接还未建立，数据丢失
```

## 核心代码

```python
def start_sink_proxy(listen_host, listen_port, target_host, target_port, interface_name):
    """启动 sink 模式透明代理"""
    # 1. Proxy 作为客户端先连接外部目标
    try:
        target_socket = socket.create_connection((target_host, target_port), timeout=10)
        logging.info(f"[SINK/{interface_name}] Connected to external target: {target_host}:{target_port}")
    except Exception as e:
        logging.error(f"[SINK/{interface_name}] Failed to connect to {target_host}:{target_port}: {e}")
        return

    # 2. Proxy 绑定并监听 listen_port (port+1)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((listen_host, listen_port))  # proxy_ip:8333
    server_socket.listen(5)

    # 3. 等待 Atom 连接 Proxy 的 listen_port
    try:
        atom_socket, atom_addr = server_socket.accept()
        logging.info(f"[SINK/{interface_name}] Atom connected: {atom_addr}")
    except socket.timeout:
        logging.warning(f"[SINK/{interface_name}] Timeout waiting for Atom connection")
        target_socket.close()
        return

    # 4. 双向透传数据
    def forward(src, dst, direction):
        while True:
            data = src.recv(8192)
            if not data:
                break
            dst.sendall(data)

    t1 = threading.Thread(target=forward, args=(atom_socket, target_socket, "Atom->Host"))
    t2 = threading.Thread(target=forward, args=(target_socket, atom_socket, "Host->Atom"))
    t1.start()
    t2.start()
```

---

# Source vs Sink 对比

| 特性                | source              | sink                        |
| ----------------- | ------------------- | -------------------------- |
| outputchannel 指定方 | 设备在回调中指定            | 请求侧在请求中指定                   |
| host:port 来源      | 设备指定 host=127.0.0.1 | 请求侧指定外部 host:port           |
| Atom 角色           | **服务端**，等待 Proxy 连接 | **客户端**，主动连接 Proxy          |
| Proxy → 目标        | 连接 Atom/设备 18012    | 连接 outputchannel 指定的外部地址    |
| 典型场景              | 设备推送数据到本地           | Atom 推送数据到外部地址如 172.18.98.5 |

---

# 文档版本

- 版本：1.2
- 更新日期：2026-05-20
- 更新内容：修正 sink 模式流程，强调"先连接外部目标，再监听本地端口"
