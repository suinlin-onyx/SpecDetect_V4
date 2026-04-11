# Proxy-B 完整链路说明

> 创建日期：2026-04-11
> 更新日期：2026-04-11 16:00

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      Proxy-B 完整链路                                    │
│                               (Real Atom 双侧数据抓包验证链路)                            │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

  SOAP请求              SOAP转发              RMCPTP命令              RMCPTP响应
┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────┐
│RXAtom    │──▶│SOAP Proxy    │──▶│Real Atom     │──▶│rmcp_proxy    │──▶│Real Device │
│TestTool3 │   │(:8082)       │   │:8282         │   │:9996         │   │:9997       │
│(Client)  │   │日志抓取      │   │              │   │日志抓取       │   │            │
└──────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └────────────┘
     │                                  │                                  │
     │ ① SOAP层                        │ ② RMCPTP层                      │
     │ 抓取Client↔Atom往来             │ 抓取Atom↔Device往来             │
     │                                  │                                  │
     ▼                                  ▼                                  ▼
┌──────────┐                    ┌──────────────┐                   ┌────────────┐
│SOAP日志  │                    │ 数据对比      │                   │RMCPTP日志  │
│请求/响应 │                    │ 对齐请求      │                   │请求/响应   │
└──────────┘                    └──────────────┘                   └────────────┘
```

**【核心目标】抓取 Atom 两侧的往来数据流，解析格式，对齐请求，解析传输结构体内容**

| 抓包点 | 位置 | 日志内容 |
|--------|------|----------|
| ① SOAP层 | Client ↔ Real Atom | SOAP XML 请求/响应 |
| ② RMCPTP层 | Real Atom ↔ Real Device | RMCPTP 二进制帧 |

**数据对比验证流程**：
1. Client 发送 SOAP 请求 → SOAP Proxy 记录
2. Real Atom 接收请求 → 转发 RMCPTP 到 Device → rmcp_proxy 记录
3. Device 返回 RMCPTP 响应 → rmcp_proxy 记录
4. Real Atom 返回 SOAP 响应 → SOAP Proxy 记录
5. **对齐两侧日志时间戳，验证数据完整性，解析结构体内容**
                                                                                          ▲
                                                                                          │
                                    ┌────────────────────────────────────────────────────┘
                                    │
                                    │ 内部转发 (127.0.0.1 环回)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      Real Atom 内部                                        │
│                                                                                             │
│  ┌──────────────────┐                                                                       │
│  │  streamsrc       │  数据回调 (SCPI客户端监听此端口接收测量结果)                          │
│  │  :18012          │                                                                       │
│  │  (TCP Server)    │                                                                       │
│  └──────────────────┘                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

**数据流说明**:
1. Client -> Proxy-B -> Real Atom: SOAP 请求
2. Real Atom -> rmcp_proxy -> Real Device: RMCPTP 命令
3. Real Device -> rmcp_proxy -> Real Atom: RMCPTP 响应
4. **Real Atom 内部转发**: 将 Device 数据通过 streamsrc (:18012) 转发给 SCPI 客户端

**IP 地址说明**:
- Proxy-B 监听: `0.0.0.0:8081`
- Real Atom: `127.0.0.1:8282` (本地)
- rmcp_proxy: `127.0.0.1:9996` (本地)
- Real Device: 远程设备 `100.89.170.72:9997`
- streamsrc: `127.0.0.1:18012` (Real Atom 内部环回)

**重要澄清**: streamsrc (:18012) 是 Real Atom **内部接口**，用于将测量数据转发给上层应用（如 SCPI）。Device 不知道 streamsrc 的存在，Device 只通过 RMCPTP 与 Atom 通信。

**定位**: 与 Real Atom 对比的验证链路，用于抓取真实设备的 RMCPTP 数据

---

## 2. 链路组件

| 组件 | 地址 | 端口 | 文件 | 作用 |
|------|------|------|------|------|
| RXAtomTestTool3 | - | - | - | 真实客户端 |
| SOAP Proxy | 127.0.0.1 | 8082 | `soap_proxy/` | SOAP请求转发+日志抓取 |
| Real Atom | 127.0.0.1 | 8282 | RXAtomSvcV3.exe | SOAP服务端，RMCPTP客户端 |
| rmcp_proxy | 127.0.0.1 | 9996 | `rmcp_proxy/rmcp_proxy.py` | TCP透明代理，RMCPTP流量捕获 |
| Real Device | 100.89.170.72 | 9997 | 远程设备 | RMCPTP服务端 |

---

## 3. 数据流动

### 3.1 请求数据流

```
Client                  Proxy-B             Real Atom           rmcp_proxy       Real Device
  │                       │                     │                   │                │
  │──── SOAP请求 ────────▶│──── SOAP请求 ──────▶│──── RMCPTP命令 ──▶│──── 透明转发 ──▶│
  │   POST /B_XXX         │   透传              │   二进制帧         │                │
