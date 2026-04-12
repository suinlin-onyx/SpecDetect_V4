# SOAP ↔ RMCP 转换对照表 (Real Atom)

> 创建日期：2026-04-11
> 更新日期：2026-04-11

---

## 一、已确认的转换对应关系

### 1. SOAP操作 ↔ RMCPTP funcid

| SOAP 操作 | funcid | 状态 | 验证时间 |
|-----------|--------|------|----------|
| B_FScan | 15 | ✅ 已确认 | 2026-04-11 19:10 |
| B_FScanDF | 21 | ✅ 已确认 | 2026-04-11 18:35 |
| B_MScan | 14 | ✅ 已确认 | 2026-04-11 18:35 |
| B_MScanDF | 16 | ✅ 已确认 | - |
| B_PScan | 13 | ⚠️ 待验证 | - |
| B_SglFreqDF | 11 | ⚠️ 待验证 | - |
| B_SglFreqMeas | 12 | ⚠️ 待验证 | - |
| B_StopMeas | 32 | ✅ 已确认 | - |
| B_WBDF | 17 | ⚠️ 待验证 | - |
| B_QueryDeviceInfo | 10 | ⚠️ 待验证 | - |
| B_QueryFaciDevStat | - | ❌ 无funcid | - |

### 2. 参数映射 (B_FScan 示例)

**SOAP参数**:
```xml
<item name="startfreq" value="137MHz" />
<item name="stopfreq" value="173MHz" />
<item name="step" value="25kHz" />
<item name="gainctrl" value="AGC" />
<item name="rfworkmode" value="0" />
<item name="scanmode" value="0" />
```

**RMCP参数**: (待解析)

---

## 二、RMCP帧结构解析

### 1. RMCPTP帧头 (实测: 16 bytes + 额外字段)

| 字段 | 大小 | 说明 |
|------|------|------|
| dwLength | 4 bytes | 帧总长度 |
| (unknown) | 8 bytes | 用途未知 |
| nVersion | 1 byte | 版本号 (=7) |
| nMsgType | 1 byte | 消息类型 (90=REQUEST, 6=RESPONSE, 0=DATA) |
| nFlags | 1 byte | 标志 |
| nCheckSum | 2 bytes | 校验和 |
| (unknown) | 1 byte | 用途未知 |

### 2. B_FScan DATA帧结构 (实测验证)

**帧布局** (总长 1053 bytes):

| 偏移 | 大小 | 内容 | 示例值 |
|------|------|------|--------|
| 0 | 16 bytes | RMCP帧头 | - |
| 16 | 5 bytes | 业务头 | - |
| 21 | 8 bytes | 计数器 | 512, 0, 0, 0 (int16) |
| 29 | N*2 bytes | 频谱数据 | -525, -755, ... |
| - | - | 总计 | 512点 = 1024 bytes |

### 3. 频谱数据

- 类型: int16 little-endian
- 转换: `dBm = raw_value / 10`
- 每帧点数: 512 (前两帧), 417 (第三帧)
- 总计: 1441点

---

## 三、SOAP XML → RMCP二进制 转换状态

### 已完成 ✅

| 项目 | 说明 | 验证 |
|------|------|------|
| funcid映射 | SOAP funcid → RMCP funcid | ✅ 1910数据验证 |
| 参数提取 | 从SOAP XML解析startfreq, stopfreq, step等 | ✅ 1910数据验证 |
| SOAP XML编码 | GB2312编码 | ✅ 嵌入式XML验证 |
| XML嵌入位置 | 从字节18开始 | ✅ |

### 部分完成 ⚠️

| 项目 | 状态 | 说明 |
|------|------|------|
| 帧头构建 | 待实现 | dwLength, nCheckSum等计算 |
| 频率编码 | 已验证 | 参数直接以XML形式嵌入，不需要二进制编码 |
| 字符串编码 | 已验证 | GB2312 |

### 未完成 ❌

| 项目 | 说明 |
|------|------|
| 完整二进制帧构建 | 需要完整的帧头结构定义 |

---

## 四、RMCP → SOAP 转换状态

### 已完成 ✅

| 项目 | 说明 | 验证 |
|------|------|------|
| DATA帧解析 | 提取频谱数据 (512/417点) | ✅ 1910数据验证 |
| 频谱转换 | raw/10 = dBm | ✅ 误差<1dBm |
| 频率计算 | startfreq + offset * step | ✅ |
| 帧头解析 | 从hex提取dwLength, nMsgType | ✅ |
| XML提取 | 从REQUEST帧提取SOAP XML | ✅ |

### 部分完成 ⚠️

| 项目 | 状态 | 说明 |
|------|------|------|
| 帧类型识别 | nMsgType已可识别 | REQUEST/RESPONSE/DATA |
| 业务数据类型 | nBdType已可识别 | 0x0F=FSCAN |
| RMCP头解析 | 部分字段位置已知 | nVersion,nMsgType,nFlags位置确认 |

### 未完成 ❌

| 项目 | 说明 |
|------|------|
| RMCP → SOAP响应构建 | 如何将DATA帧数据封装回SOAP格式 |

---

## 五、验证数据

| 采集时间 | SOAP日志 | RMCP日志 | 说明 |
|----------|----------|----------|------|
| 19:10:43 | `requests_20260411_1910/8ce334c8_req.xml` | `capture_20260411_191028.json` | B_FScan, 137-173MHz, 25kHz |
| 18:35:00 | `requests_20260411_1835/*.xml` | `capture_20260411_183353.json` | B_FScanDF |

---

## 六、下一步

### 已完成 ✅
- [x] SOAP XML参数解析
- [x] RMCP DATA帧频谱解析
- [x] 转换公式验证 (raw/10 = dBm)
- [x] Python转换模块框架

### 进行中 🔄
- [ ] 完整RMCP帧头解析（各字段位置确认）

### 待完成 📋
- [ ] 完成SOAP XML → RMCP REQUEST帧构建
- [ ] RMCP DATA帧 → streamsrc格式转换
- [ ] streamsrc → TestTool数据格式解析

---

## 七、Python转换模块

**文件位置**: `SpecDetect_POC/soap_proxy/soap_rmcp_converter.py`

**功能**:
- `parse_soap_request(xml)` - 解析SOAP XML提取参数
- `parse_rmcp_request_frame(hex)` - 解析RMCP REQUEST帧，提取嵌入式SOAP XML
- `parse_rmcp_data_frame(hex, startfreq, step)` - 解析DATA帧，返回频谱数据

**验证数据**:
```bash
python3 soap_rmcp_converter.py
```

**输出示例**:
```
=== SOAP 参数解析结果 ===
  funcid: 15
  startfreq: 137000000
  stopfreq: 173000000
  step: 25000

=== RMCP DATA 帧解析 ===
  Frame 0: 512 points
    First 5 dBm: [-52.5, -75.5, -77.2, -61.8, -57.7]
```

---

**最后更新**: 2026-04-11
