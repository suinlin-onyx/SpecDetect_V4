# TASK_20260619: 会话状态管理与回调对齐综合修复

**日期**: 2026-06-19
**优先级**: HIGH
**版本**: v1.5.8 → v1.5.9
**状态**: Phase 1 已完成(error响应结构), Phase 2 待实施

---

## Phase 1 已完成 (v1.5.8, 已 commit)

错误响应格式对齐 — `build_error_response` 结构化 XML。见 git commit `9b1a269`。

---

## Phase 2 待实施 (本次)

### P0-1: PENDING 窗口 — create_pending 计入 PENDING 占用

**问题**: Source 模式下，PENDING session 不在 `self.sessions` 中，`active_count` 不计数。两个请求间隔足够短时（streamsrc 未连接），可创建两个 PENDING session，绕过 max_sessions。

**位置**: `session_manager.py:create_pending` L70-72

**修复**: 在 `create_pending` 入口检查 `pending_sessions` 是否非空：

```python
def create_pending(self, taskid, fscan_params=None):
    with self.lock:
        # PENDING 也算占用
        if self.pending_sessions:
            raise RuntimeError("设备使用冲突")
        
        active_count = sum(1 for s in self.sessions.values() if s.state == SessionState.ACTIVE)
        if active_count >= self.max_sessions:
            raise RuntimeError("设备使用冲突")
        ...
```

**验证**: 连续发两个 B_FScan Source，第2个立即返回 BIZ-00002-conflict。

---

### P0-2: Sink 模式 SOAP 响应被 RMCP 阻塞

**问题**: Sink 模式 handlers (B_FScan/B_PScan/B_SglFreqMeas) 在 `_start_sink_stream` 之后才返回 SOAP 响应。`_start_sink_stream` 同步调用 `rmcp_client.connect(timeout=10)`，设备离线时阻塞 10 秒。

**测试证实**: SGAtom #1 B_PScan Sink — 请求 16:44:29，响应 16:44:39（10s 延迟），透明代理没捕获到响应（连接已断）。

**位置**: 
- `service.py:310` (B_FScan Sink)
- `service.py:715` (B_PScan Sink)
- `service.py:889` (B_SglFreqMeas Sink)

**修复**: SOAP 响应应在 `_start_sink_stream` **之前**返回。将 `_start_sink_stream` 改为后台线程：

```python
# 修复后流程：
session.outputchannel_forwarder = sink_socket
session.state = SessionState.ACTIVE

rf = self._get_response_fields(request)
response = self.preset_manager.build_response(...)

# 启动后台线程连接 RMCP
threading.Thread(target=self._start_sink_stream, args=(session,), daemon=True).start()

return response  # 立即返回，不等 RMCP
```

---

### P0-3: Sink 模式先连目标再查 session

**问题**: Sink 模式先 `sink_socket.connect()` 再 `create_pending()`。busy 时白白连接 Sink 目标然后立即断开。

**位置**: B_FScan Sink L278, B_PScan Sink L696, B_SglFreqMeas Sink L856

**修复**: 将 `create_pending` 调用移到 `sink_socket.connect()` 之前。

---

### P1-1: B_QueryFaciDevStat 模板对齐

**问题**: 模板有 `<equlist><equipment>` 包裹层，且缺少 `{appid}` 字段。

**修复**: 代码已写完（uncommitted），需 commit + rebuild。涉及文件：
- `B_QueryFaciDevStat.xml` — 平级结构，添加 `{appid}`
- `service.py` — 4 个测量接口的 fscan/pscan/mscan/sglfreq_params 添加 appid/userid
- `service.py` — `_handle_query_faci_dev_stat` 从 session 读取 appid/userid

---

### P1-2: B_QueryFaciDevStat idle 时泄露字段

**问题**: idle 状态时模板仍输出 taskid/userid/feature/appid/stc（空值）。真实 Atom idle 时完全不返回这些字段。

**修复**: `_handle_query_faci_dev_stat` 在 idle 时传空字符串给 taskid/feature/stc；`build_response` → `inject_fields` 跳过空值字段（或在模板中条件化）。

---

## Busy 状态逻辑全貌

### 当前已正确的行为

| 场景 | 行为 | 状态 |
|---|---|---|
| Busy 时新请求 → create_pending raise → 立即返回 conflict | 不连接 RMCP，不创建 session | ✓ |
| Source 模式 SOAP 响应 | 立即返回（不等 RMCP） | ✓ |
| B_QueryFaciDevStat busy | 返回 taskid/userid/feature/stc | △ 缺 appid |
| 4 个测量接口 conflict 回调 | 统一 BIZ-00002-conflict | ✓ |

### 待修复的行为

| 场景 | 当前 | 期望 |
|------|------|------|
| PENDING 窗口 | 第2次可创建 | 第2次拒绝 |
| Sink SOAP 响应 | 等 RMCP 10s | 立即返回 |
| Sink busy 时 | 先连 Sink 再断开 | 先查 session 再连 |
| idle 响应 | 泄露 userid/stc | 只返回基础字段 |
| busy 响应 | 缺 appid | 完整 5 字段 |

---

## 实施计划

### Step 1: 开发 (code-architect + implement)
- `session_manager.py`: create_pending 加入 PENDING 检查
- `service.py`: Sink 模式 3 处改为先返回响应再后台启动 RMCP，Sink 连接移到 session 检查之后
- 提交 B_QueryFaciDevStat 模板 + appid/userid 代码（已有 uncommitted changes）
- `device_preset.py`: build_response/inject_fields 处理空值跳过

### Step 2: 测试 (tdd-guide)
- PENDING 窗口测试
- Sink 响应延迟测试
- B_QueryFaciDevStat idle/busy 字段完整性测试
- 4 接口 conflict 回调回归测试

### Step 3: 审查 (code-reviewer)
- session 状态机完整性
- 线程安全（_start_sink_stream 改后台线程）
- callback 格式对齐

### Step 4: 打包 (按现有 build.bat)
- 更新版本号 v1.5.8 → v1.5.9
- 构建 + 部署 + 验证

---

## 涉及文件

| 文件 | Phase | 变更类型 |
|------|-------|----------|
| `session_manager.py` | P2 | PENDING 计数 |
| `service.py` | P2 | Sink 响应时序 + Sink 连接顺序 + appid/userid |
| `B_QueryFaciDevStat.xml` | P2 | 模板重构（已完成，uncommitted） |
| `device_preset.py` | P2 | inject_fields 空值跳过 |
| `version.py` | P4 | 1.5.8 → 1.5.9 |
| `settings.json` | P4 | 版本同步 |
| `version_info.txt` | P4 | 版本同步 |
