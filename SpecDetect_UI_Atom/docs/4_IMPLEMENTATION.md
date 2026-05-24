# SpecDetect_UI_Atom 实现文档

**创建日期**: 2026-04-16
**更新日期**: 2026-04-18

---

## 4.1 模块结构

### 4.1.1 当前实现

当前实现为单文件：`emulated_atom.py`

```
emulated_atom.py
│
├── 常量定义
│   ├── LEADER, VER, DT_MSCAN, DT_FSCAN 等
│   └── USE_MOCK_DATA 标志
│
├── 数据结构
│   ├── StreamSession: 会话数据结构
│   ├── BandCollector: 三频段收集器 (Queue FIFO)
│   └── RMCPHeader: RMCP帧头
│
├── 帧构建函数
│   ├── build_streamsrc_frame_*() - streamsrc帧构建
│   ├── build_mscan_frame() - MSCAN帧构建
│   └── build_pscan_*_frame() - PScan帧构建
│
├── RMCP处理
│   ├── build_rmcp_frame()
│   ├── _parse_single_fscan_frame()
│   └── send_to_rmcp_proxy()
│
├── SOAP处理
│   ├── parse_soap_request()
│   ├── build_soap_response()
│   └── _handle_*()
│
├── StreamSrcServer
│   ├── start()
│   ├── _accept_loop()
│   ├── _try_match_pending_session()
│   ├── _start_*_push()
│   └── push_frame_to_session()
│
└── AtomService
    ├── start()
    └── stop()
```

### 4.1.2 SpecDetect_Atom 目标模块结构

→ 参见 [../SpecDetect_Atom/docs/](../SpecDetect_Atom/docs/)

```
SpecDetect_Atom/
├── main.py
├── soap/
│   ├── server.py
│   ├── parser.py
│   └── builder.py
├── streaming/
│   └── streamsrc_server.py
├── session/
│   ├── session.py
│   └── session_manager.py
├── protocol/
│   ├── rmcp_client.py
│   ├── rmcp_frame.py
│   └── fscan_processor.py
├── handlers/
│   ├── fscan_handler.py
│   ├── mscan_handler.py
│   └── stop_handler.py
└── preset/
    └── device_preset.py
```

---

## 4.2 配置说明

### 4.2.1 当前配置

emulated_atom.py 中的配置：

```python
SOAP_PORT = 8283                    # SOAP服务端口
STREAMSRC_PORT = 18013             # streamsrc端口
DEVICE_HOST = '100.72.95.36'       # 设备地址
DEVICE_PORT = 1449                  # 设备RMCP端口
RMCP_PROXY_HOST = '127.0.0.1'      # rmcp_proxy地址
RMCP_PROXY_PORT = 9996             # rmcp_proxy端口
USE_MOCK_DATA = False               # 是否使用模拟数据
```

### 4.2.2 配置验证

| 配置项 | 说明 | 验证方法 |
|--------|------|----------|
| SOAP_PORT | SOAP服务监听端口 | telnet 127.0.0.1 8283 |
| STREAMSRC_PORT | streamsrc监听端口 | telnet 127.0.0.1 18013 |
| DEVICE_HOST/PORT | 设备连接 | 确认设备可达 |
| RMCP_PROXY_* | rmcp_proxy连接 | 确认rmcp_proxy运行 |

---

## 4.3 部署指南

### 4.3.1 前置条件

1. Python 3.8+
2. rmcp_proxy 服务运行在 127.0.0.1:9996
3. 网络可达目标设备 100.72.95.36:1449

### 4.3.2 启动步骤

```bash
# 1. 确保 rmcp_proxy 运行
cd SpecDetect_POC
python -m rmcp_proxy.main

# 2. 启动 emulated_atom
python -m experimental.emulated_atom

# 3. 测试连接
telnet 127.0.0.1 8283
```

### 4.3.3 测试验证

```bash
# 使用测试工具连接 127.0.0.1:8283
# 或使用 soap_proxy 转发到 emulated_atom
cd SpecDetect_POC/soap_proxy
python -m transparent_proxy 8284 127.0.0.1 8283
```

---

## 4.4 实现详情

### 4.4.1 接口实现状态

| 接口 | 处理函数 | 帧构建 | 推送函数 | 状态 |
|------|---------|--------|---------|------|
| B_FScan | _handle_fscan | build_streamsrc_frame | _start_fscan_push | ✅ |
| B_PScan | _handle_pscan | 同FSCAN | 同FSCAN | ✅ |
| B_MScan | _handle_mscan | build_mscan_frame | _start_mscan_push | ✅ |
| B_StopMeas | _handle_stopmeas | N/A | N/A | ✅ |
| B_QueryDeviceInfo | _handle_query_device | N/A | N/A | ✅ |

### 4.4.2 会话管理

```
pending_sessions: {taskid -> StreamSession}
  │
  │ B_FScan/B_PScan/B_MScan 请求到达
  ▼
创建 pending_session(taskid, fscan_params)
  │
  │ streamsrc 客户端连接 (18013)
  ▼
_link_pending_session()
  │
  │ 查找匹配的 pending_session (taskid 或 FIFO)
  ▼
session.streamsrc_client = client_socket
session.state = 'active'
  │
  ▼
_start_*_push() 启动推送线程
```

### 4.4.3 BandCollector FIFO同步

BandCollector 确保三频段按顺序输出：

```python
# 输入: [Band2, Band1, Band3] (乱序)
# 输出: [Band1, Band2, Band3] (按序)
```

---

## 4.5 子项路径映射

### 4.5.1 SpecDetect_Atom

→ 源代码: [../SpecDetect_Atom/src/](../SpecDetect_Atom/src/)
→ 详细设计: [../SpecDetect_Atom/docs/](../SpecDetect_Atom/docs/)

### 4.5.2 SpecDetect_Client

当前状态：预留，未实现

---

## 4.6 相关文档

| 文档 | 说明 |
|------|------|
| [1_REQUIREMENTS.md](1_REQUIREMENTS.md) | 需求概述 |
| [2_ARCHITECTURE.md](2_ARCHITECTURE.md) | 架构设计 |
| [3_PROTOCOL.md](3_PROTOCOL.md) | 协议细节 |
| [5_ISSUES.md](5_ISSUES.md) | 问题记录 |
| [../SpecDetect_Atom/src/](../SpecDetect_Atom/src/) | Atom源代码 |
