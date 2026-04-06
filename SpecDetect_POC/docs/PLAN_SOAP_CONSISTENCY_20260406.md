# SOAP协议一致性检验与修复计划

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 1.0 | 2026-04-06 | Claude | 初次归档 |

---

## 1. 背景

当前Proxy→Atom通信已从HTTP/JSON改为SOAP/XML，但距离完全符合文档要求仍有差距。

### 1.1 当前实现状态

| 项目 | 状态 | 说明 |
|------|------|------|
| SOAP协议基础 | ⚠️ 部分 | 基本的解析和响应已实现 |
| AuthHeader认证 | ❌ 未实现 | Header中的Token/Timestamp/Signature被忽略 |
| 响应格式 | ❌ 不符合 | 缺少ResultCode/ResultMessage/Data包装 |
| SOAP Fault | ❌ 未实现 | 错误响应使用普通Response而非SOAP Fault |
| WSDL | ❌ 未实现 | 无接口描述文件 |

---

## 2. SOAP一致性检验清单

### 2.1 检验范围

```
SOAP协议一致性测试
├── 1. SOAP信封结构
│   ├── [ ] 命名空间正确 (http://schemas.xmlsoap.org/soap/envelope/)
│   ├── [ ] Body元素存在
│   └── [ ] Header元素解析（文档要求）
│
├── 2. 认证头 (AuthHeader) - P0
│   ├── [ ] Token字段解析
│   ├── [ ] Timestamp字段解析
│   ├── [ ] Signature字段解析
│   └── [ ] 验证逻辑（拒绝无效Token）
│
├── 3. 请求操作
│   ├── [ ] StartMeasure / SglFreqMeasure
│   ├── [ ] StartScan / FScan
│   ├── [ ] StartDirection / SglFreqDF
│   ├── [ ] StartIFAnalysis / IFAnalysis
│   └── [ ] StartIFDirection / IFDF
│
├── 4. 响应格式 - P0
│   ├── [ ] ResultCode 元素存在
│   ├── [ ] ResultMessage 元素存在
│   ├── [ ] Data 包装元素
│   └── [ ] 命名空间前缀 (mon:)
│
├── 5. 错误处理 (SOAP Fault) - P1
│   ├── [ ] faultcode 元素
│   ├── [ ] faultstring 元素
│   ├── [ ] detail 元素
│   └── [ ] ErrorCode / ErrorMessage
│
└── 6. WSDL服务描述 - P2
    └── [ ] ?wsdl 端点
```

### 2.2 文档要求的响应格式

**正确响应（文档要求）：**
```xml
<mon:Response xmlns:mon="http://monitor.rrmp.gov.cn/services/">
    <mon:ResultCode>0</mon:ResultCode>
    <mon:ResultMessage>Success</mon:ResultMessage>
    <mon:Data>
        <mon:Frequency>95800000</mon:Frequency>
        <mon:SignalLevel>-45.25</mon:SignalLevel>
    </mon:Data>
</mon:Response>
```

**当前实际响应：**
```xml
<Response success="true">
    <frequency>100000000.0</frequency>
    <bandwidth>120000.0</bandwidth>
    <amplitude>-59.077354431152344</amplitude>
    <success>True</success>
</Response>
```

---

## 3. 修复优先级

| 优先级 | 项目 | 说明 |
|--------|------|------|
| **P0** | AuthHeader认证 | Token/Timestamp/Signature验证 |
| **P0** | 响应格式 | ResultCode/ResultMessage/Data包装 |
| **P1** | SOAP Fault | soap:Fault标准错误格式 |
| **P2** | WSDL | 接口描述文件生成 |

---

## 4. 检验命令

### 4.1 测试带AuthHeader的请求

```bash
curl -X POST http://localhost:8080/soap \
  -H "Content-Type: text/xml; charset=utf-8" \
  -d '<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:mon="http://monitor.rrmp.gov.cn/services/">
  <soap:Header>
    <mon:AuthHeader>
      <mon:Token>test_token</mon:Token>
      <mon:Timestamp>2026-04-06T12:00:00Z</mon:Timestamp>
      <mon:Signature>abc123</mon:Signature>
    </mon:AuthHeader>
  </soap:Header>
  <soap:Body>
    <mon:StartMeasure>
      <mon:Frequency>100000000</mon:Frequency>
      <mon:Bandwidth>120000</mon:Bandwidth>
    </mon:StartMeasure>
  </soap:Body>
</soap:Envelope>'
```

### 4.2 期望的响应格式

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:mon="http://monitor.rrmp.gov.cn/services/">
  <soap:Body>
    <mon:Response>
      <mon:ResultCode>0</mon:ResultCode>
      <mon:ResultMessage>Success</mon:ResultMessage>
      <mon:Data>
        <mon:Frequency>100000000</mon:Frequency>
        <mon:SignalLevel>-59.08</mon:SignalLevel>
      </mon:Data>
    </mon:Response>
  </soap:Body>
</soap:Envelope>
```

### 4.3 错误响应（SOAP Fault）

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Server</faultcode>
      <faultstring>设备未连接</faultstring>
      <detail>
        <mon:ErrorDetail xmlns:mon="http://monitor.rrmp.gov.cn/services/">
          <mon:ErrorCode>3001</mon:ErrorCode>
          <mon:ErrorMessage>设备未连接</mon:ErrorMessage>
        </mon:ErrorDetail>
      </detail>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>
```

---

## 5. 执行步骤

| 步骤 | 内容 | 产出物 |
|------|------|--------|
| 1 | 编写SOAP一致性测试用例 | `tests/test_soap_consistency.py` |
| 2 | 运行测试，生成检验报告 | 哪些通过/失败 |
| 3 | 修复P0问题（认证+响应格式） | 通过P0测试 |
| 4 | 修复P1问题（SOAP Fault） | 通过P1测试 |
| 5 | 修复P2问题（WSDL） | 完成所有测试 |
| 6 | 再次运行完整测试 | 最终验证 |

---

## 6. 待确认事项

| 项目 | 说明 | 状态 |
|------|------|------|
| 周期性交互 | 心跳/数据上报/通知 | 待用户确认 |
| 认证方式 | Token验证具体规则 | 待定义 |
| 错误码 | 2001-2004, 3002/3003/3005, 4001-4003/4005-4006 | 待实现 |

---

**计划制定**: 2026-04-06
**下一步**: 执行步骤1 - 编写SOAP一致性测试用例
