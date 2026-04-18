# emulated_atom 问题修复 - 完整说明文档

**更新日期**: 2026-04-18

---

## 一、问题清单与优先级

### 🔴 P0 - 阻断性问题（必须立即修复）

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| P0#1 | 每帧新建连接，端口9998耗尽 | WinError 10048，后续请求全部失败 | ✅ 已修复 |
| P0#2 | RMCP帧无法直接转发 | 设备返回RMCP格式，客户端期望streamsrc格式，数据无法使用 | ✅ 已修复 |

### 🟡 P1 - 严重缺陷（影响功能正确性）

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| P1#3 | `push_running` 无锁保护 | bool标志线程间不可靠，线程可能无法正常退出 | ✅ 已修复 |
| P1#4 | `sendall` 在锁内执行 | 阻塞其他线程，高并发时卡死 | ✅ 已修复 |

### 🟢 P2 - 优化建议（提升稳定性）

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| P2#6 | 无线程安全队列缓冲 | 帧无缓冲可能丢帧 | 待修复 |

---

## 二、streamsrc vs RMCP 帧格式对比

### streamsrc 帧 (FSCAN-529, 1086字节)

| 字段 | offset | 大小 | 编码 | 说明 |
|------|--------|------|------|------|
| Sync | 0-3 | 4B | - | `0xEEEEEEEE` |
| VER | 4-5 | 2B | big-endian | `0x0100` |
| STC | 6-9 | 4B | little-endian | 同步通道号 |
| TS | 10-17 | 8B | - | FILETIME时间戳 |
| Indicator | 18-19 | 2B | big-endian | `0x0026` |
| FSCAN type | 20-23 | 4B | - | `0x04000000` |
| DT | 24 | 1B | - | `0x0C` (FSCAN) |
| DL | 25-28 | 4B | little-endian | payload长度 |
| 元数据 | 29-61 | 33B | - | 私有格式 |
| 频谱数据 | 62+ | 交替模式 | - | `[dBm][0xFF][dBm][0xFF]...` |

### RMCP/RMCPTP 帧

| 字段 | offset | 大小 | 编码 | 说明 |
|------|--------|------|------|------|
| dwLength | 0-3 | 4B | little-endian | 帧长度 |
| tmStamp | 4-11 | 8B | - | FILETIME |
| nVersion | 12-13 | 2B | big-endian | 版本号 |
| nMsgType | 14 | 1B | - | 消息类型 |
| nFlags | 15 | 1B | - | 标志 |
| nCheckSum | 16-17 | 2B | - | 校验和 |
| Payload | 18+ | 变长 | - | FSCAN数据 (int16 little-endian) |

### 帧结构对比图

```
streamsrc 帧 (1086 bytes):
┌────────┬─────┬────────┬─────────┬──────┬──────────┬────────────┬─────────────┐
│ 0xEEEE │ VER │  STC   │   TS    │ Ind  │ DL(4B)   │ 元数据33B  │ 频谱[dBm]   │
│  4B    │ 2B  │   4B   │   8B    │ 2B   │          │            │ 交替0xFF    │
└────────┴─────┴────────┴─────────┴──────┴──────────┴────────────┴─────────────┘

RMCP 帧 (18 + payload bytes):
┌──────────────┬────────────┬───────┬───────┬─────────┬────────────┐
│ dwLength(4B) │ tmStamp(8B) │ nVer  │ nType │ nFlags  │  Payload   │
│              │             │  2B   │  1B   │   1B    │  变长      │
└──────────────┴─────────────┴───────┴───────┴─────────┴────────────┘
```

### 核心差异

1. **Sync标记**: streamsrc有`0xEEEEEEEE`，RMCP没有
2. **帧长度**: streamsrc固定(1086/896)，RMCP变长
3. **频谱编码**: streamsrc交替字节`[dBm][0xFF]`，RMCP直接int16 little-endian
4. **协议用途**: RMCP是设备通信协议，streamsrc是客户端数据流协议

### 结论

**设备返回RMCP帧，不能直接转发给streamsrc客户端。必须：**
1. 解析RMCP帧的FSCAN payload
2. 用payload中的spectrum数据重新构建streamsrc格式帧
3. 再发送给streamsrc客户端

---

## 三、线程模型与同步问题分析

### 当前线程模型

```
┌─────────────────┐
│   Main Thread   │  SOAP 处理 (接收请求)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  streamsrc accept thread            │  等待客户端连接
│  _accept_loop                       │
└────────┬────────────────────────────┘
         │  每个session创建一个
         ▼
┌─────────────────────────────────────┐
│  Push Thread (per session)          │  每0.2s推送一帧
│  push_loop()                        │
│    └→ _get_fscan_spectrum()        │
│         └→ _get_fscan_from_device() │  ⚠️ 这里每次创建新连接!
└─────────────────────────────────────┘
```

