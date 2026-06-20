# 原始文档与开发文档对比报告

> 创建日期：2026-04-06
> 更新时间：2026-04-06
> 对比范围：原始协议文档 vs 开发规格文档
> 原始文档：`D:\arvin\vhf_monitoring_ws\超短波监测管理一体化服务接口规范\`
> 开发文档：`D:\arvin\claude_workspace\SpecDetect_V4\docs\`

---

## 一、协议规范对比（RMCPTP v2.0）

### 1.1 业务数据类型 ID（settings.py vs 协议）

| 类型ID | 协议文档 | settings.py (修正后) | SRS §6.1 (修正后) | 状态 |
|--------|----------|---------------------|-------------------|------|
| 0x10 | SGLFREQ ✅ | SGLFREQ ✅ | SGLFREQ ✅ | ✅ |
| 0x11 | IFANALYSIS ✅ | IFANALYSIS ✅ | IFANALYSIS ✅ | ✅ |
| 0x12 | DF ✅ | DF ✅ | DF ✅ | ✅ |
| 0x13 | IFDF ✅ | IFDF ✅ | IFDF ✅ | ✅ |
| 0x14 | MSACN/DFSEARCH ✅ | DFSEARCH ✅ | MSACN ✅ | ✅ |
| 0x15 | FSCAN ✅ | FSCAN ✅ | FSCAN ✅ | ✅ |
| 0x16 | DSCAN ✅ | DSCAN ✅ | - | ✅ |
| 0x17 | PSCAN ✅ | PSCAN ✅ | - | ✅ |
| 0x18 | SPANALYSIS ✅ | SPANALYSIS ✅ | SPANALYSIS ✅ | ✅ |
| 0x19 | WBMONDF ✅ | WBMONDF ✅ | ❌ 原 SRS=0x25 | ✅ 已修正 |
| 0x1A | IFDFEXT ✅ | TDANALYSIS ⚠️ | - | ⚠️ 待核实 |
| 0x1C | WMON ✅ | WBFFTMon ✅ | WMON ✅ | ✅ |
| 0x1D | DIGDEM ✅ | DIGDEM ✅ | DIGDEM ✅ | ✅ |
| 0x1E | WBMSCAN ✅ | WBMSCAN ✅ | WBMSCAN ✅ | ✅ |
| 0x1F | EDETN ✅ | EDETN ✅ | EDETN ✅ | ✅ |
| 0x22 | MODREC ✅ | MODREC ✅ | ❌ 原 SRS=0x34 | ✅ 已修正 |
| 0x23 | SINA ✅ | SINA ✅ | SINA ✅ | ✅ 已补全 |
| 0x24 | ITU ✅ | ITUMEAS ✅ | ITU ✅ | ✅ 已补全 |
| 0x26 | DDCDEM ✅ | DDCDEM ✅ | DDCDEM ✅ | ✅ |
| 0x27 | SSDF ✅ | SSDF ✅ | SSDF ✅ | ✅ |
| 0x28 | MULTICHAN ✅ | MULTICHAN ✅ | ❌ 原 SRS=0x40 | ✅ 已修正 |
| 0x29 | ACDF ✅ | ACDF ✅ | ❌ 原 SRS=0x41 | ✅ 已修正 |
| 0x2B | DEMREC ✅ | DEMREC ✅ | ❌ 原 SRS=0x43 | ✅ 已修正 |
| 0x2C | MULCHANANA ✅ | MULCHANANA ✅ | MULCHANANA ✅ | ✅ 已补全 |
| 0x31 | DPX ✅ | DPX ✅ | DPX ✅ | ✅ |
| 0x33 | FREQMEAS ✅ | FREQMEAS ✅ | ❌ 原 SRS=0x51 | ✅ 已修正 |

### 1.2 SRS §3.1 服务表 vs 协议类型 ID

| SRS 服务 | SRS §3.1 ID | 协议对应类型 | 状态 |
|----------|-------------|------------|------|
| WBFFTMon (F-002) | 0x1C | WMON=0x1C ✅ | ✅ |
| WBDF (D-003) | 0x19 | WBMONDF=0x19 ✅ | ✅ 已修正 |
| FScanDF (D-004) | 0x21 | SCANDF=0x21 ✅ | ✅ |
| DigitalSignalRecDecode (S-002) | 0x1D | DIGDEM=0x1D ✅ | ✅ 已修正 |
| ModRec (S-003) | 0x2B | DEMREC=0x2B ✅ | ✅ 已修正 |
| DigDem (S-004) | 0x1D | DIGDEM=0x1D ✅ | ✅ 已修正 |
| FREQMEAS (S-003) | 0x33 | FREQMEAS=0x33 ✅ | ✅ 已修正 |

---

## 二、调制模式 ID（协议 vs SRS §6.2）

| 调制类型 | 协议文档 | SRS §6.2 | 状态 |
|----------|----------|----------|------|
| FM | 0x01 ✅ | 0x01 ✅ | ✅ |
| BPSK | 0x02 ✅ | 0x02 ✅ | ✅ |
| QPSK | 0x03 ✅ | 0x03 ✅ | ✅ |
| 8PSK | 0x04 ✅ | 0x04 ✅ | ✅ |
| 16QAM | 0x05 ✅ | 0x05 ✅ | ✅ |
| 32QAM | 0x06 ✅ | 0x06 ✅ | ✅ |
| 64QAM | 0x07 ✅ | 0x07 ✅ | ✅ |
| AM | 0x0A | 0x10 | ⚠️ **待核实** |
| SSB | 0x0B | 0x11 | ⚠️ **待核实** |
| DSB | 0x0C | 0x12 | ⚠️ **待核实** |
| OFDM | 0x17 | 0x23 | ⚠️ **待核实** |
| FSK | 0x0F | 0x15 | ⚠️ **待核实** |
| ASK | 0x11 | 0x17 | ⚠️ **待核实** |

> 调制模式 ID 需对照 GWJ003-2015 PDF 原文确认正确值。

---

## 三、SOAP 接口规范

| 项目 | API 文档 | SRS | settings.py | 状态 |
|------|----------|-----|-------------|------|
| mon 命名空间 | `http://monitor.rrmp.gov.cn/services/` ✅ | ~~`example.com`~~ → ✅ | - | ✅ 已修正 |
| SOAP 1.1 路径 | `/services` ✅ | - | `/services` ✅ | ✅ |
| SOAP 1.2 路径 | `/services/v1` | - | 未实现 | ⚠️ |
| WSDL 路径 | `?wsdl` | - | 未实现 | ⚠️ |
| 成功响应格式 | `mon:Response` ✅ | ✅ | 已实现 ✅ | ✅ |
| SOAP Fault 格式 | `soap:Fault` ✅ | ✅ | 已实现 ✅ | ✅ |

