# TASKS 2026-04-18: FSCAN 三频段扫描分析

## 🔴 目标
实现 emulated_atom 三频段循环扫描，与真实 Atom 一致

## 根因分析完成 ✅

**设备返回数据** (从 rmcp_proxy 日志 capture_9997_20260417_152722.log):

设备一次请求返回 **多个 FSCAN 帧**，每个帧对应不同频段：
- `Counters: [512, 0, 0, 0]` - 第一频段 (起始序号 0, 137.0-149.775MHz)
- `Counters: [512, 0, 512, 0]` - 第二频段 (起始序号 512, 149.8-162.575MHz)
- `Counters: [417, 0, 1024, 0]` - 第三频段 (起始序号 1024, 162.6-173.0MHz)

**问题定位**:
1. `_get_fscan_from_capture()` 只取前 512 点，丢弃了第二、三频段数据
2. metadata 频率参数是写死的，没有从设备数据解析
3. 没有实现三频段循环推送逻辑

## 实现计划

### 1. 修改数据获取逻辑 ✅
- [x] `_get_fscan_spectrum()` 返回完整三频段数据 (512+512+417 = 1441 点)
- [x] 在获取数据时同时返回各频段的 counters 信息

### 2. 修改帧构建逻辑 ✅
- [x] `build_streamsrc_frame()` 支持传入频率参数
- [x] metadata 中的起始频率、结束频率、起始序号从数据中获取

### 3. 实现三频段循环 ✅
- [x] `_start_fscan_push()` 循环发送三频段帧
- [x] 第一帧: FSCAN-529, 512点, 序号0 (band1)
- [x] 第二帧: FSCAN-529, 512点, 序号512 (band2)
- [x] 第三帧: FSCAN-434, 417点, 序号1024 (band3)
- [x] 循环往复

## 实现细节

### 关键修改
1. `_parse_single_fscan_frame()` 返回 `(spectrum, counters)` 元组
2. `_get_fscan_from_rmcp_proxy()` 根据 `counters[2]` (起始序号) 判断频段
3. `_get_fscan_from_capture()` 收集所有 FSCAN 帧并按 counters[2] 排序合并
4. `_start_fscan_push()` 按 band1(529)→band2(529)→band3(434) 循环推送

## 参考数据

| 来源 | 路径 |
|------|------|
| rmcp_proxy 日志 (设备返回) | `rmcp_proxy/capture/capture_9997_20260417_152722.log` |
| 真实 Atom 回显 | `D:\arvin\YL_workapace\...\4-18_testtool\8282_真实atom.txt` |
| 真实 Atom 帧序列 | 三频段循环: 529→529→434→529→529→434... |

## 关键代码位置

| 函数 | 位置 | 需要修改 |
|------|------|---------|
| `_get_fscan_spectrum()` | Line 1595 | 返回完整三频段数据 |
| `_get_fscan_from_capture()` | Line 1638 | 解析所有 counters |
| `build_streamsrc_frame()` | Line 308 | 支持动态频率参数 |
| `_start_fscan_push()` | Line 845 | 实现三频段循环逻辑 |
