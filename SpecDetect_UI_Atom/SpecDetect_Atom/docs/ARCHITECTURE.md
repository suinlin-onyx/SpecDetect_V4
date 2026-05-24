# SpecDetect_Atom 详细架构

**创建日期**: 2026-04-18
**最后更新**: 2026-04-25

---

## 1. 定位

本文档是 SpecDetect_Atom 子项的详细架构设计，属于 SpecDetect_UI_Atom 工作空间的一部分。

---

## 2. 目录结构 (实际)

```
SpecDetect_Atom/
├── main.py                              # 服务入口
├── config/
│   └── settings.json                    # Atom配置 (host, port, timeout)
│
├── src/atom/
│   ├── __init__.py
│   ├── config.py                        # 配置加载
│   ├── service.py                       # Atom服务主类 (协调层)
│   ├── session.py                       # StreamSession + BandCollector
│   ├── session_manager.py               # 会话管理
│   ├── fscan_processor.py               # FSCAN 数据类 (SpectrumData)
│   │
│   ├── rmcp/                            # RMCP 协议模块
│   │   ├── __init__.py
│   │   ├── client.py                    # RMCP 客户端 (连接/收发)
│   │   ├── frame.py                     # RMCP 帧构建/解析/分派
│   │   └── logger.py                    # RMCP 帧日志记录
│   │
│   ├── soap/                            # SOAP 协议模块
│   │   ├── __init__.py
│   │   ├── server.py                    # SOAP 服务端
│   │   └── parser.py                    # SOAP 请求解析
│   │
│   └── stream/                          # streamsrc 推送模块
│       ├── __init__.py
│       ├── server.py                    # streamsrc 服务端 (连接/推送)
│       └── frame.py                     # streamsrc 帧生成 (各类型)
│
├── preset/
│   └── device_preset.py                 # 设备预置信息 + XML模板
│
└── log/
    └── logger.py                        # 日志模块
```

---

## 3. 模块职责

### 3.1 service.py — 协调层

Atom 服务主类 `AtomService`，负责：

- 接收 SOAP 请求，按接口名分派到 `_handle_*()` 方法
- 管理 RMCP 连接和接收线程
- 管理 streamsrc 推送线程
- 协调各模块交互

**接口处理方法**:

| 方法                       | 接口                | funcid | 说明     |
| ------------------------ | ----------------- | ------ | ------ |
| `_handle_fscan()`        | B_FScan           | 15     | 三频段扫描  |
| `_handle_pscan()`        | B_PScan           | 16     | 频谱扫描   |
| `_handle_mscan()`        | B_MScan           | 14     | 单频点扫描  |
| `_handle_sglfreqmeas()`  | B_SglFreqMeas     | 11     | 单频率测量  |
| `_handle_stopmeas()`     | B_StopMeas        | -      | 停止测量   |
| `_handle_query_device()` | B_QueryDeviceInfo | -      | 设备信息查询 |

**核心内部方法**:

| 方法                       | 说明                                                 |
| ------------------------ | -------------------------------------------------- |
| `_start_rmcp_receive()`  | 启动 RMCP 接收线程 (FScan/MScan/SglFreq 通用路径)            |
| `_start_pscan_receive()` | 启动 PScan 专用接收线程 (raw DSCAN 流)                      |
| `_push_frame()`          | 根据 mode 生成 streamsrc 帧 (fscan/mscan/sglfreq/pscan) |

### 3.2 rmcp/ — RMCP 协议模块

| 文件          | 职责                         |
| ----------- | -------------------------- |
| `client.py` | TCP 连接管理、发送请求、接收响应         |
| `frame.py`  | RMCP 帧构建、帧头验证、payload 解析分派 |
| `logger.py` | RMCP 帧日志记录                 |

**client.py 关键函数**:

| 函数                                        | 说明                                          |
| ----------------------------------------- | ------------------------------------------- |
| `connect()` / `disconnect()`              | TCP 连接管理                                    |
| `send_request(xml, func_id)`              | 发送 RMCP 请求帧                                 |
| `receive_responses()`                     | 通用接收：TCP 流拆帧，返回完整 RMCP 帧列表                  |
| `get_callback_datas()`                    | 通用接收+解析：返回业务数据 dict 列表                      |
| `receive_pscan_raw(callback, stop_event)` | **PScan 专用**：提取控制帧后，将 buffer 视为 raw DSCAN 流 |

**frame.py 关键函数**:

