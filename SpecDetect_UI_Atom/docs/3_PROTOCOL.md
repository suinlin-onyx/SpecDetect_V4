# SpecDetect_UI_Atom 协议细节

**创建日期**: 2026-04-16
**更新日期**: 2026-04-24

---

## 3.1 SOAP接口

### 3.1.1 SOAP请求格式（Client → Atom）

```
POST /B_FScan HTTP/1.1
Host: 127.0.0.1:8282
Content-Type: text/xml; charset=utf-8
SOAPAction: B_FScan
Content-Length: ...

<soapenv:Envelope xmlns:soapenv="..." xmlns:srrc="...">
<soapenv:Body><srrc:requestbody>
  <srrc:appid>123456</srrc:appid>
  <srrc:userid>RX_admin</srrc:userid>
  <srrc:mfid>53090001140012</srrc:mfid>
  <srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
  <srrc:equpara>
    <srrc:items>
      <srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
      <srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
      <srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
    </srrc:items>
  </srrc:equpara>
  <srrc:outputchannel>
    <srrc:mode>source</srrc:mode>
    <srrc:datachannel>stream</srrc:datachannel>
  </srrc:outputchannel>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>
```

### 3.1.2 SOAP响应格式（Atom → Client）

```xml
<soapenv:Envelope xmlns:soapenv="..." xmlns:srrc="...">
<soapenv:Body><srrc:responsebody>
  <srrc:result><srrc:success>true</srrc:success></srrc:result>
  <srrc:taskid>EA-1713340800</srrc:taskid>
  <srrc:outputchannel>
    <srrc:mode>source</srrc:mode>
    <srrc:datachannel>stream</srrc:datachannel>
    <srrc:host>127.0.0.1</srrc:host>
    <srrc:port>18012</srrc:port>
    <srrc:stc>12345678</srrc:stc>
  </srrc:outputchannel>
</srrc:responsebody></soapenv:Body></soapenv:Envelope>
```

**说明**：`outputchannel.port` 是端口分配机制。当前双方配置一致，响应中确认。

---

## 3.2 streamsrc帧格式

### 3.2.1 FSCAN帧结构（1086字节）

```
Offset 0-3:    Sync      = 0xEEEEEEEE (4B BE)
Offset 4-5:    VER       = 0x0100 (2B LE, 小端)
Offset 6-9:    STC       (4B LE, 同步通道号)
Offset 10-17:  TS        = FILETIME (8B BE, 大端)
Offset 18-19:  PL        = 1062 (2B BE, payload长度)
Offset 20-21:  EL        = 0 (2B BE, 错误码)
Offset 22-23:  PAD       = 0 (2B)
Offset 24-25:  DT        = 12 (1B, 数据类型: FSCAN)
Offset 26-47:  私有元数据 (20B)
Offset 48-1085: 频谱数据 (512×int16 LE, dBm×10)
```

### 3.2.2 FSCAN帧元数据详情

| 字段        | offset | 大小  | 说明                                             |
| --------- | ------ | --- | ---------------------------------------------- |
| DT        | 24     | 1B  | 12 = FSCAN                                     |
| DL        | 25     | 1B  | 99                                             |
| indicator | 48-49  | 2B  | 0x0026 (Band1), 0x0126 (Band2), 0x0168 (Band3) |
| meta[0]   | 48-49  | 2B  | start_index                                    |
| meta[1]   | 50-51  | 2B  | 0                                              |
| meta[2]   | 52-53  | 2B  | 0                                              |
| meta[3]   | 54-55  | 2B  | 帧长度                                            |
| meta[4]   | 56-57  | 2B  | 频率范围                                           |
| meta[5]   | 58-59  | 2B  | 频点数量 (512)                                     |
| meta[6]   | 60-61  | 2B  | 0                                              |

### 3.2.3 三段式帧结构