```

### 3.2 响应数据流

```
Real Device            rmcp_proxy           Real Atom           Proxy-B           Client
  │                       │                     │                   │                │
  │◀─── RMCPTP响应/数据 ──│◀──── 透明转发 ─────│◀── streamsrc ─────│◀── SOAP响应 ───│
  │   二进制帧            │                     │   数据回调         │                │
```

---

## 4. streamsrc vs RMCPTP 双通道

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        streamsrc vs RMCPTP 双通道                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  streamsrc通道 (长连接):                                                   │
│  ┌─────────┐                              ┌─────────┐                      │
│  │ 设备    │◀─────────────────────────────│ Real    │                      │
│  │ :9997   │     设备主动连接              │ Atom    │                      │
│  └─────────┘     数据回调                   │ :18012  │                      │
│              (心跳保活)                      └─────────┘                      │
│                                                                             │
│  RMCPTP通道 (短连接):                                                     │
│  ┌─────────┐                              ┌─────────┐                      │
│  │ Real    │─────────────────────────────▶│ 设备    │                      │
│  │ Atom    │     Atom主动连接              │ :9997   │                      │
│  │ :8282   │     SOAP业务命令/响应         └─────────┘                      │
│  └─────────┘                                                              │
│                                                                             │
│  注意: 两个通道完全独立, 设备需同时维护 streamsrc 长连接才能正常通信         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 通道 | 角色 | 连接模式 | 用途 |
|------|------|----------|------|
| streamsrc | Atom是TCP服务端，设备是客户端 | **长连接** | 设备数据回调、心跳保活 |
| RMCPTP | Atom是TCP客户端，设备是服务端 | **短连接** | SOAP业务命令/响应 |

---

## 5. 端口配置

### settings_proxy_b.py

```python
SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8081,         # Proxy-B 监听端口
    },
    'atom': {
        'host': '127.0.0.1',  # Real Atom 地址 (本地)
        'port': 8282,              # Real Atom 端口
    }
}
```

### rmcp_proxy/config.py

```python
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9996
DEVICE_HOST = "100.89.170.72"
DEVICE_PORT = 9997
```

### atomsvcconfig.xml (Real Atom)

```xml
<streamsrc ip="127.0.0.1" port="18012" />
```

---

## 6. RMCPTP 帧格式

### 6.1 帧头结构 (18字节)

| 字段 | 字节 | 字节序 | 说明 |
|------|------|--------|------|
| dwLength | 4 | 小端 | 帧长度 |
| tmStamp | 8 | 小端 | FILETIME时间戳 |
| nVersion | 2 | **大端** | =7 (0x0007) |
| nMsgType | 1 | 小端 | 90=请求, 6=响应, 0=数据 |
| nFlags | 1 | 小端 | 0x01请求/0x00响应 |
| nCheckSum | 2 | 小端 | 校验和 |

### 6.2 消息类型

| nMsgType | 类型 | 说明 |
|----------|------|------|
| 90 (0x5A) | REQUEST | 设备控制请求 |
| 6 | RESPONSE | 响应消息 |
| 0 | DATA | 数据帧 |

---

## 7. SOAP 接口

### 7.1 支持的接口

| # | 接口 | 端点 | 设备连接 | 说明 |
|---|------|------|----------|------|
| 1 | B_QueryDeviceInfo | /B_QueryDeviceInfo | 不需要 | 设备信息查询 |
| 2 | B_QueryFaciDevStat | /B_QueryFaciDevStat | 不需要 | 设备状态查询 |
| 3 | B_StopMeas | /B_StopMeas | 不需要 | 停止测量 |
| 4 | B_SglFreqMeas | /B_SglFreqMeas | 需要 | 单频测量 |
| 5 | B_SglFreqDF | /B_SglFreqDF | 需要 | 单频测向 |
| 6 | B_FScan | /B_FScan | 需要 | 频段扫描 |
| 7 | B_FScanDF | /B_FScanDF | 需要 | 频段扫描测向 |
| 8 | B_MScan | /B_MScan | 需要 | 多信道扫描 |
| 9 | B_MScanDF | /B_MScanDF | 需要 | 多信道扫描测向 |
| 10 | B_PScan | /B_PScan | 需要 | 频谱扫描 |
| 11 | B_WBDF | /B_WBDF | 需要 | 宽带测向 |

### 7.2 接口分类

| 分类 | 接口 | 说明 |
|------|------|------|
| 查询接口 | B_QueryDeviceInfo, B_QueryFaciDevStat | 直接返回设备信息 |
| 控制接口 | B_StopMeas | 停止任务 |
| 执行接口 | 其他7个 | 需设备连接 streamsrc |

---

## 8. rmcp_proxy 功能

### 8.1 功能概述

1. **TCP透明代理**: 监听 9996 端口，转发到远程设备 9997
2. **流量记录**: 记录原始二进制到 `.raw` 文件
3. **帧解析日志**: 解析帧头并记录到 `.log` 文件
4. **结构化数据**: 保存到 `.json` 文件

### 8.2 输出文件

| 格式 | 用途 |
|------|------|
| `.raw` | 原始二进制，Wireshark打开 |
| `.json` | 结构化数据 |
| `.log` | 人类可读日志 |
| `.csv` | 连接统计 |

---

## 9. Real Atom 启动日志

```
[2026-04-11 13:24:06.465700(22412)]  m_bIsConnected=0
[2026-04-11 13:24:06.467700(22412)] Start Proactor thread pool success
[2026-04-11 13:24:06.469699(49516)] CProactorThreadPool started
[2026-04-11 13:24:06.479277(22412)] 打开 stream source监听端口 18012成功
```

| 日志 | 含义 |
|------|------|
| m_bIsConnected=0 | 设备未连接 |
| Proactor thread pool | 异步IO线程池启动 |
| 打开 stream source 监听端口 | streamsrc 开始监听 18012 |

---

## 10. 测试结果

### 10.1 rmcp_proxy 捕获测试 (2026-04-10)

**链路**: Mock Atom (8283) → rmcp_proxy (9996) → Real Device (100.89.170.72:9997)

| 接口 | 状态 | taskid |
|------|------|--------|
| B_MScan | ✅ 成功 | 87D36EE8-34EE-11F1-8002-00D8612F75B8 |
| B_MScanDF | ✅ 成功 | 99D66AC8-34EE-11F1-8000-00D8612F75B8 |
| B_FScanDF | ✅ 成功 | ABD4C260-34EE-11F1-8000-00D8612F75B8 |

### 10.2 Mock Atom + rmcp_proxy 测试 (2026-04-11)

| 接口类型 | 状态 | 说明 |
|----------|------|------|
| 查询接口 (1-3) | ✅ 成功 | 直接返回设备信息 |
| 执行接口 (4-11) | ⚠️ 超时 | 链路通，设备未响应 |

**设备超时原因**: 远程设备 100.89.170.72:9997 未连接 streamsrc (18012)

---

## 11. 与 Proxy-A 对比

| 对比项 | Proxy-A | Proxy-B |
|--------|---------|---------|
| 链路 | 聚合客户端 → Proxy-A → Mock Atom | RXAtomTestTool3 → SOAP Proxy → Real Atom |
| 客户端端口 | 8080 | 8082 |
| Atom | Mock Atom (9090) | Real Atom (8282) |
| Device | Mock Device (9000) | Real Device (100.89.170.72:9997) |
| streamsrc | 未使用 | 设备回调通道 |
| 数据源 | 模拟数据 | 真实设备数据 |
| SOAP Proxy | 无 | 日志抓取 |
| rmcp_proxy | 无 | 流量捕获 |
| 目标 | 开发测试 | 格式验证+数据对比 |

---

## 12. 相关文件

| 文件 | 作用 |
|------|------|
| `soap_proxy/` | SOAP 请求转发+日志抓取 |
| `rmcp_proxy/` | RMCPTP 透明代理+流量捕获 |
| `main_aggregated_client.py` | Proxy-A 聚合客户端 |
| `main_proxy_b.py` | Proxy-B 主服务 |

---

## 13. SOAP Proxy 功能需求

### 13.1 功能概述

| 功能 | 说明 |
|------|------|
| 位置 | RXAtomTestTool3 ↔ Real Atom |
| 端口 | 127.0.0.1:8082 |
| 协议 | HTTP/SOAP |
| 日志 | 请求/响应 XML 完整记录 |

### 13.2 日志格式

```log
[2026-04-11 16:10:00.123456] >>> B_FScan
[Request-ID: uuid]
[Request]
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope ...>
  ...
