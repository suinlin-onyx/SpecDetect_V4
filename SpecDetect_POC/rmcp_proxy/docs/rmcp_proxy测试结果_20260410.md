# RMCP Proxy 测试流程

> 创建日期：2026-04-10
> 更新日期：2026-04-10

---

## 架构说明

```
请求侧 → SOAP → Real Atom → rmcp_proxy:9996 → 远程Device:9997
```

| 组件 | 地址 | 说明 |
|------|------|------|
| rmcp_proxy | 127.0.0.1:9996 | TCP透明代理 |
| Real Device | 100.89.170.72:9997 | 远端设备 |
| Real Atom | 本机8282或远程113.90.244.216:8282 | SOAP服务 |

---

## 帧头结构 (18字节)

| 字段 | 字节 | 字节序 | 说明 |
|------|------|--------|------|
| dwLength | 4 | 小端 | 帧长度 |
| tmStamp | 8 | 小端 | FILETIME时间戳 |
| nVersion | 2 | **大端** | =7 |
| nMsgType | 1 | 小端 | 90=请求, 6=响应, 0=数据 |
| nFlags | 1 | 小端 | 0x01请求/0x00响应 |
| nCheckSum | 2 | 小端 | 校验和 |

---

## 消息类型

| 值 | 类型 | 说明 |
|----|------|------|
| 90 | REQUEST | 设备控制请求 |
| 6 | RESPONSE | 响应消息 |
| 0 | DATA | 数据帧(实际观察到) |

---

## 测试步骤

### 步骤1: 启动 rmcp_proxy

```bash
python D:\arvin\claude_workspace\rmcp_proxy\rmcp_proxy.py
```

预期输出：
```
[PROXY] Connected to device 100.89.170.72:9997
[PROXY] New connection from 127.0.0.1:xxxxx
```

### 步骤2: 启动 Real Atom

```bash
D:\arvin\claude_workspace\RXAtomSvcV3\AtomSvcV3.exe
```

### 步骤3: 配置设备连接

确保设备配置文件 `D:\arvin\claude_workspace\RXAtomSvcV3\config\devinfo\53090001140012_51cd8dfe-e543-40c9-bdc3-a292766fee7f.xml` 中：

```xml
<station ... serverip="127.0.0.1" serverport="9996" ... />
```

### 步骤4: 发送测试请求

使用 `test_interface_sequence.py` 或直接调用接口：

```bash
# 单频测量测试
python D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\test_interface_sequence.py
```

---

## 预期日志输出

### 请求日志 (C->S)
```
[时间] C->S REQUEST     len=703  from=127.0.0.1:xxxxx -> REQUEST
XML Content:
<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" ...
```

### 响应日志 (S->C)
```
[时间] S->C RESPONSE    len=51   from=100.89.170.72:9997
[时间] S->C DATA        len=863  from=100.89.170.72:9997
[时间] S->C DATA        len=1053 from=100.89.170.72:9997
```

---

## 输出文件

| 格式 | 用途 |
|------|------|
| `.raw` | 原始二进制，Wireshark打开 |
| `.json` | 结构化数据 |
| `.log` | 人类可读日志 |

保存位置：`D:/arvin/claude_workspace/rmcp_proxy/capture/`

---

## 配置文件

**rmcp_proxy/config.py**:
```python
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9996
DEVICE_HOST = "100.89.170.72"
DEVICE_PORT = 9997
LOG_DIR = "D:/arvin/claude_workspace/rmcp_proxy/capture"
```

---

## 一键启动脚本

**start_atom.bat**:
```batch
@echo off
chcp 65001 >nul
start "RMCP_Proxy" cmd /k "cd /d D:\arvin\claude_workspace\rmcp_proxy && python rmcp_proxy.py"
timeout /t 3 /nobreak >nul
start "" "D:\arvin\claude_workspace\RXAtomSvcV3\AtomSvcV3.exe"
timeout /t 3 /nobreak >nul
start "" "D:\arvin\claude_workspace\RXAtomSvcV3\RXAtomTestTool3.exe"
pause
```

