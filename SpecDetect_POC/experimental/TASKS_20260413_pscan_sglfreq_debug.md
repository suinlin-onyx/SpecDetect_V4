# 任务清单 - funcid 接口调试

**创建时间**: 2026-04-13
**更新**: 2026-04-13 16:30

---

## 接口验证汇总

### ✅ 已验证接口

| funcid | 接口 | 模式 | 参数 | nArrays | 状态 |
|--------|------|------|------|---------|------|
| 16 | B_MScanDF | 扫描 | startfreq/stopfreq/step | 1441 | ✅ 成功 |
| 15 | B_FScan | 频率扫描 | startfreq/stopfreq/step | - | ✅ 成功 |
| 14 | B_MScan | 多信道 | frequency/ifbw | - | ✅ 成功 |
| 11 | B_SglFreqDF | 单频 | frequency + ifbw=40MHz | 1 | ✅ 成功 |
| 11 | B_SglFreqDF | 扫描 | frequency + ifbw=40kHz + 额外参数 | 1601 | ✅ 成功 |

### ❌ 不支持接口

| funcid | 接口 | 原因 |
|--------|------|------|
| 12 | B_SglFreqMeas | 设备返回"设备校验失败" |
| 25 | B_WBDF | 设备返回校验失败 |

---

## funcid=15 B_FScan 实现

**参数**:
```xml
<item name="frequency" value="100MHz" />
<item name="startfreq" value="137MHz" />
<item name="stopfreq" value="173MHz" />
<item name="step" value="25kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
```

**返回数据**:
- streaming 数据帧
- DT = 7 (频谱数据)
- 频率范围: 137 ~ 173 MHz
- 步进: 25 kHz

---

## funcid=11 双模式详解

### 单频模式 (ifbw=40MHz)

**参数**:
```xml
<item name="frequency" value="100MHz" />
<item name="ifbw" value="40000000kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
```

**返回数据**:
- nArrays = 1
- 电平数量 = 26
- DT = 101 (电平数据)
- 中心频率 = 100 MHz
- 数据示例: -81.8 dBm

### 扫描模式 (ifbw=40kHz)

**参数**:
```xml
<item name="frequency" value="100MHz" />
<item name="ifbw" value="40000kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
<item name="audioswitch" value="OFF" />
<item name="demodmode" value="FM" />
<item name="demodbw" value="200kHz" />
<item name="bbfftl" value="2048" />
<item name="CombineFunc" value="AsIIEQ" />
```

**返回数据**:
- nArrays = 1601
- 频率范围: 80 ~ 120 MHz
- 步进: ≈25 kHz
- DT = 7 (频谱数据)
- 数据分布: -400 ~ 70 dBm (avg ≈ -75 dBm)

**注意**: 前4个值为设备前缀校准数据，实际频谱从index 4开始

---

## 数据格式说明

### 简化格式结构 (设备直接返回)

```
Byte 0-2:   Business header (nBdType=11)
Byte 3-10:  Counters (4 × int16, little-endian)
Byte 11+:   Spectrum data (int16 little-endian, dBm = raw/10)
```

### VER=1 vs VER=16 差异

| 版本 | 来源 | 数据范围 | 说明 |
|------|------|----------|------|
| VER=1 | TestTool (ATOM处理后) | -25 ~ 0 dBm | 归一化相对值 |
| VER=16 | 设备原始 | -400 ~ 70 dBm | 实际dBm编码 |

**结论**: TestTool显示的VER=1数据经过ATOM内部转换，非原始设备数据

---

## 任务完成状态

| # | 任务 | 状态 | 日期 |
|---|------|------|------|
| 9 | 修复 funcid=11 数据解析，对齐 TestTool 格式 | ✅ 完成 | 2026-04-13 |
| 10 | funcid=11 扫描模式测试 (ifbw=40kHz, nArrays=1601) | ✅ 完成 | 2026-04-13 |
| 11 | 添加 funcid=11 扫描模式完整参数并测试 | ✅ 完成 | 2026-04-13 |
| 12 | B_FScan 接口验证 | ✅ 完成 | 2026-04-13 |

---

## 相关文件

- `experimental/test_pscan_sglfreq.py` - 测试脚本
- `experimental/data/test_result_B_SglFreqDF_20260413_150111.json` - 单频模式数据
- `experimental/data/test_result_B_SglFreqDF_SCAN_20260413_160622.json` - 扫描模式数据
- `rmcp_proxy/capture/capture_20260413_144633.json` - 扫描模式捕获参考
