# 修改日志

**日期**: 2026-04-05
**项目**: SpecDetect_V4 频谱探测系统
**模块**: dashboard.html (前端) / main_atom.py (后端)

---

## 变更摘要

按照文档规范修复设备连接验证逻辑，确保业务请求必须在设备已连接的情况下才能发送。

**问题**: 未选择设备或未连接设备时，点击发送请求仍能成功执行，违反文档规范。

**修复**:
- 前端增加设备选择和连接状态检查
- 后端业务接口增加连接状态校验
- 移除错误的自动连接逻辑

---

## 详细变更

### 1. 前端 (dashboard.html)

#### 1.1 新增验证逻辑 - `sendRequest()` 函数

**位置**: 第946行附近

**变更前**:
```javascript
async function sendRequest() {
    const type = document.getElementById('task-type').value;
    // ... 直接发送请求
    if (!tcpConnected) {
        await connectDevice();  // 错误的自动连接
    }
    // ...
}
```

**变更后**:
```javascript
async function sendRequest() {
    const preset = document.getElementById('device-preset').value;
    const type = document.getElementById('task-type').value;
    // ...

    // ========== 前端验证：按文档规范 ==========
    // 1. 检查设备是否已选择
    if (!preset) {
        addLog('error', 'Client', '请先选择设备预设');
        document.getElementById('response-result').textContent = '错误: 请先选择设备预设';
        return;
    }

    // 2. 检查设备是否已连接（必须在发起业务请求之前手动连接）
    if (!tcpConnected) {
        addLog('error', 'Client', '设备未连接，请先点击"连接设备"按钮');
        document.getElementById('response-result').textContent = '错误: 设备未连接，请先连接设备';
        return;
    }
    // ========== 验证结束 ==========

    // 直接发送请求（已在上方验证设备连接状态）
    // ...
}
```

#### 1.2 修复状态刷新逻辑 - `refreshStatus()` 函数

**位置**: 第789行附近

**变更前**:
```javascript
// 虚拟设备状态（通过TCP连接判断）
document.getElementById('status-mock').className = tcpConnected ? 'status-dot running' : 'status-dot unknown';
```

**变更后**:
```javascript
// 检测原子服务
try {
    let resp = await fetch(`${ATOM_URL}/health`);
    if (resp.ok) {
        let data = await resp.json();
        // ...
        // 获取设备连接状态
        let devResp = await fetch(`${ATOM_URL}/device/status`);
        if (devResp.ok) {
            let devData = await devResp.json();
            tcpConnected = devData.connected;
        }
    }
} catch { ... }

// 虚拟设备状态（通过后端设备状态判断）
document.getElementById('status-mock').className = tcpConnected ? 'status-dot running' : 'status-dot unknown';
```

---

### 2. 后端 (main_atom.py)

#### 2.1 新增全局连接状态管理

**位置**: 第41-44行

**变更前**:
```python
# 全局设备客户端
_device_client: DeviceClient = None
# ...
_global_loop: asyncio.AbstractEventLoop = None
_global_loop_lock: asyncio.Lock = None
```

**变更后**:
```python
# 全局设备客户端
_device_client: DeviceClient = None
# ...

# 全局连接状态管理
_device_connected: bool = False
_global_loop: asyncio.AbstractEventLoop = None
_global_loop_lock: asyncio.Lock = None
```

#### 2.2 修改设备连接接口

**位置**: 第97-128行

**变更前**:
```python
@app.route('/device/connect', methods=['POST'])
def connect_device():
    try:
        client = get_device_client()
        result = run_async(client.connect())
        return jsonify({'success': True, 'message': '设备连接成功'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/device/disconnect', methods=['POST'])
def disconnect_device():
    try:
        client = get_device_client()
        run_async(client.disconnect())
        return jsonify({'success': True, 'message': '设备断开成功'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
```

