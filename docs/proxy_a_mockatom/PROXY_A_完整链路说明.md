# Proxy-A 完整链路说明

> 创建日期：2026-04-11
> 更新日期：2026-04-11 16:04

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Proxy-A 完整链路                                      │
│                           (开发/测试链路)                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

  SOAP请求                 SOAP转发                 RMCPTP命令              RMCPTP响应
┌──────────────┐    ┌──────────────┐    ┌────────────┐    ┌──────────────┐    ┌────────────┐
│ 聚合客户端    │───▶│ Proxy-A      │───▶│Mock Atom   │───▶│Mock Device  │◀───│Mock Device│
│main_aggregated│    │:8080        │    │:9090       │    │:9000        │    │:9000      │
│_client.py     │    │             │    │            │    │             │    │           │
└──────────────┘    └──────────────┘    └────────────┘    └──────────────┘    └────────────┘
                                                                                 ▲
                                                                                 │
                                    ┌─────────────────────────────────────────────┘
                                    │
                                    │ 内部转发 (可选)
                                    ▼
                                                                                 ▲
                                                                                 │
                                    ┌─────────────────────────────────────────────┘
                                    │
                                    │ 内部转发 (可选)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Mock Atom 内部                                      │
│                                                                                 │
│  ┌──────────────┐                                                               │
│  │  streamsrc   │  数据回调 (Mock Atom 可选地将数据转发到此端口)                  │
│  │  :18012      │  注意: Proxy-A 链路中此端口暂未使用                            │
│  └──────────────┘                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**数据流说明**:
1. Client -> Proxy-A -> Mock Atom: SOAP 请求
2. Mock Atom -> Mock Device: RMCPTP 命令
3. Mock Device -> Mock Atom: RMCPTP 响应
4. **可选内部转发**: Mock Atom 可通过 streamsrc (:18012) 转发测量数据（Proxy-A 链路中暂未使用）

**重要澄清**: streamsrc (:18012) 是 Mock Atom **内部接口**，用于将测量数据转发给上层应用。在 Proxy-A 开发/测试链路中，此功能暂未实现。

**定位**: 开发/测试链路，使用 Mock Atom + Mock Device 模拟完整流程

---

## 2. 链路组件

| 组件 | 端口 | 文件 | 作用 |
|------|------|------|------|
| 聚合客户端 | 8080 | `main_aggregated_client.py` | SOAP客户端入口（Mock客户端） |
| Proxy-A | 8080 | 内部路由 | SOAP请求转发 |
| Mock Atom | 9090 | `main_atom.py` | SOAP服务端，RMCPTP客户端 |
| Mock Device | 9000 | `mock_device/tcp_server.py` | RMCPTP服务端 |

---

## 3. 数据流动

### 3.1 请求数据流

```
Client                  Proxy-A              Mock Atom             Mock Device
  │                       │                     │                     │
  │──── SOAP请求 ────────▶│──── SOAP请求 ──────▶│──── RMCPTP命令 ────▶│
  │   POST /B_XXX         │   透传              │   二进制帧           │
  │                       │                     │                     │
```

### 3.2 响应数据流

```
Mock Device            Mock Atom             Proxy-A              Client
  │                       │                     │                     │
  │◀─── RMCPTP响应 ─────│──── 解析+转换 ──────│──── SOAP响应 ───────│
  │   二进制帧            │                     │                     │
```

---

## 4. 端口配置

### settings.py

```python
SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8080,         # Proxy-A 监听端口
    },
    'atom': {
        'host': '127.0.0.1',
        'port': 9090,         # Mock Atom 端口
        'device_host': '127.0.0.1',  # Mock Device 地址
        'device_port': 9000    # Mock Device RMCPTP 端口
    },
    'mock_device': {
        'host': '127.0.0.1',
        'port': 9000,
        'scenario': 'normal'
    }
}
```

---

## 5. RMCPTP 帧格式

