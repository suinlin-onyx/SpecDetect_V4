# Proxy-A 链路改造归档

> 创建日期：2026-04-08
> 更新日期：2026-04-08
> 改造目标：Mock Atom 作为 Real Atom 的等价实现，转发 SOAP → RMCPTP → Real Device

---

## 决策

**接口方案**：只使用一套 `B_XXX` 接口（方案A）

---

## 目标架构

```
Client → Proxy-A(8080) → Mock Atom(9090) → Real Device(172.18.114.33:9999)
                                         ↓
                                    RMCPTP v2.0 二进制协议
```

### 服务地址映射

| 服务 | 地址 | 说明 |
|------|------|------|
| Real Atom | 172.18.114.33:8282 | SOAP 服务（远程） |
| Real Device | 172.18.114.33:9999 | RMCPTP 设备（远程） |
| Mock Atom | 127.0.0.1:9090 | 本地 SOAP 服务 |
| Real Device (目标) | 172.18.114.33:9999 | Mock Atom 转发目标 |

**关键点**：Mock Atom 接收 SOAP 请求，转换为 RMCPTP 命令，直接发送给 Real Device。

---

## 改造目标

### 1. Mock Atom 响应格式 → Real Atom 格式

**当前格式** (Mock Atom):
```xml
<soap:Body>
  <mon:Response success="true">
    <mon:frequency>100000000</mon:frequency>
  </mon:Response>
</soap:Body>
```

**目标格式** (Real Atom):
```xml
<soapenv:Header>
  <srrc:ProviderResponse>
    <srrc:bizResCd>BIZ-000001</srrc:bizResCd>
    <srrc:bizResText>调用成功</srrc:bizResText>
  </srrc:ProviderResponse>
</soapenv:Header>
<soapenv:Body>
  <srrc:responsebody>
    <srrc:result>
      <srrc:frequency>100000000</srrc:frequency>
    </srrc:result>
  </srrc:responsebody>
</soapenv:Body>
```

### 2. Mock Atom 接口名称 → B_XXX 格式

| 旧接口 | 新接口 |
|--------|--------|
| `StartMeasure` | `B_SglFreqMeas` |
| `StartScan` | `B_FScan` |
| `StartDirection` | `B_SglFreqDF` |
| `StartIFAnalysis` | `B_IFAnalysis` |
| `StartIFDirection` | `B_IFDirection` |

### 3. Mock Atom 转发目标 → Real Device

**配置变更** (`settings.py`):
```python
SERVICES = {
    'atom': {
        'device_host': '172.18.114.33',  # Real Device 地址
        'device_port': 9999              # Real Device RMCPTP 端口
    }
}
```

---

## 改造步骤

| # | 步骤 | 文件 | 状态 |
|---|------|------|------|
| 1 | Mock Atom 响应格式改造 | `main_atom.py` | ⬜ |
| 2 | Mock Atom 接口名称改造 | `main_atom.py` | ⬜ |
| 3 | Mock Atom 请求解析改造 (srrc命名空间) | `main_atom.py` | ⬜ |
| 4 | device_client 配置指向 Real Device | `settings.py` | ⬜ |
| 5 | Proxy-A 请求构建统一 | `routes.py` | ⬜ |

---

## 预期结果

改造完成后：
- Proxy-A (8080) → Mock Atom (9090) → Real Device (172.18.114.33:9999)
- Mock Atom 等价于 Real Atom（只做 SOAP → RMCPTP 转换）

---

## 相关文件

- `main_atom.py` - Mock Atom 主服务
- `routes.py` - Proxy 路由
- `protocol_builder.py` - RMCPTP 协议构建器
- `settings.py` - 服务配置
