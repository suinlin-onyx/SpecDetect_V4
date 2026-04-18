# SpecDetect UI-Atom 测试指南

**创建日期**: 2026-04-13
**更新日期**: 2026-04-13

---

## 1. 测试环境配置

### 1.1 设备信息

| 项目 | 值 |
|------|-----|
| Real Device | 100.72.95.36:1449 |
| mfid | 53090001140012 |
| equid | 51cd8dfe-e543-40c9-bdc3-a292766fee7f |

### 1.2 本地服务

| 服务 | 端口 | 说明 |
|------|------|------|
| Client (Flask) | 8080 | Web UI |
| Client (WebSocket) | 8081 | 回调推送 |
| Atom (SOAP) | 8282 | SOAP 服务 |
| Atom (WS) | 8081 | WebSocket 推送 |

---

## 2. 接口测试用例

### 2.1 已验证接口

| funcid | 接口 | 模式 | 参数 | 预期结果 |
|--------|------|------|------|----------|
| 16 | B_MScanDF | 扫描 | startfreq/stopfreq/step | nArrays=1441 ✅ |
| 15 | B_FScan | 频率扫描 | startfreq/stopfreq/step | streaming 数据 ✅ |
| 14 | B_MScan | 多信道 | frequency/ifbw | streaming 数据 ✅ |
| 11 | B_SglFreqDF | 单频 | frequency + ifbw=40MHz | nArrays=1, 26电平 ✅ |
| 11 | B_SglFreqDF | 扫描 | frequency + ifbw=40kHz + 额外参数 | nArrays=1601 ✅ |

### 2.2 不支持接口

| funcid | 接口 | 错误信息 |
|--------|------|----------|
| 12 | B_SglFreqMeas | 设备校验失败 |
| 25 | B_WBDF | 设备校验失败 |

---

## 3. 测试用例详情

### 3.1 设备连接测试

**目的**: 验证 Client 能成功连接 Atom，Atom 能连接 Device

**前置条件**:
- Atom Service 运行中
- Real Device 在线

**测试步骤**:
1. 启动 Atom Service
2. 启动 Client
3. 打开 Web UI
4. 选择设备
5. 点击"连接"

**预期结果**:
- WebSocket 连接建立
- 显示"设备已连接"

---

### 3.2 B_FScan 接口测试

**目的**: 验证频段扫描功能

**请求参数**:
```xml
<item name="startfreq" value="137MHz" />
<item name="stopfreq" value="173MHz" />
<item name="step" value="25kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
```

**预期结果**:
- streaming 数据帧持续推送
- 频率范围: 137-173 MHz
- 步进: 25 kHz
- 数据格式: DT=7 (频谱数据)

---

### 3.3 B_SglFreqDF 单频模式测试

**目的**: 验证单频测向功能

**请求参数**:
```xml
<item name="frequency" value="100MHz" />
<item name="ifbw" value="40000000kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
```

**预期结果**:
- nArrays = 1
- 电平数量 = 26
- DT = 101 (电平数据)
- 中心频率 = 100 MHz

---

### 3.4 B_SglFreqDF 扫描模式测试

**目的**: 验证扫描模式功能

**请求参数**:
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

**预期结果**:
- nArrays = 1601
- 频率范围: 80-120 MHz (center ± 20MHz)
- 步进: ≈25 kHz
- DT = 7 (频谱数据)

---

## 4. 数据格式验证

### 4.1 简化格式结构

```
Byte 0-2:   Business header (nBdType=11)
Byte 3-10:  Counters (4 × int16, little-endian)
Byte 11+:   Spectrum data (int16 little-endian, dBm = raw/10)
```

### 4.2 关键字段

| 字段 | 说明 | 转换公式 |
|------|------|----------|
| nBdType | 业务类型 (11=FSCAN) | - |
| counters[0] | nArrays (通道数) | - |
| levels_raw | 原始电平值 | dBm = raw / 10 |
| VER | 版本 (16=电平数据) | - |
| DT | 数据类型 (7=频谱, 101=电平) | - |

---

## 5. 回归测试

### 5.1 接口回归

每次代码变更后，重新测试以下接口：

| 优先级 | 接口 | 测试内容 |
|--------|------|----------|
| P0 | B_FScan | 频段扫描 streaming |
| P0 | B_SglFreqDF (单频) | 单频测向 |
| P0 | B_SglFreqDF (扫描) | 扫描模式 |
| P1 | B_MScanDF | 多信道扫描测向 |
| P1 | B_MScan | 多信道扫描 |
| P2 | B_StopMeas | 停止测量 |

### 5.2 自动化测试

```bash
# 运行 experimental 测试
cd SpecDetect_POC/experimental
python test_pscan_sglfreq.py B_FScan 5
python test_pscan_sglfreq.py B_SglFreqDF 5
python test_pscan_sglfreq.py B_SglFreqDF_SCAN 5
```

---

## 6. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-13 | 初始版本 |