**变更后**:
```python
@app.route('/device/connect', methods=['POST'])
def connect_device():
    global _device_client, _device_connected
    try:
        client = get_device_client()
        run_async(client.connect())
        _device_client = client  # 保存全局客户端引用
        _device_connected = True
        logger.info("设备连接成功")
        return jsonify({'success': True, 'message': '设备连接成功'}), 200
    except Exception as e:
        logger.error(f"设备连接失败: {e}")
        _device_connected = False
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/device/disconnect', methods=['POST'])
def disconnect_device():
    global _device_client, _device_connected
    try:
        if _device_client:
            run_async(_device_client.disconnect())
            _device_client = None
        _device_connected = False
        logger.info("设备断开成功")
        return jsonify({'success': True, 'message': '设备断开成功'}), 200
    except Exception as e:
        logger.error(f"设备断开失败: {e}")
        _device_connected = False
        return jsonify({'success': False, 'message': str(e)}), 500
```

#### 2.3 新增连接状态检查函数

**位置**: 第144-159行

**新增内容**:
```python
# 错误码定义 (按文档规范)
ERR_DEVICE_OFFLINE = 3001

def check_device_connected():
    """检查设备连接状态，未连接则返回错误响应"""
    if not _device_connected:
        return jsonify({
            'success': False,
            'error': 'ERR_DEVICE_OFFLINE',
            'error_code': ERR_DEVICE_OFFLINE,
            'message': '设备未连接，请先调用 /device/connect 连接设备'
        }), 503
    return None
```

#### 2.4 所有业务接口增加连接检查

以下接口在执行前增加连接状态校验：

| 接口 | 路径 | 说明 |
|------|------|------|
| `/monitor/sglfreq` | 第161行 | 单频测量 |
| `/monitor/fscan` | 第196行 | 频段扫描 |
| `/monitor/ifanalysis` | 第221行 | 中频分析 |
| `/monitor/realtime_spectrum` | 第247行 | 实时频谱 |
| `/direction/df` | 第276行 | 单频测向 |
| `/direction/ifdf` | 第321行 | 中频测向 |
| `/direction/wbfft` | 第347行 | 宽带FFT |

**变更模式**:
```python
@app.route('/monitor/sglfreq', methods=['POST'])
def start_sglfreq():
    """单频测量"""
    # ========== 后端验证：按文档规范 ==========
    # 检查设备连接状态
    error_resp = check_device_connected()
    if error_resp:
        return error_resp
    # ==========================================

    # ... 原有业务逻辑（使用全局 _device_client）
```

#### 2.5 修复健康检查和设备状态接口

**位置**: 第90-139行

- `health_check()`: 返回 `_device_connected` 状态
- `get_device_status()`: 返回 `_device_connected` 状态

---

## 修复后的流程（符合文档规范）

```
1. 用户选择设备预设
   ↓
2. 用户点击"连接设备"按钮
   → POST /device/connect
   → _device_connected = True
   ↓
3. 用户填写请求参数
   ↓
4. 用户点击"发送请求"
   ├── 前端检查：
   │   ├── 是否选择了设备？否 → 提示错误，终止
   │   └── 是否已连接？否 → 提示错误，终止
   ├── 后端检查：
   │   └── check_device_connected() 返回 3001 错误
   └── 通过后执行业务请求
```

---

## 错误码

| 错误码 | 名称 | 说明 |
|--------|------|------|
| 3001 | ERR_DEVICE_OFFLINE | 设备离线/未连接 |

---

## 文档依据

- `05_API_接口文档.md` - 错误码定义 (第517-525行)
- `01_SRS_软件需求说明书.md` - 错误码 2001 设备未连接 (第365行)
- `03_LLD_详细设计说明书.md` - 设备连接流程 (第1445-1490行)

---

## 补充变更：UI布局调整

### 变更时间
2026-04-05（下午）

### 变更内容

#### 1. 设备控制面板位置调整

**位置**: dashboard.html HTML结构