---

## 四、settings.py 修正记录（2026-04-06）

### 4.1 补全的类型（新增）

| ID | 类型名称 | 说明 |
|----|----------|------|
| 0x19 | WBMONDF | 宽带监测测向 |
| 0x1E | WBMSCAN | 宽带扫描 |
| 0x22 | MODREC | 信号识别 |
| 0x23 | SINA | 信号告警 |
| 0x24 | ITUMEAS | ITU测量 |
| 0x29 | ACDF | 旋转云台 |
| 0x2B | DEMREC | 调制模式识别 |
| 0x2C | MULCHANANA | 双/多信道分析 |

### 4.2 更正的名称/注释

| ID | 旧名称 | 新名称 |
|----|--------|--------|
| 0x1C | WMON | WBFFTMon |
| 0x19 | TDANALYSIS | WBMONDF |

### 4.3 修正原因说明

- **0x19 (WBMONDF)**：协议文档定义 0x19=WBMONDF，SRS §6.1 原错误列在 0x25
- **0x1C (WBFFTMon)**：对应 SRS 服务名 WBFFTMon（宽带FFT观测），协议中对应 WMON
- **0x22 (MODREC)**：SRS §3.1.3 原错误写 0x34，已修正为协议值 0x22
- **0x28/0x29 (MULTICHAN/ACDF)**：SRS §6.1 原错误为 0x40/0x41，已按协议修正
- **0x2B (DEMREC)**：SRS §6.1 原错误为 0x43，已按协议修正
- **0x33 (FREQMEAS)**：SRS §6.1 原错误为 0x51，已修正

---

## 五、SRS 文档修正记录（2026-04-06）

### 5.1 §3.1.2 测向类服务

| 服务 | 修正前 | 修正后 | 说明 |
|------|--------|--------|------|
| WBDF | 0x25 | **0x19** | 对应协议 WBMONDF |

### 5.2 §3.1.3 信号分析类服务

| 服务 | 修正前 | 修正后 | 说明 |
|------|--------|--------|------|
| DigitalSignalRecDecode | 0x34 | **0x1D** | 对应协议 DIGDEM |
| ModRec | 0x43 | **0x2B** | 对应协议 DEMREC |
| DigDem | 0x29 | **0x1D** | 对应协议 DIGDEM |

### 5.3 §5.1 SOAP 命名空间

| 位置 | 修正前 | 修正后 |
|------|--------|--------|
| SOAPAction | `example.com` | `rrmp.gov.cn` |
| mon URI | `example.com` | `rrmp.gov.cn` |

### 5.4 §6.1 业务数据类型表

| 修正项 | 修正前 | 修正后 |
|--------|--------|--------|
| FREQMEAS | 0x51 | **0x33** |
| WBMONDF 位置 | 0x25 | **0x19** |
| MULTICHAN | 0x40 | **0x28** |
| ACDF | 0x41 | **0x29** |
| DEMREC | 0x43 | **0x2B** |
| 表顺序 | WMON 在 WBMONDF 后 | WMON(0x1C) 在 WBMONDF(0x19) 后 |

---

## 六、待核实项目（非紧急）

### 6.1 调制模式 ID

需对照 GWJ003-2015 PDF 原文确认 AM/SSB/DSB/OFDM/FSK/ASK 的正确 ID。

### 6.2 TDANALYSIS 类型 ID

- settings.py 暂时将 TDANALYSIS 放在 0x1A
- 协议文档中 0x1A 为 IFDFEXT（中频宽带测向）
- SRS §6.1 原来列 TDANALYSIS 在 0x19，但 0x19 按协议应为 WBMONDF

### 6.3 SRS §6.1 表与服务的对应关系

以下 SRS 服务名称在协议中未找到精确对应，需确认是否为别名或新服务：
- WBDF（SRS 服务名）= WBMONDF（协议名）？
- WBMONDF（SRS §6.1）= WBDF（协议名）？

---

**文档结束**
