# DEV_20260619: B_QueryFaciDevStat 状态管理模块化分析

**日期**: 2026-06-19
**版本**: v1.5.14+
**状态**: 分析完成，待实施

---

## 1. 当前架构

### 1.1 数据流水线

```
CLIENT → SOAP 请求(mfid/equid)
             │
             ├─ mfid/equid → 从请求 XML 提取（regex，service.py:996-997）
             ├─ equname    → 磁盘 devinfo/*.xml 文件（service.py:1013-1015）
             ├─ mfname     → settings.json 预设匹配（service.py:1019-1028）
             ├─ altitude   → 硬编码 "0.0"
             │
             └─ state      → SessionManager.get_active_sessions()
                    │
                    ├─ 空 → idle（内联 body_content 字符串，无 tasklist）
                    │
                    └─ 非空 → busy（读 session.fscan_params 裸 dict）:
                         taskid  = session.taskid
                         stc     = fscan_params['stc']
                         appid   = fscan_params['appid']
                         userid  = fscan_params['userid']
                         mode    = fscan_params['mode'] → if-elif → feature
```

### 1.2 关键事实

- **不查询物理设备**：B_QueryFaciDevStat 不发送任何 RMCP 请求。RMCP 协议（RX-RMCPTP）没有"查询设备状态"命令。
- **真实 Atom 同样不查询**：透明代理日志确认无 RMCP 流量。
- **工信部规范同样无 RMCP 级状态查询**：DeviceStatus 是 SOAP 层面的概念。

---

## 2. 耦合度评估

| 关注点 | 位置 | 耦合 | 问题 |
|--------|------|:--:|------|
| state 判定 | `service.py:1031` → SessionManager | 中 | idle/busy 决策逻辑在 handler 内联 |
| fscan_params 字段提取 | `service.py:1034-1049` — `.get()` 链 | **高** | 裸 dict 访问，拼写错误静默返回默认值 |
| mode→feature 映射 | `service.py:1040-1049` — if-elif | **高** | 枚举硬编码，新增模式需多处修改 |
| 站名解析 | `service.py:1019-1028` | **高** | 绕过 `Config.get_device_preset()` API，重复实现查找逻辑 |
| 空闲 XML 构建 | `service.py:1066-1077` — 内联 f-string | **高** | 绕过模板系统，XML 结构改动需同步两处 |
| devinfo 加载 | `service.py:1007` → DevicePresetManager | 低 | 正确委托 ✅ |
| SOAP 封套/HTTP | `device_preset.py:322-398` | 低 | 正确委托 ✅ |
| 正则解析重复 | `service.py:996-997` ≈ `:964-965` | 中 | 两个 handler 复制相同 namespace-agnostic regex |

### 2.1 核心问题

1. **idle XML 硬编码绕过模板系统** — 模板 `B_QueryFaciDevStat.xml` 支持 busy/idle，但 idle 路径不调用它
2. **`fscan_params` 裸 dict 访问** — `session.fscan_params.get('userid', '')` 类型不安全
3. **mode→feature 映射重复** — 同样的 if-elif 链在其他地方也需要
4. **站名解析绕过 Config API** — `get_device_preset()` 已存在但未被使用
5. **正则解析复制粘贴** — `_handle_query_device` 和 `_handle_query_faci_dev_stat` 重复

---

## 3. 模块化方案：提取 `DeviceStatusProvider`

### 3.1 提取内容

| 当前位置 | 新位置 |
|----------|--------|
| `service.py:1031` — state 判定 | `device_status.py` |
| `service.py:1034-1049` — fscan_params 字段提取 | `device_status.py` |
| `service.py:1040-1049` — mode→feature 映射 | `device_status.py` |
| `service.py:1019-1028` — 站名解析 | `device_status.py` |
| `service.py:1013-1015` — equname 提取 | `device_status.py` |
| 响应 DTO 聚合 | `device_status.py`（新增 `StatusResult` dataclass） |

### 3.2 依赖关系

```
device_status.py (DeviceStatusProvider)
  ├── session_manager.py (SessionManager) — 注入
  ├── preset/device_preset.py (DevicePresetManager) — 注入
  ├── config.py (Config) — 注入
  └── StatusResult dataclass — 新增，无外部依赖
```

**零新外部依赖** — 所有依赖已是可注入组件。

### 3.3 代码量估算

| 项目 | 当前 | 模块化后 |
|------|------|----------|
| `_handle_query_faci_dev_stat` | 97 行 | ~20 行 |
| `device_status.py`（新） | 0 | ~80-100 行 |
| 净增量 | — | ≈0（重新分布） |

---

## 4. 成本/收益

| 维度 | 当前（耦合） | 模块化后 |
|------|-------------|----------|
| **service.py 行数** | 1706（handler 97行） | ~1629（handler ~20行） |
| **测试能力** | 需完整 Service 布线 | Provider 独立可测 |
| **新增状态字段** | 改内联 XML + 模板 + 提取代码 | 改 StatusResult dataclass + 模板 |
| **切换 RMCP 状态源** | 改 handler 内联逻辑 | 替换 Provider 实现，接口不变 |
| **回归风险** | 两处 XML 结构同步 | 单一来源，类型检查 |
| **可读性** | 97 行混合关注点 | Provider 返回 StatusResult 对象 |

### 4.1 建议的三步实施

1. **idle 体改用模板** — 消除 `service.py:1066-1077` 硬编码 XML
2. **提取 DeviceStatusProvider** — 重新分组，零新依赖
3. **新增 StatusResult dataclass** — 类型安全，取代裸 dict

---

## 5. 附录：工信部规范与 GWJ 规范对比

| 规范 | 状态查询机制 |
|------|-------------|
| 工信部无2016379号-1 §11.1.24 | `QueryFacilityDevStatus` — SOAP XML `<query type='result'>`，返回 position + state(idle/busy) + task(任务ID) |
| GWJ003-2015 §4.24 | 同上结构，但 `<task>` 内容为 任务下达人（非任务ID） |
| 真实 Atom (gSOAP) | SOAP Envelope 包装：`srrc:responsebody/srrc:result/srrc:equlist/srrc:equipment/srrc:tasklist/srrc:task` |
| RMCP (RX-RMCPTP) | **无设备状态查询命令** — 纯测量数据传输协议 |

**结论**：所有层面的设备状态查询都是 SOAP 层概念，不涉及 RMCP。无心跳/keep-alive 机制。平台需通过 SelfTest（`<available/>`）或 QueryFacilityDevStatus 主动轮询。
