# 测试进度追踪

> 创建日期：2026-04-06
> 更新日期：2026-04-06
> 文档策略：临时工作目录，联调完成后合并到主文档

---

## 文档策略记录

- [x] 确认文档策略：临时目录 + 最终合并
- [ ] 联调完成后：合并到主文档
- [ ] 删除临时目录

---

## 开发阶段进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段1 | 双Proxy基础设施搭建 | ✅ 完成 |
| 阶段2 | 双通道对比工具开发 | 🔄 进行中 |
| 阶段3 | 集成测试与差异记录 | ⬜ |

### 阶段1 详细步骤

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1.1 | 分析现有 run_all.py 启动逻辑 | ✅ 完成 |
| 1.2 | 创建 config/settings_proxy_b.py | ✅ 完成 |
| 1.3 | 创建 main_proxy_b.py | ✅ 完成 |
| 1.4 | 修改 run_all.py 支持 --dual | ✅ 完成 |
| 1.5 | 验证 Proxy-A (8080) 不受影响 | ✅ 完成 |
| 1.6 | 验证 Proxy-B (8081) 独立运行 | ✅ 完成 |

### 1.5/1.6 验证结果

```
Proxy-A :8080 → Mock Atom (127.0.0.1:9090)  ✅ 正常
Proxy-B :8081 → Real Atom (127.0.0.1:8282)  ✅ 已修复
```

**修复方案**:
- routes.py 添加 `get_atom_base_url()` 函数，动态检测 `PROXY_MODE` 环境变量
- main_proxy_b.py 在导入 routes 前设置 `os.environ['PROXY_MODE'] = 'B'`
- **需要重启服务使修改生效**

### 阶段2 详细步骤

| 步骤 | 内容 | 状态 |
|------|------|------|
| 2.1 | 创建 dual_request.py | ✅ 完成 |
| 2.2 | 创建 diff_output.py | ✅ 完成 |
| 2.3 | 测试 SGLFREQ 双通道对比 | 🔄 待执行 |
| 2.4 | 测试其他业务双通道对比 | ⬜ 待执行 |

### 2.1 dual_request.py 功能

- 同时发送请求到 Proxy-A (8080) 和 Proxy-B (8081)
- 支持服务: sglfreq, ifanalysis, fscan, df, ifdf
- 并行请求，对比响应差异
- 输出格式化结果和原始响应
- 结果保存到 JSON 文件

**用法**:
```bash
python dual_request.py --service sglfreq --freq 100000000
```

### 2.2 diff_output.py 功能

- 差异分析工具，可独立使用或被 dual_request.py 调用
- 支持从 JSON 文件或直接输入响应进行分析
- 递归比较嵌套字段差异

**用法**:
```bash
python diff_output.py --file dual_request_result_xxx.json
```

### ⚠️ Real Atom 接口问题 (已调查，详见 ISSUES.md ISSUE-002)

**问题状态**: 部分解决

**确认结论**:
1. Real Atom 使用 `/B_XXX` 格式端点（如 `/B_SglFreqMeas`），不是 `/services`
2. Real Atom 有效端点: B_SglFreqMeas, B_FScan, B_StopMeas, B_QueryDeviceInfo, B_QueryFaciDevStat, B_PScan, B_MScan
3. **B_SelfTest 端点不存在** - 已从 OPERATION_TO_REAL_ATOM 映射表中移除
4. Real Atom 需要物理设备连接才能正常响应（当前测试环境无设备）

