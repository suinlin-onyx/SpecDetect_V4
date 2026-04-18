# SpecDetect Atom 重构设计文档

**创建日期**: 2026-04-17
**目标**: 重构 emulated_atom，对齐 Real Atom 行为，实现无缝切换
**项目路径**: `SpecDetect_UI_Atom/SpecDetect_Atom/`

---

## 1. 目标与背景

### 1.1 重构目标

**核心目标**: emulated_atom 作为 Real Atom 的替代品，让 test 客户端可以无缝切换。

```
test客户端 ←→ Real Atom Service  (生产环境)
test客户端 ←→ emulated_atom      (测试环境，两套代码完全兼容)
```

### 1.2 当前问题

当前 `emulated_atom.py` 是一个 monolithic 脚本：
- 所有逻辑混在一个文件 (~1400 行)
- 数据结构不清晰
- 难以维护和扩展
- 无法直接用于 SpecDetect_UI_Atom 项目

### 1.3 关键认知：数据转换是必要的

emulated_atom 收到设备数据后**必须解码再重新编码**，不是简单透传：

```
设备 → emulated_atom:
  RMCP帧 (int16 little-endian, dBm×10 存储)
    ↓ _parse_single_fscan_frame (解析)
  spectrum list (Python list, 512个float)
    ↓ build_streamsrc_frame (用交替字节格式重新组装)
  streamsrc帧 (交替字节 [dBm][0xFF]...)
    ↓ push_frame
test客户端
```

**原因**: RMCP 和 streamsrc 是两种完全不同的编码格式，必须相互转换。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SpecDetect_Atom                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         SOAPHandler                                   │  │
│  │   职责: 接收/解析 SOAP 请求 → 构建 RMCP 请求                          │  │
│  │   端口: 8283 (test) / 8282 (production)                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       StreamSession                                  │  │
│  │   职责: 会话生命周期管理 (taskid ↔ streamsrc_client ↔ rmcp_client)  │  │
│  │   状态: pending / active / closing                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                    │                               │                        │
│                    ▼                               ▼                        │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐     │
│  │      StreamSrcServer        │    │       RMCPClient           │     │
│  │   职责: 管理 streamsrc      │    │   职责: 发送 RMCP 请求     │     │
│  │        TCP 连接             │    │        接收响应             │     │
│  │   端口: 18013              │    │   端口: 1449               │     │
│  └──────────────────────────────┘    └──────────────────────────────┘     │
│                    │                               │                        │
│                    │                               │                        │
│                    │         ┌─────────────────────┘                        │
│                    │         │                                              │
│                    ▼         ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      FSCANProcessor                                  │  │
│  │   职责: 频谱数据编解码 (RMCP payload ↔ streamsrc frame)            │  │
│  │   方法: encode_for_rmcp(), decode_from_rmcp(),                     │  │
│  │        encode_for_streamsrc(), decode_from_streamsrc()             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │        远程设备              │
                    │      (RMCP 1449)            │
                    └───────────────────────────────┘
```

### 2.2 数据流图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              完整数据流                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  test_fscan529              SpecDetect_Atom              Device             │
│         │                        │                        │                │
│         │──── B_FScan ─────────>│                        │                │
│         │     (SOAP 8283)       │                        │                │
│         │                        │                        │                │
│         │                        │──── RMCP Request ────>│                │
│         │                        │     (TCP 1449)         │                │
│         │                        │                        │                │
│         │                        │<─── RMCP Response ─────│                │
│         │                        │     (流式多个帧)       │                │
│         │                        │        │                │                │
│         │                        │        ▼                │                │
│         │                        │  FSCANProcessor         │                │
│         │                        │    (解码 RMCP)          │                │
│         │                        │        │                │                │
│         │                        │        ▼                │                │
│         │                        │  SpectrumData           │                │
│         │                        │    (协议无关)           │                │
│         │                        │        │                │                │
│         │                        │        ▼                │                │
│         │                        │  FSCANProcessor         │                │
│         │                        │    (编码 streamsrc)     │                │
│         │                        │        │                │                │
│         │<─── streamsrc ────────│        │                │                │
│         │     (TCP 18013)       │        │                │                │
│         │                        │                        │                │
│         │──── B_StopMeas ──────>│                        │                │
│         │     (SOAP 8283)       │                        │                │
│         │                        │──── B_StopMeas ──────>│                │
│         │                        │                        │                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据结构

### 3.1 核心数据结构

```python
@dataclass
class SOAPRequest:
    """SOAP 请求"""
    action: str                           # B_FScan, B_StopMeas, B_QueryDeviceInfo
    taskid: Optional[str]                # 任务ID (B_FScan 响应返回)
    params: Dict[str, Any]               # 解析后的参数
    raw_xml: str                          # 原始 SOAP XML


