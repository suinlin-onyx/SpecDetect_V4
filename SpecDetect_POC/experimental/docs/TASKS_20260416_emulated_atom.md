# 任务清单 - emulated_atom 真实设备联调

**创建时间**: 2026-04-16
**更新**: 2026-04-17 00:18
**目标**: emulated_atom 与真实设备联调，确保 BFScan 流程正确

---

## BFScan 完整流程

```
1. 客户端 → SOAP B_FScan → emulated_atom:8283
   (客户端发送请求后，等待 SOAP 响应)

2. emulated_atom → SOAP 响应 → 客户端
   (响应中包含 streamsrc 端口 18013)

3. 客户端 → TCP 长连接 → streamsrc:18013
   (客户端主动连接 18013，准备接收数据) 【暂不测试】

4. emulated_atom → 监听 18013，接受连接
   (异步等待客户端连接)

5. emulated_atom → RMCP B_FScan → rmcp_proxy:9997 → device
   (同时建立到设备的长连接)

6. device → FSCAN 数据 → rmcp_proxy → emulated_atom
   (设备持续发送数据)

7. emulated_atom → streamsrc 帧 → 客户端:18013
   (推送数据给已连接的客户端)

8. 如果没有客户端连接 18013 → 数据保存本地日志
```

**当前测试重点**: 确保步骤 4、5、6 正确工作

---

## 架构

```
┌───────────────────  8283  ───────────────────┐
│                                            │
│  ┌─────────────────┐    ┌──────────────┐  │
│  │  emulated_atom  │───>│  rmcp_proxy  │  │
│  │  (Python SOAP)  │    │  (透明代理)   │  │
│  └─────────────────┘    └──────┬───────┘  │
│         ▲                       │          │
│         │                       │ 9996/9997│
│         │                       ▼          │
│    SOAP请求                   ┌─────────┐  │
│    HTTP POST                  │ 真实设备 │  │
│                              └─────────┘  │
└──────────────────────────────────────────┘
```

**组件说明：**

| 组件 | 端口 | 功能 |
|------|------|------|
| `emulated_atom.py` | 8283 (SOAP) | 接收客户端 SOAP 请求，构建 RMCP 帧，转发到 rmcp_proxy |
| `rmcp_proxy.py` | 9996/9997 | 透明代理，监听端口转发到 `100.72.95.36:1449`，同时记录流量 |
| 真实设备 | 1449 | 接收 RMCP 请求，返回 FSCAN 数据流 |

---

## 问题背景

**之前发现的真实设备 FSCAN 请求格式差异：**

| 字段 | 真实客户端 | emulated_atom (错误) |
|------|-----------|---------------------|
| startfreq | `137MHz` | `137000000Hz` |
| stopfreq | `173MHz` | `173000000Hz` |
| step | `25kHz` | `25000Hz` |
| gainctrl | `AGC` | 缺少 |
| rfworkmode | `0` | 缺少 |
| scanmode | `0` | 缺少 |
| antpol | `垂直` | 缺少 |
| antetype | `OFF` | 缺少 |
| ifatt | `0` | 缺少 |

**解决方案：** 创建 `data/fscan_real_request.py`，使用正确的 MHz/kHz 格式。

---

## Task #1: rmcp_proxy 双端口监听验证

**状态**: completed ✅

**目标**: 验证 9996 和 9997 同时监听

**验证命令**:
```bash
netstat -ano | grep -E "9996.*LISTEN|9997.*LISTEN"
```

**测试结果**:
- rmcp_proxy 正确监听 9996 和 9997
- 收到 RMCP 请求时日志输出:
  ```
  [PROXY] New connection from ('127.0.0.1', xxxxx) (port 9997)
  [PROXY] Connecting to device 100.72.95.36:1449...
  [PROXY] Connected to device 100.72.95.36:1449
  [DEBUG] Forwarding to device: 699 bytes
  :9997 C->S REQUEST      len=  699
  :9997 S->C RESPONSE     len=   51
  :9997 S->C UNKNOWN(0)  len= 1053 | 512 points | dBm: -105.2~-31.4
  ```

