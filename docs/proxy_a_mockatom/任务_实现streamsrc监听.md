# 任务：Mock Atom streamsrc 监听实现

> 创建日期：2026-04-11
> 任务来源：根据 Real Atom 日志分析，streamsrc 是被动监听端口，接收设备随机端口的连接
> 状态：已完成

---

## 背景

根据 Real Atom 日志分析：

```
[2026-04-11 12:37:12.267864(45844)]127.0.0.1:18012 接受 连接 127.0.0.1:13437 连接成功
```

**发现**：
1. streamsrc 监听 18012 端口
2. 设备主动连接 streamsrc，使用随机源端口（如 13437）
3. streamsrc 是**被动监听**端口，接收来自设备的消息

---

## 任务目标

1. 在 Mock Atom 中实现 streamsrc 监听功能
2. 分析接收到的消息内容
3. 验证 streamsrc 消息格式

---

## streamsrc 机制分析

### Real Atom streamsrc 行为

| 特性 | 说明 |
|------|------|
| 监听地址 | 127.0.0.1 (可配置) |
| 监听端口 | 18012 (可配置) |
| 连接模式 | **被动监听**，设备主动连接 |
| 源端口 | 设备随机分配（如 13437） |
| 用途 | 设备数据回调通道 |

### streamsrc vs RMCPTP 区别

| 通道 | 角色 | 连接模式 | 说明 |
|------|------|----------|------|
| streamsrc | Atom是服务端，设备是客户端 | **被动监听** | 设备主动连接，发送数据 |
| RMCPTP | Atom是客户端，设备是服务端 | **主动连接** | Atom连接设备发送命令 |

---

## 实现步骤

### 步骤1: 创建 streamsrc 监听模块

**文件**: `mock_atom_streamsrc.py` 或集成到 `main_atom.py`

**功能**:
```python
class StreamSrcServer:
    """streamsrc TCP 服务器"""
    
    def __init__(self, host='127.0.0.1', port=18012):
        self.host = host
        self.port = port
        self.server_socket = None
        
    def start(self):
        """启动 streamsrc 监听"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
    def accept_connection(self):
        """接受设备连接"""
        client_socket, client_addr = self.server_socket.accept()
        # client_addr[1] 是随机源端口
        return client_socket, client_addr
```

### 步骤2: 配置 streamsrc 参数

**配置项** (在 settings.py 中添加):
```python
SERVICES = {
    'atom': {
        # ... existing config ...
        'streamsrc_host': '127.0.0.1',  # streamsrc 监听地址
        'streamsrc_port': 18012,           # streamsrc 监听端口
    }
}
```

### 步骤3: 分析接收到的消息

**接收消息**:
```python
def handle_client(self, client_socket, client_addr):
    """处理设备消息"""
    while True:
        data = client_socket.recv(8192)
        if not data:
            break
        # 记录原始数据
        log(f"收到设备消息 from {client_addr}: {len(data)} bytes")
        # 解析 RMCPTP 帧头
        self.parse_rmcp_frame(data)
```

**分析内容**:
- 帧头结构 (18字节): dwLength, tmStamp, nVersion, nMsgType, nFlags, nCheckSum
- 消息类型: REQUEST (90), RESPONSE (6), DATA (0)
- 业务数据类型: SGLFREQ, FSCAN, etc.

---

## 待分析问题

| # | 问题 | 说明 |
|---|------|------|
| 1 | streamsrc 消息类型 | 接收到的消息是什么类型？ |
| 2 | streamsrc 帧格式 | 是否与 RMCPTP 帧格式相同？ |
| 3 | streamsrc 消息内容 | 设备发送的具体数据是什么？ |

---

## 验证方法

### 方法1: Wireshark 抓包

在 streamsrc 端口 (18012) 抓包，观察设备发送的数据。

### 方法2: 日志记录

在 Mock Atom 中记录接收到的原始数据和解析结果。

### 方法3: 对比 Real Atom 日志

与 Real Atom 日志对比，确认消息格式是否一致。

---

## 参考

| 文档 | 路径 | 说明 |
|------|------|------|
| Real Atom 日志 | `D:\arvin\claude_workspace\RXAtomSvcV3\log\` | 包含 streamsrc 连接日志 |
| streamsrc 任务 | `proxy_b_realatom/任务_streamsrc配置同步机制分析.md` | streamsrc 配置分析 |

---

## 下一步

- [x] 创建 `StreamSrcServer` 类
- [x] 在 `main_atom.py` 中集成 streamsrc 监听
- [x] 记录接收到的原始数据
- [x] 解析并分析消息内容
- [x] 对比 RMCPTP 帧格式

---

## 实现总结

### 已完成功能

1. **StreamSrcServer 类** (`main_atom.py` 第 45-240 行)
   - `__init__(host, port)` - 初始化服务器
   - `start()` - 启动监听 (绑定 127.0.0.1:18012)
   - `stop()` - 停止监听
   - `_accept_loop()` - 接受设备连接
   - `_handle_client()` - 处理设备消息
   - `_parse_and_log_frames()` - 解析 RMCPTP 帧头

2. **配置项** (`config/settings.py`)
   ```python
   'streamsrc_host': '127.0.0.1',
   'streamsrc_port': 18012
   ```

3. **控制接口**
   - `GET /streamsrc/status` - 获取 streamsrc 状态
   - `POST /streamsrc/start` - 启动 streamsrc 监听
   - `POST /streamsrc/stop` - 停止 streamsrc 监听

4. **自动启动**
   - `main()` 函数启动时自动调用 `streamsrc.start()`

### 启动方式

```bash
cd D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC
python main_atom.py
```

### 测试验证

1. 启动 Mock Atom
2. 检查 streamsrc 状态: `curl http://127.0.0.1:9090/streamsrc/status`
3. 设备连接到 127.0.0.1:18012
4. 观察日志中的 streamsrc 消息

---

**最后更新**: 2026-04-11