@dataclass
class RMCPFrame:
    """RMCPTP 帧"""
    dw_length: int                        # 报文总长度
    tm_stamp: int                         # FILETIME 时间戳
    n_version: int                        # 版本号 (=7)
    n_msg_type: int                       # 消息类型 (90=请求, 0=数据)
    n_flags: int                          # 标志
    n_checksum: int                       # 校验和
    payload: bytes                        # 业务数据


@dataclass
class SpectrumData:
    """协议无关的频谱数据"""
    levels: List[float]                   # 512个电平值 (已转换为 dBm)
    counters: Tuple[int, int, int, int]   # 计数器 (n_arrays, ...)
    timestamp: int                        # FILETIME 时间戳
    n_arrays: int                        # 频段数


@dataclass
class StreamSrcFrame:
    """streamsrc 帧 (1086 bytes)"""
    sync: int                             # 0xEEEEEEEE
    ver: int                              # 版本号 (=256, big-endian)
    stc: int                              # 同步通道号
    ts: int                               # FILETIME 时间戳
    frame_seq: int                        # 帧序列号
    indicator: int                        # 0x26=FSCAN-529, 0x68=FSCAN-434
    metadata: List[int]                   # 7个元数据 (int16)
    levels: List[float]                   # 512个电平值 (dBm)


@dataclass
class StreamSession:
    """会话"""
    taskid: str
    state: str                            # pending / active / closing / closed
    streamsrc_client: Optional[socket]    # streamsrc TCP 客户端
    rmcp_client: Optional['RMCPClient']    # RMCP 连接
    created_at: float                     # 创建时间
    last_data_time: float                 # 最后数据时间
```

### 3.2 帧格式详情

#### RMCP FSCAN Payload (来自设备)

```
偏移 0:     nBdType = 0x0F (15 = FSCAN)
偏移 1-2:   reserved
偏移 3-10:  counters[4] (4 x int16 little-endian)
              counters[0] = nArrays (频段数)
偏移 11+:   levels (int16 little-endian, dBm×10)
```

#### streamsrc Frame (1086 bytes, 推送至客户端)

```
Offset 0-3:   Sync      = 0xEEEEEEEE (4 bytes LE)
Offset 4-5:   VER       = 0x0100 (2 bytes BE → 256)
Offset 6-9:   STC       (4 bytes LE)
Offset 10-17:  TS        = FILETIME (8 bytes LE)
Offset 18:     FrameSeq  (1 byte)
Offset 19:     Indicator = 0x26 (FSCAN-529) 或 0x68 (FSCAN-434)
Offset 20-47:  Reserved = 0x00
Offset 48-61:  Metadata[7] = 7 x int16 LE
              [16801, 0, 0, 20480, 18115, 512, 0]
Offset 62+:    Spectrum = 交替字节 [dBm_byte][0xFF]...
              共 1024 bytes = 512 points

dBm 编码:
  负值: byte = 256 + dBm (例如 -84 → 172)
  正值: byte = dBm
  Marker: 0xFF
```

---

## 4. 类设计

### 4.1 FSCANProcessor

```python
class FSCANProcessor:
    """频谱数据处理器 - 负责 RMCP ↔ streamsrc 之间的编解码"""

    def decode_from_rmcp(self, payload: bytes) -> SpectrumData:
        """从 RMCP payload 解析出 SpectrumData

        RMCP FSCAN payload 格式:
        - byte 0: nBdType (1 byte): 0x0F = 15 = FSCAN
        - bytes 1-2: reserved
        - bytes 3-10: counters (4 x int16 LE) - counters[0] = nArrays
        - bytes 11+: levels (int16 LE, dBm×10)
        """
        pass

    def encode_for_streamsrc(self, data: SpectrumData, indicator: int = 0x26) -> StreamSrcFrame:
        """将 SpectrumData 编码为 streamsrc 帧格式"""
        pass

    def decode_from_streamsrc(self, frame: bytes) -> SpectrumData:
        """从 streamsrc 帧解析出 SpectrumData

        用于 test_fscan529 等客户端解析接收到的帧
        """
        pass
