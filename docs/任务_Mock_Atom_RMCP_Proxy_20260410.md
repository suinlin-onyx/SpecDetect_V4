# Mock Atom → rmcp_proxy 任务

> 创建日期：2026-04-10

---

## 任务目标

让 Mock Atom 转发 SOAP 请求到 rmcp_proxy：

```
请求侧 → SOAP → Mock Atom (8282) → rmcp_proxy (9996) → 远程Device
```

---

## 任务步骤

### 步骤1: 创建 settings 文件

创建 `config/settings_rmcp_proxy.py`：
```python
SERVICES['atom']['device_host'] = '127.0.0.1'
SERVICES['atom']['device_port'] = 9996  # rmcp_proxy
```

### 步骤2: 添加 /B_XXX 端点

在 `main_atom.py` 添加：
- `/B_QueryDeviceInfo`
- `/B_QueryFaciDevStat`
- `/B_StopMeas`
- `/B_SglFreqMeas`
- `/B_SglFreqDF`
- `/B_FScan`
- `/B_FScanDF`
- `/B_MScan`
- `/B_MScanDF`
- `/B_PScan`
- `/B_WBDF`

### 步骤3: 转发逻辑

每个 `/B_XXX` 端点：
1. 解析 SOAP 请求
2. 转换为 RMCPTP 帧
3. 发送到 rmcp_proxy
4. 返回响应

### 步骤4: 测试验证

1. 启动 rmcp_proxy
2. 启动 Mock Atom (使用新配置)
3. 发送测试请求
4. 验证全链路

---

## 当前 Mock Atom 架构

| 端点 | 说明 |
|------|------|
| `/services` | 通用 SOAP 端点 |
| `/monitor/sglfreq` | 单频测量（旧格式）|
| `/monitor/fscan` | 频段扫描（旧格式）|

## 目标架构

| 端点 | 说明 |
|------|------|
| `/B_XXX` | Real Atom 兼容端点 |
| `/services` | 通用 SOAP 端点 |
