# Proxy-A 链路改造归档

> 创建日期：2026-04-08
> 改造目标：统一接口为 B_XXX 格式，响应格式与 Real Atom 一致

---

## 决策

**接口方案**：只使用一套 `B_XXX` 接口（方案A）

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

### 3. Proxy-A 请求构建统一

**改造后 Proxy-A 统一使用 `build_real_atom_request()`**

```
Client → Proxy-A → build_real_atom_request() → Mock Atom (9090)
                         ↓
                  使用 Real Atom 格式请求
                  (与 Real Atom 完全一致)
```

---

## 改造步骤

| # | 步骤 | 文件 | 状态 |
|---|------|------|------|
| 1 | Mock Atom 响应格式改造 | `main_atom.py` | ⬜ |
| 2 | Mock Atom 接口名称改造 | `main_atom.py` | ⬜ |
| 3 | Mock Atom 请求解析改造 | `main_atom.py` | ⬜ |
| 4 | Proxy-A 请求构建统一 | `routes.py` | ⬜ |

---

## 预期结果

改造完成后：
- Proxy-A (8080) → Mock Atom (9090) = 与 Real Atom 行为一致
- Proxy-B (8081) → Real Atom (8282) = Real Atom 行为
- 两者完全等价，可互换

---

## 相关文件

- `main_atom.py` - Mock Atom 主服务
- `routes.py` - Proxy 路由
- `protocol_builder.py` - RMCPTP 协议构建器
