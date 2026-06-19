# TASK_20260619: 错误响应格式对齐 — max_sessions 冲突回调修复

**日期**: 2026-06-19
**优先级**: HIGH
**范围**: SpecDetect_Atom 的 SOAP 错误响应格式与真实 Atom (RXAtomSvcV3) 对齐

---

## 背景

真实 Atom 在 B_FScan 设备使用冲突时返回结构化错误：

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:srrc="http://www.srrc.org.cn">
  <soapenv:Header>
    <srrc:ProviderResponse>
      <srrc:bizResCd>BIZ-00002-conflict</srrc:bizResCd>
      <srrc:bizResText>设备使用冲突</srrc:bizResText>
    </srrc:ProviderResponse>
  </soapenv:Header>
  <soapenv:Body>
    <srrc:responsebody>
      <srrc:error>
        <srrc:type>cancel</srrc:type>
        <srrc:code>BIZ-00002-conflict</srrc:code>
        <srrc:text>设备使用冲突</srrc:text>
      </srrc:error>
    </srrc:responsebody>
  </soapenv:Body>
</soapenv:Envelope>
```

SpecDetect_Atom 当前 `build_error_response` 给出的是不兼容格式：

```xml
<srrc:error>达到最大 session 数 1</srrc:error>
<!-- 缺少 responsebody 包裹、缺少 type/code/text 子元素 -->
<!-- bizResCd 写成 BIZ-000001（成功码） -->
```

---

## 问题清单

### P0 — 错误响应结构不兼容

| # | 位置 | 当前 | 期望 |
|---|------|------|------|
| 1 | `_error.xml` | `<srrc:error>{error_msg}</srrc:error>` | `<srrc:responsebody><srrc:error><srrc:type>{error_type}</srrc:type><srrc:code>{error_code}</srrc:code><srrc:text>{error_text}</srrc:text></srrc:error></srrc:responsebody>` |
| 2 | `_envelope.xml` Header | 多余 namespace (`SOAP-ENC`, `xsi`, `xsd`, `ns1`) | 精简为仅保留 `soapenv` + `srrc`（非必须但建议） |
| 3 | `device_preset.py:373` | `bizResCd='BIZ-000001'` | 应透传 `{bizrescd}` |
| 4 | `device_preset.py:374` | `bizResText='调用失败'` | 应透传 `{bizrestext}` |

### P1 — build_error_response 签名扩展

```python
# 当前
def build_error_response(self, error_msg: str) -> bytes:

# 期望
def build_error_response(self, error_msg: str,
                         error_code: str = 'BIZ-00002-conflict',
                         error_type: str = 'cancel',
                         biz_res_cd: str = 'BIZ-00002-conflict',
                         biz_res_text: str = '设备使用冲突') -> bytes:
```

### P2 — B_FScan.xml 字段顺序微调（建议）

| 当前模板顺序 | 参考顺序 |
|---|---|
| ...equid → equpara → taskid → outputchannel | ...equid → **taskid** → equpara → outputchannel |

items 内部顺序（功能无影响，建议对齐以便 diff）：
```
当前: rfworkmode, stopfreq, scanmode, gain, startfreq, step
参考: startfreq, stopfreq, step, gain, rfworkmode, scanmode
```

---

## 涉及文件

| 文件 | 修改类型 |
|------|----------|
| `src/preset/templates/_error.xml` | **重写** — 改为结构化 XML |
| `src/preset/device_preset.py` | **修改** — `build_error_response` 签名 + 逻辑 |
| `src/preset/templates/_envelope.xml` | **修改** — 精简 namespace（可选） |
| `src/preset/templates/B_FScan.xml` | **修改** — taskid 位置 + items 顺序（可选） |
| `src/atom/service.py` | **修改** — 调用处传 error_code 参数 |

---

## 调用处映射

| service.py 调用 | 建议 error_code | 建议 error_text |
|---|---|---|
| 创建 session 超限 (L239/L297/L649/L703/L755/L811/L871) | `BIZ-00002-conflict` | `设备使用冲突` |
| Sink 缺少 host/port (L272/L681/L848) | `BIZ-000002` | `缺少 outputchannel 参数` |
| Sink 连接失败 (L289/L696/L864) | `BIZ-000002` | `Sink 连接失败: {e}` |
| 设备信息未找到 (L939/L975) | `BIZ-000002` | `设备信息未找到` |
| L1035 请求失败 | `BIZ-000002` | `请求失败` |

---

## 测试要点

1. **max_sessions=1 时发起两个 B_FScan** → 第二个返回的 XML 与参考 XML 结构一致
2. **XPath 验证**: `//srrc:responsebody/srrc:error/srrc:code` = `BIZ-00002-conflict`
3. **XPath 验证**: `//srrc:responsebody/srrc:error/srrc:type` = `cancel`
4. **Header 验证**: `//srrc:ProviderResponse/srrc:bizResCd` = `BIZ-00002-conflict`
5. **成功路径无损**: 正常 B_FScan 响应格式不变
6. **其他接口错误**: B_PScan / B_MScan / B_SglFreqMeas 超限时同样返回结构化错误

---

## 审查要点

1. `build_error_response` 的默认参数值是否符合 GWJ003 规范
2. `_envelope.xml` namespace 精简是否影响现有客户端解析
3. 所有 `build_error_response` 调用点是否都有了合适的 error_code
4. 向后兼容 — 调用方如果按纯文本解析 `<srrc:error>` 需要同步更新