```

### 4.2 SOAPHandler

```python
class SOAPHandler:
    """SOAP 协议处理器"""

    def __init__(self, port: int, session_manager: 'SessionManager'):
        self.port = port
        self.session_manager = session_manager

    def start(self):
        """启动 SOAP 服务器"""
        pass

    def _handle_request(self, client: socket, request_data: bytes):
        """处理接收到的 SOAP 请求"""
        # 1. 解析 SOAP XML
        soap_req = self._parse_soap(request_data)

        # 2. 根据 action 分发
        if soap_req.action == 'B_FScan':
            self._handle_fscan(client, soap_req)
        elif soap_req.action == 'B_StopMeas':
            self._handle_stopmeas(client, soap_req)
        elif soap_req.action == 'B_QueryDeviceInfo':
            self._handle_query_device(client, soap_req)
        else:
            self._send_error(client, f"Unknown action: {soap_req.action}")

    def _handle_fscan(self, client: socket, req: SOAPRequest):
        """处理 B_FScan 请求"""
        # 1. 生成 taskid
        taskid = f'EA-{int(time.time())}'

        # 2. 发送 SOAP 响应
        response = self._build_soap_response(taskid)
        client.sendall(response)
        client.close()

        # 3. 创建 pending session
        session = StreamSession(taskid=taskid, state='pending')
        self.session_manager.add_pending(session)

        # 4. 触发 RMCP 请求 (异步)
        self._start_fscan_task(session, req.params)
