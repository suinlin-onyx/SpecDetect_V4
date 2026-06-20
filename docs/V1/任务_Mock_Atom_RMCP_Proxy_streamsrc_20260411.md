# Mock Atom → rmcp_proxy → streamsrc 实现进度

> 创建日期：2026-04-11
> 更新日期：2026-04-11

---

## 架构

```
请求侧 → SOAP → Mock Atom (8283) → rmcp_proxy (9996) → 远程Device (100.89.170.72:9997)
                                        ↑
                               streamsrc (18012)
                               设备回调通道
```

---

## 已实现功能

### 1. Mock Atom SOAP 接口 (/B_XXX)

**文件**: `main_atom_rmcp_proxy.py`

| 接口 | 端点 | 状态 |
|------|------|------|
| B_QueryDeviceInfo | /B_QueryDeviceInfo | ✅ 查询接口，直接返回 |
| B_QueryFaciDevStat | /B_QueryFaciDevStat | ✅ 查询接口，直接返回 |
| B_StopMeas | /B_StopMeas | ✅ 停止测量，直接返回 |
| B_SglFreqMeas | /B_SglFreqMeas | ⚠️ 链路通，设备超时 |
| B_SglFreqDF | /B_SglFreqDF | ⚠️ 链路通，设备超时 |
| B_FScan | /B_FScan | ⚠️ 链路通，设备超时 |
| B_FScanDF | /B_FScanDF | ⚠️ 链路通，设备超时 |
| B_MScan | /B_MScan | ⚠️ 链路通，设备超时 |
| B_MScanDF | /B_MScanDF | ⚠️ 链路通，设备超时 |
| B_PScan | /B_PScan | ⚠️ 链路通，设备超时 |
| B_WBDF | /B_WBDF | ⚠️ 链路通，设备超时 |

**说明**:
- 查询接口 (1-3) 完全正常，直接返回设备信息
- 执行接口 (4-11) Mock Atom → rmcp_proxy → Device 链路正常，rmcp_proxy 日志显示收到请求
- **设备超时原因**：远程设备 100.89.170.72:9997 未响应（网络/认证问题），非 Mock Atom 问题
- **正式设备测试成功的接口**：B_FScan, B_FScanDF, B_MScan, B_MScanDF, B_PScan, B_SglFreqDF, B_SglFreqMeas, B_WBDF

### 2. streamsrc 监听功能

**文件**: `main_atom_rmcp_proxy.py` (StreamSrcServer 类)

```python
STREAMSRC_HOST = '0.0.0.0'
STREAMSRC_PORT = 18012
```

**功能**:
- TCP Server，监听设备连接
- 接收设备数据并解析 RMCPTP 帧头
- 心跳探测机制（30秒无数据发送探测）
- 多客户端支持

**测试结果**: ✅ 设备连接成功，数据接收正常

---

## 配置

### settings_rmcp_proxy.py

```python
SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8283,  # Mock Atom SOAP 端口
    },
    'atom': {
        'device_host': '127.0.0.1',  # rmcp_proxy 地址
        'device_port': 9996,           # rmcp_proxy 端口
    }
}
```

### 启动方式

```bash
# 1. 启动 rmcp_proxy
cd D:/arvin/claude_workspace/rmcp_proxy && python rmcp_proxy.py

# 2. 启动 Mock Atom
cd D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC && python main_atom_rmcp_proxy.py

# 3. 连接设备（执行接口前必须）
curl -X POST "http://127.0.0.1:8283/device/connect" -H "Content-Type: application/json"
```

---

## 待解决问题

### 执行接口设备超时

**现象**: Mock Atom 发送请求到 rmcp_proxy，rmcp_proxy 收到并转发到远程设备 (100.89.170.72:9997)，但设备不响应

**可能原因**:
1. ~~远程设备未连接 streamsrc (18012)~~ ← **已澄清：streamsrc 是 Atom 内部接口，与设备无关**

**相关任务**: `proxy_b_realatom/任务_streamsrc配置同步机制分析.md`

---

## 下一步

1. 执行任务：**streamsrc 配置同步机制分析**
2. 确认远程设备 100.89.170.72:9997 可达性
3. 实现 Mock Device 作为 streamsrc 客户端测试