**相关文件**:
- Real Atom 位置: `D:\arvin\claude_workspace\RXAtomSvcV3\`
- Real Atom WSDL: `D:\arvin\claude_workspace\RXAtomSvcV3\wsdl\8282\`
- Real Atom 日志: `D:\arvin\claude_workspace\RXAtomSvcV3\log\`

**健康检查响应**:
- Proxy-A/B: `{"service": "proxy", "status": "ok"}`

### 1.1 分析结果

**run_all.py 结构**:
- 端口检查列表: `[9000, 9090, 8080, 19000]`
- 启动顺序: Mock Device (9000) → Atom (9090) → Proxy (8080)
- 启动函数: `start_service(script_name, service_name, port)`
- 日志输出: `logs/service_{port}.log`

**main_proxy.py 结构**:
- 使用 `config.settings.SERVICES['proxy']` 获取配置
- 使用 `SERVICES['atom']` 获取 Atom 连接地址
- Flask 应用，端口由配置决定

**settings.py 关键配置**:
```python
SERVICES['proxy']['port'] = 8080
SERVICES['atom']['host'] = '127.0.0.1'
SERVICES['atom']['port'] = 9090
```

**双Proxy需要修改的内容**:
1. 新增端口 8081 到 `PORTS_TO_CHECK`
2. 新建 `settings_proxy_b.py`（Atom 指向 Real Atom）
3. 新建 `main_proxy_b.py`（导入 settings_proxy_b）
4. `run_all.py` 添加 `--dual` 参数支持

---

## 测试用例状态

| ID | 测试项 | 状态 | 执行日期 | 备注 |
|----|--------|------|----------|------|
| TC-01 | TCP 连接测试 | ⬜ | - | 待执行 |
| TC-02 | SGLFREQ 单点频率测量 | ⬜ | - | 待执行 |
| TC-03 | IFANALYSIS 中频分析 | ⬜ | - | 待执行 |
| TC-04 | FSCAN 频谱扫描 | ⬜ | - | 待执行 |
| TC-05 | DF 测向功能 | ⬜ | - | 待执行 |
| TC-06 | IFDF 中频测向 | ⬜ | - | 待执行 |

### 状态图例

| 状态 | 说明 |
|------|------|
| ⬜ | 未执行 |
| 🔄 | 执行中 |
| ✅ | 通过 |
| ❌ | 失败 |
| ⚠️ | 部分通过/有警告 |
| ⏸️ | 阻塞（待前置条件） |

---

## 里程碑

| 里程碑 | 目标日期 | 实际日期 | 状态 |
|--------|----------|----------|------|
| M1: 连接测试通过 | - | - | ⬜ |
| M2: 基础业务功能通过 | - | - | ⬜ |
| M3: 全部测试通过 | - | - | ⬜ |

---

## Real Atom 联调发现（重要）

### Real Atom 行为分析

**测试结论**：Real Atom 在没有物理设备时会**阻塞等待**，而不是崩溃

**观察结果**：
1. Real Atom 进程启动正常，端口 8282 监听正常
2. Real Atom 持续 ping 设备 IP（m_bIsConnected=0）
3. 收到 SOAP 请求后，Real Atom 阻塞等待设备响应
4. curl 请求超时（30秒），但 Real Atom 进程仍在运行

**日志证据**：
```
[22:17:08] 启动成功
[22:17:10] m_bIsConnected=0, ping不通设备
[22:17:19] 收到 Soap call
[22:17:19.xxx] 阻塞等待（无崩溃）
```

**配置已正确**：
- streamsrc: 127.0.0.1:9000 ✓
- devinfo station: 127.0.0.1:9000 ✓

**阻塞原因**：
- Real Atom 需要与物理设备建立连接才能处理业务请求
- 无物理设备时，Real Atom 等待设备响应而不会返回错误

### 协议转换流程

```
外部请求 → [SOAP/HTTP] → Proxy → [SOAP/HTTP] → Atom → [RMCPTP v2.0/TCP] → Device
```

**转换点**：
| 阶段 | 协议 | 格式 |
|------|------|------|
| 外部 → Proxy | SOAP | XML over HTTP |
| Proxy → Atom | SOAP | XML over HTTP |
| Atom → Device | RMCPTP v2.0 | 二进制帧 over TCP |

**关键代码位置**：
- `routes.py` - SOAP 请求解析和转发
- `main_atom.py:236-252` - SOAP → RMCPTP 转换
- `protocol_builder.py` - RMCPTP 帧构建
- `mock_device/tcp_server.py` - RMCPTP 响应处理

---

## 双通道对比测试结果

### 测试时间：2026-04-06

| 通道 | 服务 | 结果 | 说明 |
|------|------|------|------|
| Proxy-A | Mock Atom | ✅ 成功 | 正常返回数据 |
| Proxy-B | Real Atom | ❌ 超时 | 阻塞等待物理设备 |

**结论**：
- Mock Atom 链路工作正常
- Real Atom 需要物理设备才能正常响应

---

## 统计数据

| 指标 | 值 |
|------|---|
| 总测试用例 | 6 |
| 已执行 | 1 |
| 通过 | 1 |
| 失败 | 0 |
| 完成率 | 17% |

**最后更新**: 2026-04-06