| 函数                            | 说明                                              |
| ----------------------------- | ----------------------------------------------- |
| `build_rmcp_frame()`          | 构建 RMCP 请求帧                                     |
| `validate_rmcp_frame()`       | 验证 RMCP 帧头 (nVersion=7)                         |
| `parse_rmcp_callback_frame()` | **统一入口**：解析 RMCP 帧，按 n_bd_type 分派到对应 parser     |
| `parse_fscan_payload()`       | 解析 FSCAN(15)/SGLFREQ(14)/IFANALYSIS(11) payload |
| `parse_dscan_payload()`       | 解析 DSCAN(16) payload (标准 RMCP 帧路径)              |

**n_bd_type 分派表** (`_BD_TYPE_PARSER_MAP`):

| n_bd_type | 类型         | 解析函数                  |
| --------- | ---------- | --------------------- |
| 16        | DSCAN      | `parse_dscan_payload` |
| 15        | FSCAN      | `parse_fscan_payload` |
| 14        | SGLFREQ    | `parse_fscan_payload` |
| 11        | IFANALYSIS | `parse_fscan_payload` |

### 3.3 stream/ — streamsrc 推送模块

| 文件          | 职责                        |
| ----------- | ------------------------- |
| `server.py` | 接收 streamsrc 客户端连接、管理推送线程 |
| `frame.py`  | 生成各类型 streamsrc 帧         |

**frame.py 帧生成函数**:

| 函数                             | 帧类型         | 大小    | 说明                       |
| ------------------------------ | ----------- | ----- | ------------------------ |
| `build_fscan_frame()`          | FSCAN-529   | 1086B | FScan 三频段 (Band1/2)      |
| `build_fscan_frame_434()`      | FSCAN-434   | 896B  | FScan Band3              |
| `build_mscan_frame()`          | MSCAN       | 45B   | 单频点扫描 (DT=13)            |
| `build_pscan_fscan_frame()`    | PScan FSCAN | 2944B | PScan 频谱帧 (DT=12, 1441点) |
| `build_pscan_spectrum_frame()` | PScan 频谱    | 3256B | SglFreq 频谱帧 (DT=7)       |
| `build_pscan_level_frame()`    | PScan 电平    | 40B   | SglFreq 电平帧 (DT=101)     |
| `build_pscan_itu_frame()`      | PScan ITU   | 36B   | SglFreq ITU帧 (DT=8)      |

### 3.4 session.py — 会话数据

| 类               | 说明                                        |
| --------------- | ----------------------------------------- |
| `StreamSession` | 会话数据结构 (状态、参数、连接、线程控制)                    |
| `BandCollector` | FScan 三频段收集器 (Queue FIFO，凑齐 B1+B2+B3 后输出) |

**StreamSession 关键属性**:

| 属性                   | 说明                                              |
| -------------------- | ----------------------------------------------- |
| `state`              | SessionState 枚举 (PENDING/ACTIVE/CLOSING/CLOSED) |
| `fscan_params`       | SOAP 请求参数 (stc, frequency 等)                    |
| `streamsrc_client`   | streamsrc 客户端 socket                            |
| `band_collector`     | FScan 专用 BandCollector                          |
| `_latest_band_info`  | MScan/SglFreq 最新 RMCP 回调数据                      |
| `_sglfreq_frame_idx` | SglFreq 三帧循环索引 (0/1/2)                          |
| `_pscan_band`        | PScan 最新 DSCAN 数据                               |

### 3.5 soap/ — SOAP 协议模块

| 文件          | 职责                   |
| ----------- | -------------------- |
| `server.py` | SOAP 服务端 socket 管理   |
| `parser.py` | HTTP 头解析、SOAP XML 解析 |

---

## 4. 数据流

### 4.1 FScan (通用 RMCP 路径)

```
SOAP B_FScan → _handle_fscan()
  → RMCP send_request(func_id=15)
  → _start_rmcp_receive()
    → receive_loop()
      → get_callback_datas()
        → receive_responses() → 拆帧
        → parse_rmcp_callback_frame() → parse_fscan_payload()
      → BandCollector.put(band_info)  # 凑齐 B1+B2+B3
  → push_loop (fscan 分支)
    → band_collector.get() → [B1, B2, B3]
    → _push_frame(session, band)
      → build_fscan_frame() / build_fscan_frame_434()
    → streamsrc_client.sendall()
```

### 4.2 PScan (专用 raw DSCAN 路径)