### 当前同步机制

**仅使用 `<threading.Lock()>` 一种同步原语**

| 锁 | 保护对象 |
|----|----------|
| `SessionManager.lock` | sessions/taskid_to_session字典 |
| `StreamSession.lock` | session内部状态 |

### 同步缺陷分析

| 共享状态 | 访问方式 | 问题 |
|----------|----------|------|
| `push_running` | 直接读写，无锁 | bool标志线程间不可靠，可能死循环 |
| `fscan_params` | 直接读写，无锁 | push_loop读时main可能写 |
| `streamsrc_client` | 直接赋值(line 840)，无锁 | Main写，Push读，无同步 |
| `target_client` | attach_target有锁，但读取无锁 | line 1772读取未受保护 |

### 具体缺陷代码

```python
# Main thread (line 840)
session.streamsrc_client = client_socket  # 无锁写入

# Push thread (line 953)
session.streamsrc_client.sendall(frame)   # 无锁读取

# Main thread (line 880)
session.push_running = True

# Push thread (line 889)
while session.push_running:  # 可能永远看不到True
```

### 连接泄漏问题

```python
# push_loop 每0.2秒执行一次
while session.push_running:
    spectrum = _get_fscan_spectrum(...)
    # 内部调用
    target_client = TargetDeviceClient(...)  # 新建连接
    target_client.connect()
    # ... 接收数据 ...
    target_client.disconnect()  # 关闭

# 结果: 每秒5个连接/断开，端口快速耗尽
```

---

## 四、优化方案

### 方案与问题对应表

| 优化方案 | 解决的问题 |
|----------|------------|
| Event 替代 bool 标志 | P1#3 线程正常退出 |
| deque 线程安全队列 | P2#6 帧可缓冲不丢帧 |
| 锁与 IO 分离 | P1#4 其他线程不被阻塞 |
| 连接复用 | P0#1 端口不耗尽 |
| RMCP→streamsrc 转换 | P0#2 客户端能正确解析 |

### 方案1: Event 替代 bool 标志

```python
class StreamSession:
    def __init__(self, ...):
        self._stop_event = threading.Event()
        self.push_running = False  # 保留属性，但用Event实际控制

    def stop_push(self):
        self._stop_event.set()

    def push_loop(self):
        self.push_running = True
        while not self._stop_event.is_set():  # 线程安全等待
            ...
        self._stop_event.clear()
```

### 方案2: deque 线程安全队列

```python
from collections import deque

class StreamSession:
    def __init__(self, ...):
        self._frame_queue = deque(maxlen=100)  # 有界队列
        self._queue_lock = threading.Lock()
        self._data_event = threading.Event()

    def queue_frame(self, frame: bytes):
        with self._queue_lock:
            self._frame_queue.append(frame)
        self._data_event.set()

    def get_frame(self, timeout=1.0) -> Optional[bytes]:
        while not self._stop_event.is_set():
            with self._queue_lock:
                if self._frame_queue:
                    return self._frame_queue.popleft()
            self._data_event.wait(timeout=0.1)
        return None
```

### 方案3: 锁与 IO 分离

```python
def push_frame_to_session(self, session: StreamSession, frame: bytes):
    # 调试写入（同一线程，无需锁）
    if session.debug_file:
        with open(session.debug_file, 'ab') as f:
            f.write(frame)

    # 网络发送（sendall本身线程安全，锁外执行）
    if session.streamsrc_client:
        try:
            session.streamsrc_client.sendall(frame)
        except Exception as e:
            log(f"推送帧失败: {e}", "STREAM")
```

### 方案4: 连接复用

```python
class StreamSession:
    def __init__(self, ...):
        self._target_client = None
        self._target_lock = threading.Lock()

    def get_target_connection(self):
        """获取或创建到目标设备的连接（复用）"""
        with self._target_lock:
            if self._target_client is None or not self._is_connected(self._target_client):
                self._target_client = TargetDeviceClient(TARGET_HOST, TARGET_PORT)
                self._target_client.connect()
            return self._target_client

    def close_target_connection(self):
        with self._target_lock:
            if self._target_client:
                self._target_client.disconnect()
                self._target_client = None
```

### 优化效果对比

| 项目 | 优化前 | 优化后 |
|------|--------|--------|
| 停止标志 | 普通bool，无锁 | threading.Event |
| 数据传递 | 直接发送 | deque队列缓冲 |
| 连接管理 | 每帧新建 | 复用 |
| 锁粒度 | 锁包含sendall | 只保护共享状态 |
| 线程通信 | 轮询 | Event驱动 |

### 预期效果

- 线程正常退出，无死循环
- 无端口耗尽
- 推送帧可缓冲，不丢失
- 其他线程不被阻塞

---

