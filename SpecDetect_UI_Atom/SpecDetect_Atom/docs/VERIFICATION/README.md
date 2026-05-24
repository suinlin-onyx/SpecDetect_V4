# 验证数据来源

本文档汇总了开发过程中用于验证的数据来源，按用途分类。

---

## 1. SOAP 请求响应对照

### 1.1 soap_proxy 透明代理日志

**路径**: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\conversion_output\`

**用途**: 记录请求与响应对应的完整结构体

**文件格式**:
- `{timestamp}_req.bin` - SOAP 请求原始数据
- `{timestamp}_res.bin` - 回调响应原始数据

**说明**: 每对文件对应一次完整的请求-响应交互

---

### 1.2 手动操作请求报文与回显

**路径**: `..\手动请求接口示例\` (同目录)

**用途**: 手动操作请求的报文与 test tool 回显对照

**子目录**:
- `接口soap请求报文/` - 发送的请求 XML
- `接口soap请求回调/` - 接收的回调响应 XML

**接口覆盖**:
| 接口 | 请求文件 | 回调文件 |
|------|----------|----------|
| B_FScan | B_FScan.xml | B_FScan.xml |
| B_PScan | B_PScan.xml | B_PScan.xml |
| B_MScan | B_MScan.xml | B_MScan.xml |
| B_QueryDeviceInfo | B_QueryDeviceInfo.xml | B_QueryDeviceInfo.xml |
| B_QueryFaciDevStat | B_QueryFaciDevStat.xml | B_QueryFaciDevStat.xml |
| B_SglFreqMeas | B_SglFreqMeas.xml | B_SglFreqMeas.xml |
| B_SglFreqDF | B_SglFreqDF.xml | B_SglFreqDF.xml |
| B_WBDF | B_WBDF.xml | B_WBDF.xml |
| B_FScanDF | B_FScanDF.xml | B_FScanDF.xml |
| B_StopMeas | B_StopMeas.xml | B_StopMeas.xml |

---

## 2. Stream 数据

### 2.1 soap_proxy 抓包日志

**路径**: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\logs\`

**用途**: 详细的 stream 流信息抓包

**文件格式**: `*_soappx_stream_*.log`

**说明**: 记录 streamsrc 数据推送的完整时序和帧数据

---

## 3. RMCP 协议解析

### 3.1 RMCP 抓包解析日志

**路径**: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\experimental\logs\rmcp_capture\`

**用途**: RMCP 协议的抓包和解析结果

**文件格式**:
- `capture_{port}_{timestamp}.log` - 原始抓包日志
- `capture_{port}_{timestamp}.json` - 结构化解析结果

**说明**: 包含 RMCPTP 帧的完整解析，可用于验证帧格式

---

## 4. 参考实现

### 4.1 已实现的功能程序

**路径**: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\experimental\emulated_atom.py`

**用途**: 作为重构的指引，实现的行为基准

**说明**: 所有接口的实现逻辑应与 emulated_atom.py 对齐

---

## 使用指南

### 开发新接口时

1. 查看 `接口soap请求报文/` 中对应接口的请求格式
2. 查看 `接口soap请求回调/` 中对应接口的响应格式
3. 参考 emulated_atom.py 的实现逻辑
4. 使用 soap_proxy 日志验证请求响应对

### 调试帧格式时

1. 查看 `rmcp_capture/` 中的抓包日志验证 RMCP 帧结构
2. 查看 `soap_proxy/logs/` 中的 stream 日志验证 streamsrc 帧结构

### 验证兼容性时

1. 对比 SpecDetect_Atom 与 emulated_atom.py 的输出
2. 使用 conversion_output 中的原始数据做精确对比

---

## 目录结构

```
VERIFICATION/
├── README.md                    # 本文件
└── (链接指向外部目录)

外部数据源 (不复制，仅链接):
├── SpecDetect_POC/
│   ├── soap_proxy/
│   │   ├── conversion_output/  # SOAP 请求响应对
│   │   └── logs/              # Stream 抓包
│   └── experimental/
│       ├── logs/rmcp_capture/ # RMCP 解析
│       └── emulated_atom.py   # 参考实现
│
└── 手动请求接口示例/
    ├── 接口soap请求报文/       # 请求 XML
    └── 接口soap请求回调/       # 响应 XML
```