**变更前**:
```html
<!-- 设备控制面板在 header 外部，独立于 main-container -->
<div class="device-control-panel">...</div>

<div class="main-container">
    <div class="panel request-panel">请求参数</div>
    <div class="panel flow-panel">数据流追踪</div>
    <div class="panel display-panel">数据展示</div>
</div>
```

**变更后**:
```html
<div class="main-container">
    <!-- 左侧列：设备控制 + 请求参数垂直堆叠 -->
    <div class="left-column">
        <div class="panel device-control-panel">设备控制</div>
        <div class="panel request-panel">请求参数</div>
    </div>
    <div class="panel flow-panel">数据流追踪</div>
    <div class="panel display-panel">数据展示</div>
</div>
```

#### 2. 新增CSS类 `.left-column`

**位置**: 第64-70行

**新增内容**:
```css
/* 左侧列：设备控制 + 请求参数垂直堆叠 */
.left-column {
    grid-row: 1 / 3;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
```

#### 3. 设备控制面板样式调整

**变更前**:
```css
.device-control-panel {
    background: #16213e;
    border-bottom: 2px solid #0f3460;
}
.device-preset-section {
    display: flex;
    gap: 15px;
    align-items: center;
}
.device-info {
    flex: 1;
}
```

**变更后**:
```css
.device-control-panel {
    flex: 0 0 auto;
}
.device-preset-section {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    flex-wrap: wrap;
}
.form-group-row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
}
.device-info {
    width: 100%;
}
.device-info div {
    margin-bottom: 2px;
}
.device-info span {
    color: #fff;
}
```

#### 4. 设备信息显示改为3行格式

**变更前**:
```html
<div class="device-info" id="device-info">未选择设备</div>
```

**变更后**:
```html
<div class="device-info" id="device-info">
    <div>设备型号: <span id="device-model">-</span></div>
    <div>频率范围: <span id="device-freq">-</span></div>
    <div>支持功能: <span id="device-cap">-</span></div>
</div>
```

#### 5. JavaScript `loadDevicePreset()` 函数更新

**变更前**:
```javascript
function loadDevicePreset() {
    const preset = document.getElementById('device-preset').value;
    const deviceInfo = document.getElementById('device-info');

    if (!preset) {
        deviceInfo.textContent = '未选择设备';
        return;
    }
    deviceInfo.textContent = preset + ' | 频率范围: ' + config.freqRange + ' | 支持: ' + ...;
}
```

**变更后**:
```javascript
function loadDevicePreset() {
    const preset = document.getElementById('device-preset').value;
    const deviceModel = document.getElementById('device-model');
    const deviceFreq = document.getElementById('device-freq');
    const deviceCap = document.getElementById('device-cap');

    if (!preset) {
        deviceModel.textContent = '-';
        deviceFreq.textContent = '-';
        deviceCap.textContent = '-';
        return;
    }
    deviceModel.textContent = preset;
    deviceFreq.textContent = config.freqRange;
    deviceCap.textContent = config.hasDF ? '监测+测向' : '仅监测';
}
```

#### 6. 连接设备函数增加调试日志

**位置**: 第819-853行

新增响应状态检查和详细日志输出，便于诊断连接问题。

---

### 布局效果