---

## 接口测试脚本

**位置**: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\test_interface_sequence.py`

**ATOM_URL**: `http://113.90.244.216:8282/` (远程) 或 `http://127.0.0.1:8282/` (本地)

**测试接口**:
- B_SglFreqMeas: 单频测量
- B_SglFreqDF: 单频测向
- B_FScan: 频段扫描
- B_FScanDF: 频段扫描测向
- B_PScan: 频谱扫描
- B_WBDF: 宽带测向
- B_MScan: 多信道扫描
- B_MScanDF: 多信道扫描测向

---

## 注意事项

1. **nVersion是大端序**，其他字段是小端序
2. **XML编码是GB2312**，不是UTF-8
3. **FILETIME时间戳**：有效范围1601-01-01到现在
4. **数据帧nMsgType=0**：文档说29或95，实际观察到0

---

## 测试结果 (2026-04-10 23:05)

### 测试接口
| 接口 | 状态 | taskid |
|------|------|--------|
| B_MScan | ✅ 成功 | 87D36EE8-34EE-11F1-8002-00D8612F75B8 |
| B_MScanDF | ✅ 成功 | 99D66AC8-34EE-11F1-8000-00D8612F75B8 |
| B_FScanDF | ✅ 成功 | ABD4C260-34EE-11F1-8000-00D8612F75B8 |

### 捕获数据
- 捕获文件: `capture_20260410_230353.*`
- 请求帧: 607/754/758 字节, nMsgType=90 (REQUEST)
- 响应帧: 31/61 字节, nMsgType=6 (RESPONSE)
- 数据帧: 31/62/93 字节, nMsgType=0 (DATA)

### 流程验证
```
请求侧 → SOAP → Real Atom(8282) → rmcp_proxy(9996) → 远程Device(100.89.170.72:9997)
```
**全链路通联 ✅**

---

## 完整测试结果 (2026-04-10 23:22)

### 测试接口（按文档标准顺序）
| # | 接口 | 状态 | taskid | funcid |
|---|------|------|--------|--------|
| 1 | B_QueryDeviceInfo | ✅ | - | - |
| 2 | B_QueryFaciDevStat | ✅ | - | - |
| 3 | B_FScan | ✅ | A148FCCE-34F0-11F1-8000-00D8612F75B8 | 15 |
| 4 | B_FScanDF | ✅ | B3442E80-34F0-11F1-8000-00D8612F75B8 | 16? |
| 5 | B_MScan | ✅ | C53DBF66-34F0-11F1-8000-00D8612F75B8 | 14 |
| 6 | B_MScanDF | ✅ | D73F3D20-34F0-11F1-8000-00D8612F75B8 | 32 |
| 7 | B_PScan | ✅ | E939C4D2-34F0-11F1-8000-00D8612F75B8 | 21 |
| 8 | B_SglFreqDF | ✅ | FB357BCC-34F0-11F1-8000-00D8612F75B8 | 11 |
| 9 | B_SglFreqMeas | ✅ | 0D32F57A-34F1-11F1-8000-00D8612F75B8 | 13 |
| 10 | B_WBDF | ✅ | 1F2DD9D4-34F1-11F1-8000-00D8612F75B8 | 25 |

### 捕获统计
- 捕获文件: `capture_20260410_231857.*`
- nMsgType=90 (REQUEST): 160 帧
- nMsgType=6 (RESPONSE): 8 帧
- nMsgType=0 (DATA): 4 帧

### funcid 映射（官方配置）
来源：`RXAtomSvcV3\config\devinfo\53090001140012_51cd8dfe-e543-40c9-bdc3-a292766fee7f.xml`