| Band  | PL   | 总长度   | 帧信道数 | 频率范围             |
| ----- | ---- | ----- | ---- | ---------------- |
| Band1 | 1062 | 1086B | 512点 | 137.0-149.775MHz |
| Band2 | 1062 | 1086B | 512点 | 149.8-162.575MHz |
| Band3 | 872  | 896B  | 417点 | 162.6-173.0MHz   |

### 3.2.4 MSCAN帧结构（45字节）

```
Offset 0-3:    Sync      = 0xEEEEEEEE (4B BE)
Offset 4-5:    VER       = 1 (2B LE)
Offset 6-9:    STC       (4B LE)
Offset 10-17:  TS        = FILETIME (8B BE)
Offset 18-19:  PL        = 21 (2B BE)
Offset 20-21:  EL        = 0 (2B BE)
Offset 22-23:  PAD       = 0 (2B)
Offset 24:     DT        = 13 (MSCAN)
Offset 25:     DL        = 16
Offset 26-29:  freq_count = 1 (4B)
Offset 30-37:  固定值     (8B)
Offset 38-41:  固定值     (4B)
Offset 43-44:  电平值     (2B LE)
```

---

## 3.3 RMCP帧格式

### 3.3.1 RMCPTP帧头（18字节）

```
Offset 0-3:    dwLength  (uint32 LE, 报文总长度)
Offset 4-11:   tmStamp   (uint64 LE, FILETIME)
Offset 12-13:  nVersion  (uint16 BE, =7)
Offset 14:      nMsgType  (uint8, 90=REQUEST, 0/29=DATA)
Offset 15:      nFlags    (uint8)
Offset 16-17:   nCheckSum (uint16 LE)
```

### 3.3.2 Checksum算法

```
1. fold32: 将tmStamp按32位折叠
2. fold16: 将结果再次折叠为16位
3. complement: 取反
```

### 3.3.3 RMCP FSCAN Payload（来自设备）

```
byte[0]      nBdType = 0x0F (15 = FSCAN)
byte[1:2]    reserved
byte[3:10]   counters[4] (4 × int16 LE), counters[0] = nArrays
byte[11:]    levels (int16 LE, dBm×10, 每帧512点)
```

---

## 3.4 接口参数详解

### 3.4.1 B_FScan / B_PScan 参数

| 参数名        | 类型     | 说明        | 默认值       |
| ---------- | ------ | --------- | --------- |
| startfreq  | double | 起始频率 (Hz) | 137000000 |
| stopfreq   | double | 结束频率 (Hz) | 173000000 |
| step       | double | 频率步进 (Hz) | 25000     |
| gain       | string | 增益模式      | AGC       |
| rfworkmode | int    | 射频工作模式    | 0         |
| keepmode   | int    | 保持模式      | 0         |

### 3.4.2 B_MScan 参数

| 参数名       | 类型     | 说明        | 默认值       |
| --------- | ------ | --------- | --------- |
| frequency | double | 测量频率 (Hz) | 100000000 |
| ifbw      | string | 中频带宽      | (可选)      |

---

## 3.5 协议确认行为

以下是从实测中发现的重要协议细节：

| #   | 发现                                  | 说明                                       |
| --- | ----------------------------------- | ---------------------------------------- |
| P1  | XML必须gb2312编码                       | 发送到设备的请求必须是gb2312编码                      |
| P2  | nMsgType=0 用于数据帧                    | 不是协议文档中的29/95                            |
| P3  | nVersion大端存储                        | little-endian惯例的例外                       |
| P4  | dwLength = 帧头18 + payload           | 含XML+null                                |
| P5  | B_StopMeas仅发给rmcp_proxy             | 不转发为RMCP到设备                              |
| P6  | Checksum算法：fold32→fold16→complement |                                          |
| P7  | streamsrc帧：1086B                    | Sync(4B) + Header(44B) + Spectrum(1024B) |
| P8  | 频谱数据交替字节模式                          | [dBm][0xFF][dBm][0xFF]...                |

## 3.6 SOAP ↔ RMCP 接口映射关系