### 5.1 帧头结构 (18字节)

| 字段 | 字节 | 字节序 | 说明 |
|------|------|--------|------|
| dwLength | 4 | 小端 | 帧长度 |
| tmStamp | 8 | 小端 | FILETIME时间戳 |
| nVersion | 2 | **大端** | =7 (0x0007) |
| nMsgType | 1 | 小端 | 90=请求, 6=响应, 0=数据 |
| nFlags | 1 | 小端 | 0x01请求/0x00响应 |
| nCheckSum | 2 | 小端 | 校验和 |

### 5.2 消息类型

| nMsgType | 类型 | 说明 |
|----------|------|------|
| 90 (0x5A) | REQUEST | 设备控制请求 |
| 6 | RESPONSE | 响应消息 |
| 0 | DATA | 数据帧 |

---

## 6. SOAP 接口

### 6.1 支持的接口

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

### 6.2 接口分类

| 分类 | 接口 | 说明 |
|------|------|------|
| 查询接口 | B_QueryDeviceInfo, B_QueryFaciDevStat | 直接返回模拟数据 |
| 控制接口 | B_StopMeas | 停止任务 |
| 执行接口 | 其他7个 | 需连接设备发送RMCPTP |

---

## 7. streamsrc 机制

**注意**: Proxy-A 链路中 streamsrc 未被使用，Mock Device 作为 TCP 客户端连接 Mock Atom 的 streamsrc 端口。

```
Mock Device (9000) ────── streamsrc长连接 ──────▶ Mock Atom (:18012)
       │                                                ▲
       │              RMCPTP命令                         │
       └────────────────────────────────────────────────┘
                        (复用同一连接)
```

**实际实现**: Mock Device 复用与 Mock Atom 的 RMCPTP 连接发送数据和接收命令，而非独立的 streamsrc 通道。

---

## 8. 测试结果

### 8.1 接口测试 (2026-04-10)

| # | 接口 | 状态 | taskid |
|---|------|------|--------|
| 1 | B_QueryDeviceInfo | ✅ | - |
| 2 | B_QueryFaciDevStat | ✅ | - |
| 3 | B_FScan | ✅ | 获取成功 |
| 4 | B_FScanDF | ✅ | 获取成功 |
| 5 | B_MScan | ✅ | 获取成功 |
| 6 | B_MScanDF | ✅ | 获取成功 |
| 7 | B_PScan | ✅ | 获取成功 |
| 8 | B_SglFreqDF | ✅ | 获取成功 |
| 9 | B_SglFreqMeas | ✅ | 获取成功 |
| 10 | B_WBDF | ✅ | 获取成功 |

**完成率**: 10/10 (100%)

---

## 9. 与 Proxy-B 对比

| 对比项 | Proxy-A | Proxy-B |
|--------|---------|---------|
| 端口 | 8080 | 8081 |
| Atom | Mock Atom (9090) | Real Atom (8282) |
| Device | Mock Device (9000) | Real Device (100.89.170.72:9997) |
| streamsrc | 未使用 | 设备回调通道 |
| 数据源 | 模拟数据 | 真实设备数据 |
| 响应速度 | 即时返回 | 依赖设备响应 |

---

## 10. 相关文件

| 文件 | 作用 |
|------|------|
| `main_aggregated_client.py` | 聚合客户端入口（Mock客户端） |
| `main_atom.py` | Mock Atom 主服务 |
| `mock_device/tcp_server.py` | Mock Device RMCPTP 服务 |
| `app/atom_service/protocol_builder.py` | RMCPTP 帧构建 |
| `config/settings.py` | Proxy-A 配置 |
| `app/proxy_service/routes.py` | SOAP 路由 |

---

## 11. 启动方式

```bash
# 启动聚合客户端 (Proxy-A 链路)
cd D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC
python main_aggregated_client.py

# 或使用 run_all.py
python run_all.py
```

---

**最后更新**: 2026-04-11
