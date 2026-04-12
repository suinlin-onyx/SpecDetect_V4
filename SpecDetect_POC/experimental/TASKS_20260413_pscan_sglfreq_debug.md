# 任务清单 - B_PScan/B_SglFreqMeas 调试

**创建时间**: 2026-04-12
**目标**: 解决 B_PScan 和 B_SglFreqMeas 接口"设备校验失败"问题

---

## 问题现象

| 接口 | FuncID | 状态 | 错误信息 |
|------|--------|------|---------|
| B_PScan | 13 | ❌ 失败 | 设备校验失败[设备ID:00106][功能:13] |
| B_SglFreqMeas | 12 | ❌ 失败 | 设备校验失败[设备ID:00106][功能:12] |
| B_WBDF | 25 | ❌ 失败 | 设备校验失败[设备ID:00106][功能:25] |

---

## 已确认信息

### rmcp_proxy capture 分析

**B_PScan 请求参数** (失败的请求):
```xml
<item name="frequency" value="100MHz" />
<item name="dfmode" value="1" />          <!-- DF模式 - 可能问题所在 -->
<item name="ifbw" value="40000kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
<item name="dftype" value="0" />
```

**真实 TestTool B_PScan 数据** (成功):
- 频率范围: 137-173 MHz
- 信道总数: 1441
- 帧信道数量: **1441** (完整扫描，不是512)
- PL: 2920
- 电平格式: 直接 dBm 值 (如 36, 24, 23...)

### 失败原因推测

1. **dfmode 参数问题**:
   - 失败的请求包含 `dfmode=1` (Direction Finding 模式)
   - 真实 TestTool 调用 B_PScan 时没有 dfmode 参数
   - dfmode 需要 DF 硬件支持

2. **参数缺失**:
   - adjust_params_by_funcid 可能缺少 funcid=12/13 的处理
   - soap_to_rmcp_direct.py 中的参数调整逻辑可能不完整

3. **设备工作模式**:
   - 可能需要在调用 B_PScan 之前先完成特定初始化流程
   - streaming 接口需要先 stop 再 start

---

## 待验证假设

### 假设 1: dfmode 参数导致校验失败

**验证方法**: 构造不包含 dfmode 的 B_PScan 请求

**预期结果**: 如果去掉 dfmode 后成功，说明是参数问题

**测试步骤**:
1. 修改 soap_to_rmcp_direct.py 中的 adjust_params_by_funcid 函数
2. 对于 funcid=13，不添加 dfmode 参数
3. 重新测试 B_PScan

### 假设 2: 缺少 stop_streaming 调用

**验证方法**: 在测试 B_PScan 前先调用 stop_streaming

**预期结果**: 如果 stop 后成功，说明是连接状态问题

### 假设 3: 需要特定初始化流程

**验证方法**: 检查真实 TestTool 调用 B_PScan 前的设备状态

**需要对比**:
- rmcp_proxy capture 中 B_MScan 成功前的设备状态
- B_PScan 失败前的设备状态

---

## 参考数据

### 真实 TestTool B_PScan 成功数据
文件: `D:\arvin\claude_workspace\RXAtomSvcV3\2026-4-12-18-32\TestTool_接收数据,手动保存\B_PScan\B_PScan.txt`

```
LEADER:-286331154 VER:1 STC:1775989839 TS:2026-4-12 18:30:43:926 PL:2920 EL:0
扫频频谱观测数据:DT:12 DL:2915
频段序号:1  信道总数:1441
起始频率:137.0000MHz  结束频率:173.0000MHz
步长:25.0000kHz  帧信道数量:1441
电平: 36  24  23  24  30  32  34  37...
```

### rmcp_proxy capture 中的失败请求
文件: `rmcp_proxy/capture/capture_20260412_182933.json`

**B_WBDF (funcid=25) 也失败了**，说明 DF 相关接口可能都需要特殊硬件。

---

## 下一步计划

1. **首先验证假设 1**: 去掉 dfmode 参数后重新测试 B_PScan
2. **如果假设 1 无效，验证假设 2**: 确保使用 stop_streaming
3. **检查 soap_to_rmcp_direct.py**: 对比 B_MScan 和 B_PScan 的参数处理差异
4. **分析真实 TestTool 的请求参数**: 从 B_PScan.txt 找到实际发送的请求

---

## 相关文件

- `experimental/atom_data_formatter.py` - 数据格式化器
- `experimental/streaming_receiver.py` - streaming 数据接收
- `experimental/soap_to_rmcp_direct.py` - SOAP 到 RMCP 转换
- `rmcp_proxy/capture/capture_20260412_182933.json` - rmcp_proxy 抓包数据
- `D:\arvin\claude_workspace\RXAtomSvcV3\2026-4-12-18-32\TestTool_接收数据,手动保存\` - 真实 TestTool 数据

---

## 代码修改记录

### 2026-04-12 19:50

**修改**: `_filetime_to_datetime` 嵌套函数问题修复

**问题**: `_filetime_to_datetime` 被定义为嵌套函数（在 `_parse_simple_level` 内），导致类方法调用 `self._filetime_to_datetime()` 时出现属性错误

**修复**: 将类方法中的 `self._filetime_to_datetime()` 改为调用模块级 `_filetime_to_datetime()` 函数

**提交**: 8dc6ed8 fix: 修复_atom_data_to_datetime方法访问错误
