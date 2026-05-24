# 数据审查与帧过滤模块 [进行中]

**创建日期**: 2026-04-25
**问题发现日期**: 2026-04-25
**方案**: 乙 — 双端验证 + 明确停止时序

---

## 问题描述

1. **残留数据问题**: Session 重启时（StopMeas 后再发 B_FScan），收到大量错误数据
2. **GPS 数据混入**: n_bd_type=38 (GPS占用度) 不应出现在 FSCAN 等业务流中
3. **多 n_bd_type 混杂**: 错误的数据被封装到 streamsrc 帧发出

---

## 根因分析

数据流路径：
```
设备 RMCP → RMCPClient._recv_buffer → get_callback_datas()
  → parse_rmcp_callback_frame() → BandCollector / session变量
  → _push_frame() → streamsrc帧 → test tool
```

**问题点**：
1. RMCP 层：GPS(38) 等 n_bd_type 不在解析器映射中，但仍可能被其他路径处理
2. Session 重启时：recv_buffer 残留数据、BandCollector 未清空
3. streamsrc 层：无数据验证，直接封装

---

## 方案设计

### 分层验证架构

| 层 | 位置 | 验证内容 | GPS 在此层 |
|---|---|---|---|
| Layer 1 | RMCP receive_loop | n_bd_type 白名单检查 | ✓ 丢弃 |
| Layer 2 | RMCP → BandCollector | 数据结构验证 (counters/n_arrays/levels) | ✓ 丢弃 |
| Layer 3 | streamsrc 封帧前 | 帧参数合法性 (indicator/PL) | ✓ 丢弃 |

### n_bd_type 白名单

```python
_MODE_BD_TYPE_WHITELIST = {
    'fscan':  {15},           # FSCAN
    'mscan':  {14},           # SGLFREQ (单频点)
    'sglfreq': {11},          # IFANALYSIS
    'pscan':  {16},           # DSCAN
}
```

### 验证函数

```python
# validator.py

# Layer 1: n_bd_type 白名单
def validate_bd_type(mode: str, n_bd_type: int) -> bool:
    whitelist = _MODE_BD_TYPE_WHITELIST.get(mode, set())
    return n_bd_type in whitelist

# Layer 2: 数据结构验证
def validate_band_structure(band: dict) -> bool:
    # counters[2] 必须是 0/512/1024
    # n_arrays 必须在 1-10000 范围
    # levels 值必须在 -1000~+1000 范围
    ...

# Layer 3: streamsrc 封帧前验证
def validate_streamsrc_frame_params(band: dict, mode: str) -> bool:
    # indicator 必须与 start_index 匹配
    # PL 必须合理
    ...
```

---

## 实现任务

- [x] 新增 `src/atom/validator.py` — 数据审查模块
- [x] 修改 `src/atom/service.py` — Layer 1+2 集成到 receive_loop
- [x] 修改 `src/atom/service.py` — Layer 3 集成到 _push_frame
- [x] 修改 `src/atom/session.py` — close_all() 显式清理 buffer + 队列
- [x] 修改 `src/log/logger.py` — 新增 FILTER 日志标签

---

## 文件改动

| 文件 | 改动 |
|------|------|
| `src/atom/validator.py` | 新增：数据审查模块 |
| `src/atom/service.py` | Layer 1+2 在 receive_loop，Layer 3 在 _push_frame |
| `src/atom/session.py` | close_all() 显式清理 RMCP buffer + BandCollector + 队列 |
| `src/log/logger.py` | 新增 LogTag.FILTER |

---

## 验证状态

- [x] validator.py 语法验证通过
- [x] service.py 语法验证通过
- [x] session.py 语法验证通过