</soapenv:Envelope>
[Response]
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope ...>
  ...
</soapenv:Envelope>
```

### 13.3 日志文件

| 文件 | 内容 |
|------|------|
| `soap_proxy_{date}.log` | 当天所有 SOAP 请求/响应对 |
| `soap_proxy_{date}_{uuid}_req.xml` | 单个请求完整 XML |
| `soap_proxy_{date}_{uuid}_res.xml` | 单个响应完整 XML |

### 13.4 与 rmcp_proxy 对齐

```
RXAtomTestTool3 ──▶ SOAP Proxy ──▶ Real Atom ──▶ rmcp_proxy ──▶ Device
     │                │              │             │
     │ ① SOAP日志     │ ② 时间戳     │ ③ RMCPTP日志│
     ▼                ▼              ▼             ▼
  Client侧         对齐点1        对齐点2       Device侧
```

**对齐方式**：通过时间戳 + 操作类型 + taskid 关联两侧日志

---

## 14. 启动方式

```bash
cd D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC

# 1. 启动 SOAP Proxy (8082) - 抓取 Client↔Atom 的 SOAP 日志
python soap_proxy/main.py
# 或 python -m soap_proxy

# 2. 启动 rmcp_proxy (9996) - 抓取 Atom↔Device 的 RMCPTP 日志
python rmcp_proxy/rmcp_proxy.py

# 3. 启动 Real Atom
D:\arvin\claude_workspace\RXAtomSvcV3\AtomSvcV3.exe

# 4. 使用 RXAtomTestTool3 连接 SOAP Proxy (:8082) 发送请求
```

**注意**：RXAtomTestTool3 应配置连接 `127.0.0.1:8082` 而非直接连接 Real Atom

---

## 14. 已知问题

### 问题: 远程设备未响应

**现象**: rmcp_proxy 日志显示 `C->S RAW_DATA`，但设备无响应

**可能原因**:
1. 远程设备未连接 streamsrc (18012)
2. streamsrc IP 配置不正确
3. 设备认证/会话问题

**验证方式**: 检查 Real Atom 日志中 `m_bIsConnected` 状态

---

**最后更新**: 2026-04-11