```
SOAP B_PScan → _handle_pscan()
  → RMCP send_request(func_id=16)
  → _start_pscan_receive()
    → receive_pscan_raw()
      1. 提取 RMCP 控制帧 (69B, msg_type=6)
      2. 后续 buffer 视为 raw DSCAN payload 流 (无帧头)
      3. 按 reserved 字段拆帧 → _parse_raw_dscan()
      4. callback → session._pscan_band
  → push_loop (pscan 分支)
    → _push_frame(session, band)
      → build_pscan_fscan_frame(rmcp_levels, pl, stc)
        → RMCP 4001点 [2280:3721] = 1441点 (137-173MHz)
    → streamsrc_client.sendall(2944B)
```

### 4.3 MScan (通用 RMCP 路径)

```
SOAP B_MScan → _handle_mscan()
  → RMCP send_request(func_id=14)
  → _start_rmcp_receive()  # 与 FScan 共用
    → get_callback_datas() → n_bd_type=14 (SGLFREQ)
    → session._latest_band_info = band_info
  → push_loop (mscan 分支)
    → _push_frame(session, None)
      → session._latest_band_info → levels[0]
      → build_mscan_frame(dbm_level, frequency)
    → streamsrc_client.sendall(45B)
```

### 4.4 SglFreqMeas (通用 RMCP 路径)

```
SOAP B_SglFreqMeas → _handle_sglfreqmeas()
  → RMCP send_request(func_id=11)
  → _start_rmcp_receive()  # 与 FScan 共用
    → get_callback_datas() → n_bd_type=11 (IFANALYSIS)
    → session._latest_band_info = band_info
  → push_loop (sglfreq 分支)
    → _push_frame(session, None)
      → session._latest_band_info → levels (int16 数组)
      → 三帧循环:
        帧0: build_pscan_spectrum_frame()  (3256B, DT=7)
        帧1: build_pscan_level_frame()     (40B, DT=101)
        帧2: build_pscan_itu_frame()       (36B, DT=8)
    → streamsrc_client.sendall()
```

---

## 5. RMCP 接收路径对比

| 模式        | 接收函数                   | 帧格式                     | 数据来源                        |
| --------- | ---------------------- | ----------------------- | --------------------------- |
| FScan     | `get_callback_datas()` | 标准 RMCP 帧 (18头+payload) | `band_collector`            |
| MScan     | `get_callback_datas()` | 标准 RMCP 帧               | `session._latest_band_info` |
| SglFreq   | `get_callback_datas()` | 标准 RMCP 帧               | `session._latest_band_info` |
| **PScan** | `receive_pscan_raw()`  | 控制帧 + raw DSCAN 流       | `session._pscan_band`       |

---

## 6. Session 状态机

```
pending ──── streamsrc 连接 ────→ active
   │                                  │
   │ 30s超时                     B_StopMeas / TCP断联 / 无数据30s
   ▼                                  ▼
 (清理)                            closing → closed
```

---

## 7. 线程模型

```
Main Thread (SOAP 接收)
    │ create_pending_session
    ▼
Accept Thread (streamsrc 连接监听)
    │ 为每个连接创建 Push Thread
    ▼
Push Thread (per session, push_loop)
    │ 每 0.2s 推送一帧
    │ 从 band_collector / _latest_band_info / _pscan_band 获取数据
    ▼
RMCP Receive Thread (per session, receive_loop / receive_pscan_raw)
    │ 阻塞接收设备数据
    │ 写入 band_collector / session._latest_band_info / session._pscan_band
```

---

## 8. 配置

**config/settings.json**:

```json
{
  "atom": { "host": "127.0.0.1", "soap_port": 8282, "streamsrc_port": 18012 },
  "device": { "host": "100.72.95.36", "port": 1449 },
  "session": { "stale_timeout": 30, "idle_timeout": 30 },
  "log": { "level": "INFO", "dir": "./logs" }
}
```

---

## 9. 日志 Tag

| Tag       | 内容             |
| --------- | -------------- |
| `ATOM`    | 主服务日志          |
| `STREAM`  | streamsrc 推送相关 |
| `SOAP`    | SOAP 处理相关      |
| `SESSION` | Session 管理相关   |
| `RMCP`    | RMCP 通信相关      |

---

## 10. 依赖关系

```
main.py
 └── atom/service.py
      ├── atom/config.py
      ├── atom/session.py (StreamSession, BandCollector)
      ├── atom/session_manager.py
      ├── atom/soap/server.py + parser.py
      ├── atom/stream/server.py + frame.py
      ├── atom/rmcp/client.py + frame.py + logger.py
      ├── atom/fscan_processor.py (SpectrumData)
      └── preset/device_preset.py
```