## 五、任务列表 (按依赖顺序执行)

### Task #7: P0#2 - RMCP→streamsrc 格式转换
**依赖**: 无
**问题**: 设备返回RMCP帧，客户端期望streamsrc帧，格式完全不同无法直接转发
**方案**:
```
recv RMCP帧 (18字节头 + payload)
→ 解析payload提取 spectrum/counters
→ 按 counters[2] 排序合并三个频段
→ build_streamsrc_frame() 重新封装
→ 发送给 streamsrc 客户端
```
**验证**: 客户端能正确解析FSCAN数据

### Task #9: P0#1 - 连接复用
**依赖**: Task #7
**问题**: 每帧新建连接，端口9998耗尽，WinError 10048
**方案**: session层面维护_target_client，首次请求时创建，后续请求复用
**验证**: 多次FSCAN请求无端口冲突

### Task #8: P1#3 - Event 替代 bool 标志
**依赖**: Task #9
**问题**: push_running(bool)无锁保护，线程可能无法正常退出
**方案**: threading.Event替代bool，_stop_event.set()/is_set()/wait()
**验证**: B_StopMeas后线程正常退出

### Task #10: P1#4 - 锁与IO分离
**依赖**: Task #8
**问题**: sendall在锁内执行，阻塞其他线程
**方案**: 锁只保护共享状态，sendall移至锁外
**验证**: 高并发下无阻塞

---

## 六、依赖关系

```
Task#7(P0#2) → Task#9(P0#1) → Task#8(P1#3) → Task#10(P1#4)
```

**关键路径**: P0#2 和 P0#1 是递进关系 —— 修好RMCP解析后，还需解决端口冲突才能正常工作。

---

## 七、2026-04-18 已实现

### 1. 移除固定端口绑定
- **文件**: `emulated_atom.py`
- **修改**:
  - 移除 `TEST_LOCAL_PORT = 9998` 常量
  - 移除 `use_fixed_local_port` 参数
  - `TargetDeviceClient` 直接使用系统分配端口
- **原因**: Windows上SO_REUSEADDR无法立即重用TIME_WAIT状态的端口
- **效果**: 缓解端口冲突，但未根本解决（仍需连接复用）

### 2. 连接复用 (Task #9)
- **文件**: `emulated_atom.py`
- **修改**:
  - `TargetDeviceClient` 添加 `is_connected()` 方法检测连接状态
  - `_get_fscan_from_device` 优先复用 session 中的已有连接
  - 复用连接时不断开，只在新创建连接时在session结束时断开
- **逻辑**:
  ```
  1. 检查 session.target_client 是否存在且已连接
  2. 如果可用，复用该连接，标记 reuse_connection=True
  3. 如果不可用，创建新连接，存储到 session.target_client
  4. 完成后：复用则不断开，新创建则在session结束时断开
  ```
- **效果**: 避免频繁创建/关闭连接，解决端口耗尽问题

### 3. Event 替代 bool 标志 (Task #8)
- **文件**: `emulated_atom.py`
- **修改**:
  - `StreamSession` 添加 `_stop_event = threading.Event()`
  - `close_all` 中调用 `_stop_event.set()` 替代直接设置 `push_running = False`
  - `push_loop` 中使用 `while not session._stop_event.is_set()` 替代 `while session.push_running`
  - `push_loop` 中使用 `_stop_event.wait(timeout=0.2)` 实现可中断的等待
- **逻辑**:
  ```
  1. close_all 调用 _stop_event.set() 唤醒等待中的线程
  2. push_loop 通过 _stop_event.is_set() 检查停止标志
  3. _stop_event.wait(timeout=0.2) 实现定期唤醒检查
  ```
- **效果**: 线程能正确响应停止信号，正常退出

### 4. 锁与IO分离 (Task #10)
- **文件**: `emulated_atom.py`
- **修改**:
  - `push_frame_to_session` 中移除 `with self.lock:` 包裹 `sendall`
  - 锁只保护 `debug_file` 写入（同一线程，无需锁）
  - `sendall` 在锁外执行
- **逻辑**:
  ```
  1. debug_file 写入（同一线程）：无需锁
  2. socket.sendall：本身线程安全，锁外执行
  3. 其他线程调用 close_all 时不会被阻塞
  ```
- **效果**: 高并发下无阻塞，线程间互不影响

---

## 八、归档文件路径

| 文档 | 路径 |
|------|------|
| 帧格式对比 | `memory/reference_streamsrc_vs_rmcp.md` |
| 线程同步分析 | `memory/project_specdetect_sync_analysis.md` |
| 问题与优化方案 | `memory/reference_emulated_atom_issues_optimization.md` |
| 任务进度 | `memory/project_emulated_atom_tasks.md` |
| 本文档 | `experimental/TASKS_20260418_emulated_atom_待办任务.md` |
