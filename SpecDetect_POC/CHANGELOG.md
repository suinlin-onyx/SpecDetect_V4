# 变更日志

## [未发布] - 2026-04-05

### 修复的问题

#### 1. 设备连接后请求失败 (NoneType 'send' error)

**问题描述：**
点击"连接设备"成功后，发送业务请求失败，错误信息：`'NoneType' object has no attribute 'send'`

**根本原因：**
1. `run_async()` 函数在代码中有两个定义：
   - 新版：使用持久化的后台事件循环 (`SelectorEventLoop`)
   - 旧版：使用 `asyncio.run()` 每次创建新事件循环
2. 旧版定义在代码中被实际调用，导致每次请求创建新的事件循环，TCP连接被关闭
3. Windows上 `ProactorEventLoop` 与 `run_coroutine_threadsafe()` 不兼容

**解决方案：**
1. 删除重复的 `run_async()` 定义
2. 使用 `asyncio.SelectorEventLoop()` 替代默认事件循环，确保Windows兼容性
3. 修复 `future.result()` 在Python 3.13上不接受timeout参数的问题

---

#### 2. 快速连续请求导致数据混乱

**问题描述：**
快速连续点击"发送请求"时，出现错误：
- `接收响应失败: 数据长度不足: 需要18字节, 实际1字节`
- `校验和错误: 计算值=0x55b, 实际值=0x97`

**根本原因：**
多个HTTP请求共用一个TCP连接 (`_device_client`)，异步操作导致响应数据交叉污染。

**解决方案：**
改为**短连接模式** - 每次请求创建独立的TCP连接：
```python
async def do_fscan():
    client = get_device_client()  # 新建客户端
    await client.connect()
    try:
        service = MonitorService(client)
        return await service.start_fscan(...)
    finally:
        await client.disconnect()  # 断开连接
```

已修改的接口：
- `/monitor/sglfreq` - 单频测量
- `/monitor/fscan` - 频段扫描
- `/monitor/ifanalysis` - 中频分析
- `/direction/df` - 单频测向
- `/direction/ifdf` - 中频测向
- `/direction/wbfft` - 宽带FFT

---

#### 3. Hook日志覆盖问题

**问题描述：**
Hook日志中同一layer的记录被覆盖，只显示最后一次记录。

**根本原因：**
`ProtocolContext.layers` 使用字典直接赋值，而非追加：
```python
self.layers[layer_name] = data  # 覆盖模式
```

**解决方案：**
改为列表追加模式：
```python
if layer_name not in self.layers:
    self.layers[layer_name] = []
self.layers[layer_name].append(data)  # 追加模式
```

---

#### 4. Hook日志未及时写入

**问题描述：**
Hook日志在请求结束后未立即写入文件。

**解决方案：**
在 `end_context()` 中添加 `flush()` 确保日志立即写入：
```python
for handler in self._logger.handlers:
    handler.flush()
```

同时将日志级别从 `debug` 改为 `info`，确保日志输出。

---

### 其他改进

#### 5. SGLFREQ响应幅度解析错误 (1.78e+25)

**问题描述：**
单频测量返回的幅度值为异常大数 `1.78e+25`，远超正常dBm范围。

**根本原因：**
1. Mock设备帧头格式错误：`'!B H H I'` 应为 `'!B H I I'`（nFlags占2字节而非1）
2. `build_response_frame` 未将 business_type 字节计入 payload_length
3. Atom服务解析时未跳过 business_type 字节，导致偏移错误

**解决方案：**
1. 修正 MockFrameBuilder 帧头格式
2. 修正 payload_length 计算：`payload_length = len(payload) + 1`
3. 修正 MonitorService 解析：`data_offset = 1` 跳过 business_type

---

#### 6. FSCAN/IFANALYSIS响应point_count解析错误 (25600)

**问题描述：**
频段扫描和中频分析返回的 point_count 值为 25600（应为100左右）。

**根本原因：**
解析代码中 n_arrays 字段的偏移量错误：
- 错误偏移：`payload[data_offset + 4:data_offset + 8]`
- 正确偏移：`payload[data_offset + 3:data_offset + 7]`

业务数据头格式为 `nBdType(1) + nFlags(2) + nArrays(4) + nOffset(4)`，nArrays 起始于 header 内的第4字节（从0开始），即 `header[3:7]`。

**解决方案：**
修正 MonitorService 中 n_arrays 的读取偏移量。

---

#### 启动脚本改进
- `run_all.py` 启动完成后显示聚合页面链接：`http://localhost:8080/dashboard`

#### 设备能力说明
| 设备类型 | 支持的业务 |
|---------|-----------|
| MS950 | SGLFREQ, IFANALYSIS, FSCAN |
| MS845 | SGLFREQ, IFANALYSIS, FSCAN |
| MS970 | SGLFREQ, IFANALYSIS, FSCAN, DF, IFDF |
| MD1000 | 所有业务类型 |

> 注意：DF、IFDF、WBFFT等测向业务需要设备支持，MS950不支持这些业务。