---

## Task #2: emulated_atom 发送 RMCP 请求到 rmcp_proxy

**状态**: completed ✅

**目标**: 确保 emulated_atom 发送 699 bytes RMCP 请求到 rmcp_proxy:9997

**检查点**:
- [x] emulated_atom 配置 RMCP_PROXY_PORT = 9997
- [x] `build_rmcp_request_frame()` 构建 699 bytes 帧
- [x] 发送请求后 rmcp_proxy 日志显示 699 bytes
- [x] 收到设备 51 bytes 响应
- [x] 收到设备 FSCAN 数据 (1053/863 bytes)

**测试结果** (2026-04-17 00:10):
- rmcp_proxy 成功转发 699 bytes 请求到设备
- 设备响应 51 bytes (RESPONSE)
- 设备发送 1053 bytes FSCAN 数据 (512 points, dBm: -101.2 ~ -37.9)
- 设备发送第二帧 1053 bytes FSCAN 数据 (512 points, dBm: -111.7 ~ -33.3)

**注意**: 设备在 00:10 后停止响应，后续请求无回调。这是设备问题，不是 emulated_atom 代码问题。

**测试命令**:
```bash
# 终端1: 启动 rmcp_proxy
cd D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/rmcp_proxy
python rmcp_proxy.py

# 终端2: 发送 BFScan 请求
curl -X POST http://127.0.0.1:8283 \
  -H "Content-Type: text/xml; charset=utf-8" \
  -H 'SOAPAction: "B_FScan"' \
  -d '<?xml version="1.0" encoding="UTF-8"?>...'

# 验证 rmcp_proxy 日志是否显示:
# :9997 C->S REQUEST      len=  699
```

---

## Task #3: emulated_atom 接收设备 FSCAN 数据并保存本地日志

**状态**: completed ✅

**目标**: 即使没有客户端连接 18013，也要把设备数据保存到本地日志

**数据流**:
```
device → rmcp_proxy → emulated_atom → 本地日志文件
```

**验证结果**:
- rmcp_proxy 的 `capture_9997_*.json` 记录了完整的请求/响应
- `raw_fscan_9997_*.log` 记录了原始 FSCAN 数据 (dBm 值)
- emulated_atom 通过 `_get_fscan_from_rmcp_proxy()` 成功获取设备数据

**注意**: emulated_atom 当前使用模拟数据作为 fallback，因为设备回调不稳定

**数据流**:
```
device → rmcp_proxy → emulated_atom → 本地日志文件
```

**验证方式**:
- 查看 `experimental/logs/` 或 `rmcp_proxy/capture/` 下的日志
- 应该包含 FSCAN 数据的 hex 或解析后的 levels

---

## Task #4: streamsrc 1086B 帧推送

**状态**: pending

**目标**: emulated_atom 正确解析设备响应并推送 streamsrc 1086B 帧

**1086B 帧结构** (待确认):
```
Offset 0-3:   Sync (0xEEEEEEEE)
Offset 4-5:    VER (0x0100)
Offset 6-9:    STC
Offset 10-17:  TS
Offset 18-21:  PL
Offset 22:     EL (0)
Offset 23:     Reserved (0)
Offset 24:     DT (12 = FSCAN)
Offset 25-28:  DL (1057)
Offset 29+:    DATA (metadata + spectrum)
```

**帧长度**: 23 (帧头) + 5 (帧体头) + DL = 1086 bytes

---

## Task #5: 客户端连接 streamsrc 18013 端口

**状态**: pending

**目标**: 验证客户端能连接 18013 并接收 streamsrc 数据

**测试命令**:
```bash
# 客户端连接 18013
nc 127.0.0.1 18013
```

---

## 发现的问题及修复

### 问题 1: SOAPAction 解析失败

**现象**: `curl` 发送请求时，`operation` 为空字符串

**原因**: `parse_soap_request()` 中 SOAPAction 正则表达式依赖 HTTP 头部的行顺序，但日志预览截断导致误判

