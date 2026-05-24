# PScan 接口实现任务

## 已有基础

| 组件 | 状态 |
|------|------|
| SOAP handler `_handle_pscan` | ✓ 已实现 |
| RMCP 请求 XML 构建 (`mode='pscan'`) | ✓ 已实现 |
| streamsrc 帧生成 (`build_pscan_*_frame`) | ✓ 已实现 |
| BandCollector 缓冲 | ✓ 已复用 FSCAN 成果 |
| `_start_rmcp_receive` 接收线程 | ✓ 已重构 |

## 待实现

### P0 - 核心回调解析

**1. 分析 soap_proxy 捕获的 streamsrc PScan 帧**
- 文件：`soap_proxy/logs/stream_B_PScan_18013_220836_270530.bin`
- 确认 streamsrc PScan 帧格式（1671B vs 3256B？）
- 提取帧头结构：VER、INDICATOR、DT、DL 等字段
- 对照已有的 `build_pscan_spectrum_frame` (3256B) 是否正确

**2. 实现 RMCP PScan 回调解析 (`_start_rmcp_receive`)**
- 实测确认：n_bd_type=0x10 → DSCAN 数据帧 (1240B)
- 数据点数：605个 int16 ((1240-18-11)/2)
- counters[0] = 1441 (总通道数，非帧内数据点数)
- 帧结构与 FSCAN 类似：`[n_bd_type][2B][counters(8B)][int16[N]]`
- counters offset = 3

**3. 实现 push loop `mode='pscan'` (`_start_push`)**
- 当前 server.py 的 push_loop 缺少 `elif mode == 'pscan'` 分支
- 参考 FSCAN：循环 `band_collector.get()` → `_push_callback(session, band)` → `sendall(frame)`
- 确认 PScan 推送逻辑：是实时推送每帧，还是缓冲后批量推送？

### P1 - 验证与对齐

**4. 对比 soap_proxy 捕获的 streamsrc PScan 帧**
- 分析捕获文件中的帧结构
- 确认streamsrc帧头格式与现有实现是否一致
- VER 字段：应该也是 1？

**5. 测试完整流程**
- SOAP B_PScan → streamsrc 连接 → RMCP REQUEST → 设备回调 → streamsrc 推送
- 验证数据正确性

### P2 - 细节优化

**6. PScan 三帧循环逻辑确认**
- FSCAN: B1→B2→B3 三帧顺序推送（已完成）
- PScan: spectrum → level → ITU 三帧循环？或实时推送？
- 需确认设备回调的 n_bd_type 顺序

## 关键参考

- **FSCAN 经验**：VER=1、BandCollector 单band put/多band get、RMCP payload offset=3 for counters
- **PScan n_bd_type**：0x10 (DSCAN, 1240B, 605点int16)
- **PScan funcid**：16
- **捕获文件**：`soap_proxy/logs/stream_B_PScan_18013_220836_270530.bin` (59205B)
- **RMCP回调日志**：`rmcp_DSCAN_9996_20260423_150425.log`
