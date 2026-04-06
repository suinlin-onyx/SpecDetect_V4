# 问题日志

> 创建日期：2026-04-06
> 用途：记录联调过程中发现的问题及解决方案

---

## 问题模板

```
## ISSUE-XXX: [问题简述]

**发现日期**: YYYY-MM-DD
**状态**: Open / In Progress / Resolved / Closed
**优先级**: P0 / P1 / P2

### 问题描述
[详细描述]

### 复现步骤
1.
2.
3.

### 预期行为
[期望的结果]

### 实际行为
[实际发生的情况]

### 根因分析
[分析结果]

### 解决方案
[采用的修复方法]

### 相关文档/提交
- 提交: `hash`
- 相关文档: [链接]
```

---

## 问题列表

<!-- 使用上方模板记录问题 -->

## ISSUE-001: routes.py ATOM_BASE_URL 配置不生效

**发现日期**: 2026-04-06
**状态**: Resolved
**优先级**: P1

### 问题描述
main_proxy_b.py 导入了 `config.settings_proxy_b` 中的 SERVICES（配置为 Real Atom: 8282），
但 `app/proxy_service/routes.py` 模块级导入 `from config.settings import SERVICES`，
导致 ATOM_BASE_URL 在模块导入时就被计算为 127.0.0.1:9090（Mock Atom）。

### 解决方案
在 routes.py 中添加 `get_atom_base_url()` 函数，通过 `PROXY_MODE` 环境变量动态检测运行模式。
main_proxy_b.py 在导入 routes 前设置 `os.environ['PROXY_MODE'] = 'B'`。

## ISSUE-002: Real Atom 接口格式不兼容

**发现日期**: 2026-04-06
**状态**: Resolved (Partial)
**优先级**: P0
**更新日期**: 2026-04-06

### 问题描述
Real Atom (AtomSvcV3.exe at 8282) 对请求返回空响应，日志显示 "Unknown Web service interface"。

### 根因分析

#### 1. 接口路径问题
**确认结论**: Real Atom 使用 `/B_XXX` 格式端点，而非 `/services`

**证据来源**:
- WSDL 文件位置: `D:\arvin\vhf_monitoring_ws\RXAtomSvcV3\wsdl\8282\`
  - `B_SglFreqMeas.wsdl`, `B_FScan.wsdl`, `B_StopMeas.wsdl` 等
  - **注意**: 不存在 `B_SelfTest.wsdl`
- Real Atom 日志 (Atomsvc-20260406-194340783.log):
  ```
  wsdl文件D:\arvin\vhf_monitoring_ws\RXAtomSvcV3\wsdl\boer\B_SelfTest.wsdl不存在
  ```
- flask_proxy.py (VHFMonitor_Python) 确认路由方式:
  ```python
  atom_url = f'http://{ATOMSVC_HOST}:{ATOMSVC_PORT}/{service_name}'
  # 例如: http://127.0.0.1:8282/B_SglFreqMeas
  ```

#### 2. 有效端点列表 (来自 WSDL 文件)
| 端点 | 功能 | WSDL 存在 |
|------|------|-----------|
| `/B_SglFreqMeas` | 单频测量 | ✅ |
| `/B_FScan` | 频段扫描 | ✅ |
| `/B_PScan` | 并行扫描 | ✅ |
| `/B_MScan` | 调制扫描 | ✅ |
| `/B_StopMeas` | 停止测量 | ✅ |
| `/B_QueryDeviceInfo` | 设备信息查询 | ✅ |
| `/B_QueryFaciDevStat` | 设备状态查询 | ✅ |
| `/B_SelfTest` | 设备自检 | ❌ **不存在** |

#### 3. 设备连接依赖
Real Atom 需要与物理设备建立连接才能正常响应业务请求。

**日志证据**:
```
ping...m_bDevSvrRun=0...172.18.114.x 9999
```
- `m_bDevSvrRun=0` 表示设备服务器未运行
- Real Atom 尝试连接多个设备 IP (172.18.114.x) 的 9999 端口
- 当前测试环境无物理设备连接

### 正确请求格式 (已确认)
```xml
POST /B_SglFreqMeas HTTP/1.1
Content-Type: text/xml; charset=utf-8

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body>
  <srrc:requestbody>
    <srrc:userid>RX_admin</srrc:userid>
    <srrc:mfid>53090001140007</srrc:mfid>
    <srrc:equid>8f1b953d-d618-4d4f-a106-81c47183af3c</srrc:equid>
    <srrc:equpara></srrc:equpara>
    <srrc:resulttype></srrc:resulttype>
    <srrc:outputchannel>
      <srrc:mode>source</srrc:mode>
      <srrc:datachannel>stream</srrc:datachannel>
    </srrc:outputchannel>
  </srrc:requestbody>
</soapenv:Body>
</soapenv:Envelope>
```

### 阻塞原因
- Real Atom 需要与物理设备建立连接才能响应业务请求
- 当前测试环境 (8282端口的 AtomSvcV3) 无法正常响应，因为没有设备连接
- **B_SelfTest 端点不存在**: 已从 OPERATION_TO_REAL_ATOM 映射表中移除

### 相关文档/提交
- 相关代码: `app/proxy_service/routes.py`
- 配置文件: `config/settings_proxy_b.py`
- Real Atom 位置: `D:\arvin\claude_workspace\RXAtomSvcV3\`
- Real Atom WSDL: `D:\arvin\claude_workspace\RXAtomSvcV3\wsdl\8282\`
- Real Atom 日志: `D:\arvin\claude_workspace\RXAtomSvcV3\log\`
- 参考实现: `D:\arvin\vhf_monitoring_ws\VHFMonitor_Python\services\flask_proxy.py`

### 修改记录
| 日期 | 修改内容 | 提交 |
|------|---------|------|
| 2026-04-06 | 从 OPERATION_TO_REAL_ATOM 移除 B_SelfTest（不存在于 WSDL） | - |
| 2026-04-06 | 添加注释说明有效端点来源 | - |


---

## 已解决问题

| ISSUE | 问题 | 解决方案 | 关闭日期 |
|-------|------|----------|----------|
| - | - | - | - |

---

**最后更新**: 2026-04-06