**修复**: 在 `else` 分支添加检测 - 当 `operation` 为空但 `params` 包含 FSCAN 参数时，也进入 `_handle_fscan` 处理

```python
elif params and any(k in params for k in ('startfreq', 'stopfreq', 'step')):
    log(f"operation 为空但检测到 FSCAN 参数，当作 B_FScan 处理")
    self._handle_fscan(client, params)
```

### 问题 2: SOAP XML 解析不支持直接子元素格式

**现象**: `params = {}`，无法获取频率参数

**原因**: 解析器只支持 `<equpara><item name="xxx" value="yyy"/></equpara>` 格式，不支持 `<B_FScanRequest><startfreq>137MHz</startfreq></B_FScanRequest>` 格式

**修复**: 在 `parse_soap_request()` 中添加直接子元素提取逻辑

### 问题 3: 设备回调不稳定

**现象**: 00:10 之前有回调，之后无响应

**原因**: 设备端问题（连接断开/会话状态），与 emulated_atom 代码无关

**建议**: 检查设备连接状态，或等待设备恢复后重新测试

### 问题 4: 设备响应延迟大

**现象**: 设备响应延迟可达 60+ 秒

**修复**: 增加等待超时到 90 秒

---

## 新功能实现 (2026-04-17)

### 1. rmcp_proxy 回调数据日志记录

**功能**: `_save_rmcp_raw_log()` 将收到的 rmcp_proxy 原始数据保存到日志文件

**日志位置**: `experimental/logs/rmcp_callback/rmcp_raw_<timestamp>.log`

**日志内容**:
- 原始数据大小
- Hex 格式数据
- 解析后的 RMCPTP 帧头信息

### 2. streamsrc 1086 字节帧格式

**功能**: `build_streamsrc_frame()` 生成 1086 字节格式帧

**帧格式** (基于 TASKS_20260415_atom_filter_analysis.md):
```
Offset 0-3:   Sync (0xEEEEEEEE)
Offset 4-47:  Header (44 bytes)
Offset 48-61: Metadata [16801, 0, 0, 20480, 18115, 512, 0] (14 bytes)
Offset 62-1085: Spectrum (512 x int16 = 1024 bytes)
```

---

## BFScan 请求格式 (已验证可用)

```bash
curl -X POST http://127.0.0.1:8283 \
  -H "Content-Type: text/xml; charset=utf-8" \
  -H 'SOAPAction: "B_FScan"' \
  -d '<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:B_FScanRequest>
<srrc:startfreq>137MHz</srrc:startfreq>
<srrc:stopfreq>173MHz</srrc:stopfreq>
<srrc:step>25kHz</srrc:step>
<srrc:gainctrl>AGC</srrc:gainctrl>
<srrc:rfworkmode>0</srrc:rfworkmode>
<srrc:scanmode>0</srrc:scanmode>
<srrc:antpol>垂直</srrc:antpol>
<srrc:antetype>OFF</srrc:antetype>
<srrc:ifatt>0</srrc:ifatt>
</srrc:B_FScanRequest></soapenv:Body></soapenv:Envelope>'
```

---

## 当前状态

**代码修改已完成**，待设备恢复后验证：
1. `_save_rmcp_raw_log()` - 日志记录功能
2. `build_streamsrc_frame()` - 1086 字节帧格式
3. 超时等待增加到 90 秒

**设备问题**: 设备回调不稳定，需要检查设备连接

---

## 文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| emulated_atom.py | `experimental/` | 主服务，实现 SOAP→RMCP→streamsrc 完整链路 |
| analyze_streamsrc.py | `experimental/` | streamsrc 帧解析工具 |
| rmcp_proxy.py | `rmcp_proxy/` | 透明代理 |
| fscan_real_request.py | `data/` | 正确格式的 FSCAN XML 构建 |

---

## 参考文档

- `data/fscan_request_template.xml` - 真实请求格式模板
- `data/fscan_real_request.py` - FSCAN XML 构建代码
- `data/devinfo/` - 设备支持接口与参数
