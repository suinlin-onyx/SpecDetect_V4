# 任务：streamsrc 配置同步机制分析

> 创建日期：2026-04-11
> 任务来源：分析 Proxy-B 链路中 streamsrc 机制
> 状态：已澄清（无需同步到设备）

---

## 结论

**streamsrc 不需要同步到设备** - streamsrc 是 Real Atom 内部接口转发用途。

### streamsrc 实际用途

根据架构分析：
- streamsrc (18012) 是 **Real Atom 内部的数据回调通道**
- 设备通过 RMCPTP 连接到 Real Atom 发送命令
- Real Atom 将数据/结果通过 streamsrc 通道推送给调用方（如 SCPI 程序）
- SCPI 程序需要提前监听 18012 端口来接收数据

### 完整数据流

```
SCPI程序 ────── 监听18012 ──────▶ streamsrc (:18012)
                                        ▲
                                        │
Client ── SOAP ──▶ Real Atom ── RMCPTP ─▶│
                                         Device
```

### 与设备的关系

| 组件 | streamsrc 作用 |
|------|---------------|
| Real Atom | 内部转发：将设备数据推送到 18012 |
| Real Device | 不知道 streamsrc 的存在 |
| SCPI程序 | 监听 18012 接收数据回调 |

**结论**：streamsrc 是 Real Atom 与上层应用（如 SCPI）之间的内部通道，与 Real Device 无关。

---

## 背景

在 Proxy-B (Real Atom) 链路中，streamsrc 是设备回调通道：
- Real Atom 监听 streamsrc 端口 (默认 18012)
- Real Device 主动连接 streamsrc 端口

**关键问题**：当修改 `atomsvcconfig.xml` 中的 streamsrc 配置后，远程设备能够感知到变化。这说明 Real Atom 与 Device 之间有配置同步机制。

---

## 已知信息

### 1. streamsrc 是设备回调通道

**架构**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Real Atom 架构                                     │
│                                                                           │
│    SOAP 请求                    streamsrc (TCP Server)                      │
│         │                              ▲                                   │
│         │                              │ 设备主动连接                      │
│         ▼                              │                                   │
│  ┌─────────────┐              ┌───────────────┐                          │
│  │ Real Atom   │─────────────▶│ Real Device   │                          │
│  │ :8282       │  RMCPTP命令 │ :9997        │                          │
│  │ SOAP服务    │              │ streamsrc连接 │                          │
│  └─────────────┘              └───────────────┘                          │
│         │                                                                    │
│         │ 转发RMCPTP命令通过已建立的 streamsrc 连接                          │
└─────────┼──────────────────────────────────────────────────────────────────┘
```

**角色**:
- Atom: TCP服务端 (监听 streamsrc port)
- Device: TCP客户端 (主动连接 Atom)

### 2. streamsrc vs RMCPTP 双通道

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        streamsrc vs RMCPTP 双通道                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  streamsrc通道:                                                             │
│    设备 ──────────────────长连接─────────────────▶ Atom                     │
│         (设备主动连接, 数据回调, 心跳保活)                                   │
│                                                                             │
│  RMCPTP通道:                                                               │
│    Atom ─────────────────短连接─────────────────▶ 设备                     │
│         (Atom主动连接, SOAP业务命令/响应)                                    │
│                                                                             │
│  注意: 两个通道完全独立, 设备需同时维护 streamsrc 长连接才能正常通信         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 通道 | 角色 | 连接模式 | 用途 |
|------|------|----------|------|
| streamsrc | 设备→Atom | 长连接 | 设备数据回调、心跳 |
| RMCPTP | Atom→Device | 短连接 | 业务命令/响应 |

### 3. streamsrc 配置位置

**atomsvcconfig.xml** (Real Atom):
```xml
<streamsrc ip="127.0.0.1" port="18012" />
```

### 4. devinfo 配置 (RMCPTP 通道)

```xml
<station id="53090001" serverip="127.0.0.1" serverport="9996" protocol="rmcp" ... />
```

### 5. Real Atom 启动日志

```
[2026-04-11 13:24:06.465700(22412)]  m_bIsConnected=0
[2026-04-11 13:24:06.467700(22412)] Start Proactor thread pool success
[2026-04-11 13:24:06.469699(49516)] CProactorThreadPool started
[2026-04-11 13:24:06.479277(22412)] 打开 stream source监听端口 18012成功
```

### 6. 协议文档描述

根据 `无线电协议v2.0_通用协议.docx`:

> 连接请求由客户端发起，客户端通过socket连接到中间服务端
> 每执行一功能，均单独建立一连接

**注意**：原始协议文档中**未找到 streamsrc 相关描述**。

---

## 待分析问题

| # | 问题 | 说明 |
|---|------|------|
| 1 | streamsrc 配置同步机制 | Atom 如何将 streamsrc 地址告知 Device |
| 2 | Device 端配置 | 设备端如何存储 streamsrc 地址 |
| 3 | 配置变更生效方式 | 修改 streamsrc 端口后，设备如何感知 |

---

## 分析步骤

### 步骤1: 查找设备端配置文件

**目标目录**:
- `D:\arvin\YL_workapace\`
- `D:\arvin\claude_workspace\RXAtomSvcV3\`
- 远程设备本地配置

**搜索关键词**:
- `streamsrc`
- `18012`
- `stream source`
- `数据通道`

### 步骤2: 分析 RMCPTP 协议

**分析内容**:
- 设备连接 RMCPTP 通道时，Atom 返回的响应中是否包含 streamsrc 信息
- 是否有协议字段携带 streamsrc 地址

### 步骤3: 抓包验证

**验证方法**:
- 在 Real Atom 与 Device 之间抓包
- 观察设备注册/连接时的数据交换

---

## 参考文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 无线电协议v2.0 | `D:\arvin\YL_workapace\超短波监测管理一体化服务接口规范\无线电协议2.0\` | 原始协议规范 |
| atomsvcconfig | `D:\arvin\claude_workspace\RXAtomSvcV3\config\` | Real Atom 配置 |
| devinfo | `D:\arvin\claude_workspace\RXAtomSvcV3\config\devinfo\` | 设备配置 |

---

## 下一步行动

- [ ] 在 YL_workspace 目录查找设备端配置文件
- [ ] 在 RXAtomSvcV3 目录查找 streamsrc 相关配置
- [ ] 分析 RMCPTP 设备注册流程

---

**最后更新**: 2026-04-11
