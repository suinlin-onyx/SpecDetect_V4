# PScan streamsrc 封帧对齐任务

**创建日期**: 2026-04-24
**最后更新**: 2026-04-25

---

## 已完成任务

### 任务1: PL序列对齐 ✅ (2026-04-24)

- PL序列改为 [872, 616, 360, 872, 616] (5帧循环)
- 移除 PL=104
- 修改位置: `service.py` `_push_frame()` pscan分支

### 任务2: FScanType修改 ✅ (2026-04-24)

- FScanType 改为 `0x0b` (11, IFANALYSIS)
- 修改位置: `stream/frame.py` `build_pscan_fscan_frame()`

### 任务3: Metadata统一 ✅ (2026-04-24)

- 所有帧使用同一份 metadata (start_index=0, 1441通道)
- bytes 29-30 改为 `a105` (1441)
- 修改位置: `stream/frame.py` `_get_pscan_metadata()`

### 任务4: 高频段数据来源探索 ✅ (2026-04-24)

**结论**: RMCP 4001点 (80-180MHz, 25kHz步长) 中按频率选取 137-173MHz 子带

**频率映射**:
- 137MHz = RMCP index (137-80)/0.025 = **2280**
- 173MHz = RMCP index (173-80)/0.025 = **3720**
- slice `rmcp_levels[2280:3721]` = **1441点**

**字节编码**: PScan 第二字节 `0x00` (不同于 FScan 的 `0xFF`)

---

## 当前状态

PScan streamsrc 封帧已与真实设备对齐 (2026-04-24)。

帧格式: 2944B, DT=12, FScanType=0x0b, 1441点, PL仅控制indicator。

详见 `docs/PSCAN_FRAME_IMPLEMENTATION.md`。

---

## 待验证项

| # | 任务 | 状态 | 优先级 |
|---|------|------|--------|
| A | B_SglFreqMeas 实现与联调 | 代码完成，待设备验证 | 高 |
| B | B_MScan 实现与联调 | 代码完成，待设备验证 | 高 |
| C | PScan real device 测试 | 代码已恢复，待验证 | 中 |

---

## 参考数据

- 抓包文件: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\logs\stream_B_PScan_18013_222551_374907.bin`
- RMCP DSCAN: 4001点/帧, 8013B payload, reserved=1
