# TASKS 2026-04-25 PScan 分析归档 [已完成]

**归档日期**: 2026-04-25
**状态**: 实现完成，待测试验证

---

## PScan streamsrc 帧格式确认

### 抓包分析

- 文件: `stream_B_PScan_18013_210658_251442.bin`
- 设备: 真实设备

### DT 类型

| DT  | 帧数  | 说明            |
| --- | --- | ------------- |
| 201 | 1   | UUID 帧 (连接握手) |
| 12  | 10  | FSCAN 数据帧     |

**结论**: PScan 使用 DT=12 (FSCAN 格式)

### Indicator 变化

- 0x0168, 0x0368, 0x0268, 0x0168 ...
- Indicator 与 PL 值相关联

---

## PL 值

### 来源

- 随机序列: [872, 616, 360, 872, 616] 循环
- 或在这4个数中随机选择

### PL 影响

- 影响 payload 长度
- 影响 indicator 值
- 不影响总 spectrum points (1441)

---

## RMCP → streamsrc 转换

### 数据流

```
RMCP 设备 → receive_pscan_raw() → _parse_raw_dscan()
  → session._pscan_band → push_loop
  → _push_frame → build_pscan_fscan_frame()
  → streamsrc DT:12 FSCAN帧
```

### RMCP 数据

- n_bd_type = 16 (DSCAN)
- 17 个 DSCAN 回调 (含 1 个初始化帧)
- spectrum_length = 1441 points

### streamsrc 数据

- DT = 12 (FSCAN)
- 1441 points per frame
- 10 个数据帧 (初始化帧不发送)

---

## 1441 points 解析

### 频率范围

- RMCP 覆盖 80-180MHz (4001 points, 25kHz 步长)
- 选取 137-173MHz 子带 (indices 2280-3720)
- 1441 = 3720 - 2280

### 编码

- RMCP int16 (dBm × 10) → 单字节 (dBm) + 0x00 填充
- 公式: byte = 256 + dBm (负值) 或 min(dbm, 255) (正值)

---

## 关键实现

| 文件                | 函数                                 | 说明                    |
| ----------------- | ---------------------------------- | --------------------- |
| `rmcp/client.py`  | `receive_pscan_raw()`              | PScan 专用接收            |
| `rmcp/client.py`  | `_parse_raw_dscan()`               | 解析 raw DSCAN payload  |
| `rmcp/frame.py`   | n_bd_type=16 映射                    | `parse_dscan_payload` |
| `stream/frame.py` | `build_pscan_fscan_frame()`        | 构建 DT:12 FSCAN 帧      |
| `stream/frame.py` | `_PSCAN_RMCPCENTER_START/END`      | 2280/3721             |
| `service.py`      | `_start_pscan_receive()`           | PScan 接收线程            |
| `service.py`      | `_push_frame` pscan 分支             | PL 序列轮询               |
| `validator.py`    | `_MODE_BD_TYPE_WHITELIST['pscan']` | {16}                  |

---

## 待验证

- [ ] PScan 真实设备测试
- [ ] 确认 streamsrc 帧能被 test tool 正确解析
- [ ] 确认频率范围 137-173MHz 正确

---

## 历史文档

- `docs/TASKS_20260424_PScan_HighFreq.md` - 高频数据来源分析
- `docs/TASKS_20260424_PScan_粘包问题.md` - TCP 粘包处理