```
┌─────────────────────────────────────────────────────────────┐
│  顶部状态栏: 代理服务 | 原子服务 | 虚拟设备 | TCP连接       │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│ │ 设备控制    │  │             │  │                     │ │
│ │ 设备型号:   │  │ 数据流追踪  │  │                     │ │
│ │ 频率范围:   │  │             │  │     数据展示        │ │
│ │ 支持功能:   │  │             │  │                     │ │
│ ├─────────────┤  │             │  │                     │ │
│ │ 请求参数    │  │             │  │                     │ │
│ │ 任务类型    │  │             │  │                     │ │
│ │ 频率/带宽   │  │             │  │                     │ │
│ │ ...        │  │             │  │                     │ │
│ └─────────────┘  └─────────────┘  └─────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 运行日志                                                │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 补充变更：协议Hook系统

### 变更时间
2026-04-05（下午）

### 变更目的
记录请求在各层之间的转换过程，便于分析协议转换链路。

### 设计原则
1. **上下文传递** - 每个请求有一个 `ProtocolContext`，贯穿所有层次
2. **各层添加自己的数据** - 不重复记录，只记录本层 transformation
3. **统一汇总输出** - 请求完成后输出完整转换链日志

### 新增文件

#### 1. `utils/protocol_hook.py` - Hook系统核心模块

**核心类**:

```python
@dataclass
class ProtocolFrame:
    """帧记录"""
    direction: str          # "send" 或 "recv"
    frame_type: str         # "RMCPTP_CMD" / "RMCPTP_RESP" / "SOAP"
    hex_data: str           # 十六进制数据
    timestamp: float

@dataclass
class ProtocolContext:
    """请求上下文，贯穿所有层次"""
    request_id: str          # UUID前8位
    timestamp: float
    layers: Dict[str, Dict[str, Any]]  # 各层数据
    frames: List[ProtocolFrame]          # 帧记录

class HookManager:
    """Hook管理器（单例）"""
    _instance = None

    def start_context() -> ProtocolContext
    def get_context() -> Optional[ProtocolContext]
    def end_context() -> Optional[ProtocolContext]
    def log_layer(layer_name: str, data: Dict[str, Any])
    def log_frame(direction: str, frame_type: str, hex_data: str)
```

**关键设计点**:
- 使用 `ContextVar` 实现协程安全的请求上下文隔离
- 单例 `HookManager` 统一管理，避免到处传递上下文
- 各层只记录自己的数据，不重复
- 统一汇总输出：请求结束时一次性输出完整链路

### 修改文件

#### 2. `app/atom_service/device_client.py`

**变更**: `receive_response()` 和 `send_and_receive()` 返回值增加原始帧数据

```python
# 变更前
async def receive_response(...) -> tuple:
    return header_info, payload

# 变更后
async def receive_response(...) -> tuple:
    return header_info, payload, raw_frame
```

#### 3. `app/atom_service/services/monitor.py`

适配新的 `send_and_receive()` 返回值（3元素tuple）

#### 4. `app/atom_service/services/direction.py`

适配新的 `send_and_receive()` 返回值（3元素tuple）

#### 5. `main_atom.py` - 所有业务接口集成Hook

**示例 - `/monitor/fscan`**:
```python
@app.route('/monitor/fscan', methods=['POST'])
def start_fscan():
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/monitor/fscan",
            "business_type": "0x15 (FSCAN)",
            "params": {"start_freq": start_freq, ...}
        })

        async def do_fscan():
            service = MonitorService(_device_client)
            return await service.start_fscan(...)

        result = run_async(do_fscan())

        # 记录响应数据
        hook.log_layer("atom", {"result_points": result.get('point_count', 0)})

        return jsonify(result), 200
    finally:
        hook.end_context()
```

### Hook日志输出示例

当调用 `/monitor/fscan` 时，日志输出：

```
[a1b2c3d4] 耗时: 45.2ms
  ├─ atom: {'interface': '/monitor/fscan', 'business_type': '0x15 (FSCAN)', 'params': {'start_freq': 100000000, 'end_freq': 200000000, 'step': 1000000}}
     ├─ SEND RMCPTP_CMD: 00 00 00 2A 00 00 00 00 00 00 00 00 07 00 15 00 ...
     └─ RECV RMCPTP_RESP: 00 00 00 50 00 00 00 00 00 00 00 00 07 00 15 00 ...
```

### 后续可扩展

Proxy层SOAP转换记录可在 `proxy_service/routes.py` 中集成：
```python
hook = HookManager.get_instance()
hook.start_context()
hook.log_layer("proxy", {"soap_action": "SglFreqMeasure", ...})
hook.log_frame("send", "SOAP", soap_xml)
# ...
hook.end_context()
```