```

### 4.3 RMCPClient

```python
class RMCPClient:
    """RMCP 客户端 - 与远程设备通信"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self) -> bool:
        """连接到 RMCP 服务器"""
        pass

    def disconnect(self):
        """断开连接"""
        pass

    def send_request(self, frame: RMCPFrame) -> bool:
        """发送 RMCP 请求帧"""
        pass

    def receive_response(self, timeout: float = 90.0) -> Generator[bytes, None, None]:
        """流式接收响应 (yield 每个数据帧)"""
        pass

    def build_fscan_request(self, params: Dict) -> RMCPFrame:
        """构建 B_FScan RMCP 请求帧

        RMCP 请求帧格式:
        - dwLength: 报文长度 (little-endian uint32)
        - tmStamp: FILETIME (8 bytes)
        - nVersion: 7 (uint16)
        - nMsgType: 90 (uint8)
        - nFlags: 0x01 (uint8)
        - nCheckSum: 校验和 (uint16)
        - payload: B_FScan 业务数据
        """
        pass
```

### 4.4 StreamSrcServer

```python
class StreamSrcServer:
    """streamsrc TCP 服务器 - 推送数据到客户端"""

    def __init__(self, port: int, session_manager: 'SessionManager'):
        self.port = port
        self.session_manager = session_manager

    def start(self):
        """启动 TCP 服务器"""
        pass

    def push_frame(self, frame: bytes):
        """推送帧到所有已连接的客户端"""
        pass

    def register_client(self, client: socket, session: StreamSession):
        """注册客户端到会话"""
        pass

    def unregister_client(self, client: socket):
        """注销客户端"""
        pass
```

### 4.5 SessionManager

```python
class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.pending_sessions: Dict[str, StreamSession] = {}  # taskid → session
        self.sessions: Dict[socket, StreamSession] = {}       # socket → session
        self.lock = threading.Lock()

    def add_pending(self, session: StreamSession):
        """添加 pending session"""
        pass

    def match_client(self, client: socket) -> Optional[StreamSession]:
        """将客户端匹配到 pending session"""
        pass

    def remove_session(self, client: socket) -> Optional[StreamSession]:
        """移除会话"""
        pass

    def get_session_by_socket(self, client: socket) -> Optional[StreamSession]:
        """通过 socket 查找会话"""
        pass
```

---

## 5. 端口配置

### 5.1 端口映射

| 链路 | Test 环境 | Production 环境 | 说明 |
|------|----------|-----------------|------|
| SOAP Server | 8283 | 8282 | Atom SOAP 监听端口 |
| streamsrc | 18013 | 18012 | 推送 streaming 数据 |
| RMCP Device | 1449 | 1449 | 与远程设备通信 |

### 5.2 配置管理

```python
# config/settings.json
{
  "atom": {
    "soap_port": 8283,
    "streamsrc_port": 18013,
    "device_host": "100.72.95.36",
    "device_port": 1449
  },
  "emulated": {
    "enabled": true,
    "use_mock_data": false,
    "capture_dir": "../SpecDetect_POC/rmcp_proxy/capture"
  }
}
```

---

## 6. 实现要点

### 6.1 B_FScan 完整流程

```python
def _start_fscan_task(self, session: StreamSession, params: Dict):
    """启动 FSCAN 任务"""

    # 1. 构建 RMCP 请求
    rmcp_frame = self.rmcp_client.build_fscan_request(params)

    # 2. 发送 RMCP 请求
    self.rmcp_client.send_request(rmcp_frame)

    # 3. 流式接收响应
    for payload in self.rmcp_client.receive_response(timeout=90.0):
        # 4. 解码 RMCP payload → SpectrumData
        spectrum = self.fscan_processor.decode_from_rmcp(payload)

        if spectrum and len(spectrum.levels) >= 512:
            # 5. 编码 SpectrumData → streamsrc frame
            stream_frame = self.fscan_processor.encode_for_streamsrc(spectrum)

            # 6. 推送帧
            self.streamsrc_server.push_frame(stream_frame)

            # 7. 控制推送频率 (每秒最多5帧)
            time.sleep(0.2)
```

### 6.2 会话关联流程

```
1. B_FScan 请求到达
   → 创建 pending session (taskid=X, state=pending)
   → 等待 streamsrc 客户端连接

2. test_fscan529 连接 streamsrc 18013
   → StreamSrcServer 接受连接
   → 匹配 pending session
   → session.streamsrc_client = client
   → session.state = 'active'

3. 数据推送开始
   → RMCP 响应 → FSCANProcessor → streamsrc frame → push_frame
   → 帧发送到 session.streamsrc_client

4. B_StopMeas 请求到达
   → 查找对应 session
   → 发送 B_StopMeas 到设备
   → 清理 session
```

### 6.3 错误处理与清理

```python
def _cleanup_session(self, session: StreamSession):
    """清理会话"""
    session.state = 'closing'

    # 关闭 streamsrc 客户端
    if session.streamsrc_client:
        try:
            session.streamsrc_client.close()
        except:
            pass

    # 关闭 RMCP 连接
    if session.rmcp_client:
        session.rmcp_client.disconnect()

    session.state = 'closed'
```

---

## 7. 项目结构

```
SpecDetect_UI_Atom/
├── SpecDetect_Atom/
│   ├── __init__.py
│   ├── main.py                      # 服务入口
│   │
│   ├── config/
│   │   └── settings.json            # 配置文件
│   │
│   ├── data/                       # 数据结构
│   │   ├── __init__.py
│   │   ├── soap_request.py         # SOAPRequest
│   │   ├── rmcp_frame.py           # RMCPFrame
│   │   ├── spectrum_data.py         # SpectrumData
│   │   ├── streamsrc_frame.py      # StreamSrcFrame
│   │   └── session.py               # StreamSession
│   │
│   ├── protocol/                    # 协议处理
│   │   ├── __init__.py
│   │   ├── soap_handler.py          # SOAPHandler
│   │   ├── rmcp_client.py          # RMCPClient
│   │   └── fscan_processor.py      # FSCANProcessor
│   │
│   ├── server/                     # 服务端组件
│   │   ├── __init__.py
│   │   ├── streamsrc_server.py      # StreamSrcServer
│   │   └── session_manager.py       # SessionManager
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               # 辅助函数
│
├── config/
│   └── devinfo/                    # 设备预设 XML
│
├── docs/
│   └── REFACTORING_DESIGN.md       # 本文档
│
└── tests/
    ├── test_soap_handler.py
    ├── test_rmcp_client.py
    ├── test_fscan_processor.py
    └── test_integration.py
```

---

## 8. 与现有代码的对应关系

| 新类 | 现有代码位置 | 说明 |
|------|-------------|------|
| `FSCANProcessor` | emulated_atom.py `_parse_single_fscan_frame` + `build_streamsrc_frame` | 整合解码/编码逻辑 |
| `SOAPHandler` | emulated_atom.py `_handle_fscan` + `_handle_stopmeas` | 提取为独立类 |
| `RMCPClient` | emulated_atom.py `_get_fscan_from_rmcp_proxy` | 独立 RMCP 客户端 |
| `StreamSrcServer` | emulated_atom.py `StreamSrcServer` | 类化 |
| `SessionManager` | emulated_atom.py `SessionManager` | 类化 |
| `StreamSession` | emulated_atom.py `StreamSession` | 整合到 data/session.py |

---

## 9. 实施计划

### Phase 1: 数据结构定义
- [ ] 定义所有 dataclass
- [ ] 实现基本编解码函数

### Phase 2: 核心类实现
- [ ] FSCANProcessor (编解码核心)
- [ ] RMCPClient (设备通信)
- [ ] SOAPHandler (请求处理)

### Phase 3: 服务端组件
- [ ] SessionManager
- [ ] StreamSrcServer
- [ ] 集成测试

### Phase 4: 完整流程验证
- [ ] B_FScan 完整流程
- [ ] B_StopMeas 清理流程
- [ ] 与 Real Atom 行为对比

---

## 10. 参考文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 整体架构
- [REQUIREMENTS.md](./REQUIREMENTS.md) - 需求文档
- `../../SpecDetect_POC/experimental/emulated_atom.py` - 现有实现
- `../../SpecDetect_POC/experimental/docs/DATA_FLOW.md` - 数据流说明
- `../../SpecDetect_POC/experimental/docs/FSCAN_FRAME_STRUCTURE.md` - FSCAN 帧结构