**重要发现**: SOAP接口(funcid)与RMCP回调(nBdType)是**两套独立的编号体系**，同一功能在两套体系中编号可能不同。

### 完整映射表 (实测校正版)

| SOAP funcid | SOAP接口名       | XML关键参数                 | RMCP nBdType (Hex) | RMCP nBdType (Dec) | RMCP回调类型   | 状态   |
| ----------- | ------------- | ----------------------- | ------------------ | ------------------ | ---------- | ---- |
| 11          | B_SglFreqMeas | demodmode=FM            | 0x0B               | 11                 | IFANALYSIS | ✅ 实测 |
| 11          | B_SglFreqMeas | frequency (无demodmode)  | 0x0E               | 14                 | SGLFREQ    | ✅ 实测 |
| 14          | B_MScan       | frequency/ifbw          | 0x0E               | 14                 | SGLFREQ    | ✅ 实测 |
| 15          | B_FScan       | startfreq/stopfreq/step | 0x0F               | 15                 | FSCAN      | ✅ 实测 |
| 15          | B_FScan       | startfreq/stopfreq/step | 0x10               | 16                 | DSCAN      | ✅ 实测 |
| 16          | B_PScan       | startfreq/stopfreq/step | 0x01               | 1                  | DSCAN      | ✅ 实测 |
| 16          | B_PScan       | startfreq/stopfreq/step | 0x10               | 16                 | RESP (响应帧) | ✅ 实测 |

### 实测确认的 funcid → nBdType 映射

| funcid | XML参数                   | nBdType | 数据特征                |
| ------ | ----------------------- | ------- | ------------------- |
| 11     | demodmode=FM            | 0x0B    | IFANALYSIS, demod分析 |
| 11     | frequency               | 0x0E    | SGLFREQ             |
| 14     | frequency/ifbw          | 0x0E    | SGLFREQ             |
| 15     | startfreq/stopfreq/step | 0x0F    | FSCAN (512点)        |
| 15     | startfreq/stopfreq/step | 0x10    | DSCAN (1441点)       |
| 16     | startfreq/stopfreq/step | 0x01    | PSCAN (1671B帧)      |

### 文档定义 vs 实测差异

| 接口         | SOAP funcid | RMCP nBdType (文档) | 实测 nBdType    | 差异    |
| ---------- | ----------- | ----------------- | ------------- | ----- |
| SGLFREQ    | 11          | 10 (0x0A)         | **14 (0x0E)** | 编号不同  |
| IFANALYSIS | -           | 11 (0x0B)         | 11 (0x0B)     | ✅ 一致  |
| B_MScan    | 14          | MSACN (14)        | **0x0E (14)** | 类型名不同 |
| FSCAN      | 15          | 15 (0x0F)         | 15 (0x0F)     | ✅ 一致  |
| DSCAN      | 16          | 16 (0x10)         | 16 (0x10)     | ✅ 一致  |
| PSCAN      | 17          | 17 (0x11)         | **1 (0x01)**  | 编号不同  |

### 关键结论

1. **funcid=15 触发多种回调**: B_FScan请求会同时返回 FSCAN(nBdType=0x0F) 和 DSCAN(nBdType=0x10) 数据
2. **设备固件差异**: 部分接口的nBdType与文档定义不一致
3. **B_PScan**: 返回 nBdType=0x01(PSCAN数据) 和 nBdType=0x10(响应帧)

---

## 3.7 相关文档

| 文档                                         | 说明   |
| ------------------------------------------ | ---- |
| [1_REQUIREMENTS.md](1_REQUIREMENTS.md)     | 需求概述 |
| [2_ARCHITECTURE.md](2_ARCHITECTURE.md)     | 架构设计 |
| [4_IMPLEMENTATION.md](4_IMPLEMENTATION.md) | 实现文档 |
| [5_ISSUES.md](5_ISSUES.md)                 | 问题记录 |
| [5_ISSUES.md](5_ISSUES.md)                 | 问题记录 |