| funcid | 接口 | 关键参数 |
|--------|------|----------|
| 11 | B_SglFreqMeas | frequency, ifbw, demodmode |
| 13 | B_SglFreqDF | frequency, dfmode, dftype |
| 14 | B_MScan | frequency, ifbw |
| 15 | B_FScan | startfreq, stopfreq, step, scanmode |
| 16 | B_PScan | startfreq, stopfreq, step, keepmode |
| 21 | B_FScanDF | startfreq, stopfreq, step |
| 25 | B_WBDF | frequency, ifbw |
| 32 | B_MScanDF | frequency, dfmode, ifbw |

### 完整测试结果验证
| # | 接口 | funcid | 状态 |
|---|------|--------|------|
| 1 | B_QueryDeviceInfo | - | ✅ |
| 2 | B_QueryFaciDevStat | - | ✅ |
| 3 | B_FScan | 15 | ✅ |
| 4 | B_FScanDF | 21 | ✅ |
| 5 | B_MScan | 14 | ✅ |
| 6 | B_MScanDF | 32 | ✅ |
| 7 | B_PScan | 16 | ✅ |
| 8 | B_SglFreqDF | 13 | ✅ |
| 9 | B_SglFreqMeas | 11 | ✅ |
| 10 | B_WBDF | 25 | ✅ |

**全部 10 个接口测试通过 ✅**

---

## SOAP vs RMCPTP 参数对比验证

| 接口 | funcid | SOAP 参数 | RMCPTP 参数 | 匹配 |
|------|--------|-----------|-------------|------|
| B_FScan | 15 | startfreq=137000000, stopfreq=173000000, step=25000, gain=AGC, scanmode=0 | startfreq=137MHz, stopfreq=173MHz, step=25kHz, gainctrl=AGC, scanmode=0 | ✅ |
| B_PScan | 16 | startfreq=137000000, stopfreq=173000000, step=25000, gain=AGC, keepmode=0 | startfreq=137MHz, stopfreq=173MHz, step=25kHz, gainctrl=AGC, keepmode=0 | ✅ |
| B_MScan | 14 | frequency=100000000, ifbw=40000000, gain=AGC | frequency=100MHz, ifbw=40000kHz, gainctrl=AGC | ✅ |
| B_MScanDF | 32 | frequency=100000000, dfmode=1, ifbw=40000000, gain=AGC | frequency=100MHz, dfmode=1, ifbw=40000kHz, gainctrl=AGC | ✅ |
| B_FScanDF | 21 | startfreq=137000000, stopfreq=173000000, step=25000, gain=AGC | startfreq=137MHz, stopfreq=173MHz, step=25kHz, gainctrl=AGC | ✅ |
| B_SglFreqDF | 13 | frequency=100000000, dfmode=1, ifbw=40000000, gain=AGC | frequency=100MHz, dfmode=1, ifbw=40000kHz, gainctrl=AGC | ✅ |
| B_SglFreqMeas | 11 | frequency=100000000, ifbw=40000000, gain=AGC | frequency=100MHz, ifbw=40000kHz, gainctrl=AGC | ✅ |
| B_WBDF | 25 | frequency=100000000, ifbw=40000000, gain=AGC | frequency=100MHz, ifbw=40000kHz, gainctrl=AGC | ✅ |

### 差异说明
- **单位差异**：SOAP 用 Hz，RMCPTP 用 MHz/kHz（实际值相等，如 137000000 Hz = 137 MHz）
- **参数名差异**：SOAP 用 `gain`，RMCPTP 用 `gainctrl`（Real Atom 内部转换）

### 结论
**测试数据与开发文档完全匹配 ✅**

---

## 待实现功能

### 1. Mock Atom 监听 streamsrc 功能
**问题**：Real Atom streamsrc (18012) 是 TCP 服务器，但 Mock Atom 没有实现监听功能
**状态**：待实现
**优先级**：中

详见：`D:\arvin\claude_workspace\SpecDetect_V4\docs\待实现功能_20260410.md`
