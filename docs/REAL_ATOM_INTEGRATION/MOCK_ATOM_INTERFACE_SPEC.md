# Mock Atom 接口规范文档

> 创建日期：2026-04-08
> 更新日期：2026-04-08
> 目标：以 Real Atom 为标准，改造 Mock Atom 实现完整 SOAP 接口

---

## 1. 接口总览

| # | 接口 | equpara结构 | outputchannel | taskid |
|---|------|-------------|---------------|--------|
| 1 | B_QueryDeviceInfo | xsi:nil | 否 | 否 |
| 2 | B_QueryFaciDevStat | xsi:nil | 否 | 否 |
| 3 | B_StopMeas | xsi:nil + taskid | 否 | 回显 |
| 4 | B_FScan | groupitems | 是 | 是 |
| 5 | B_FScanDF | items | 是 | 是 |
| 6 | B_MScan | groupitems | 是 | 是 |
| 7 | B_MScanDF | items | 是 | 是 |
| 8 | B_PScan | items | 是 | 是 |
| 9 | B_SglFreqMeas | items | 是 | 是 |
| 10 | B_SglFreqDF | items | 是 | 是 |
| 11 | B_WBDF | items | 是 | 是 |

---

## 2. 请求格式

### 2.1 查询接口（无outputchannel）

```xml
<srrc:requestbody>
  <srrc:appid>123456</srrc:appid>
  <srrc:userid>RX_admin</srrc:userid>
  <srrc:priority>9</srrc:priority>
  <srrc:executetime>0</srrc:executetime>
  <srrc:mfid>53090001140012</srrc:mfid>
  <srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
  <srrc:equpara xsi:nil="true"/>
</srrc:requestbody>
```

### 2.2 执行接口 - groupitems（B_FScan, B_MScan）

```xml
<srrc:equpara>
  <srrc:groupitems>
    <srrc:groupitem>
      <srrc:groupid>1</srrc:groupid>
      <srrc:items>
        <srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
        <srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
        ...
      </srrc:items>
    </srrc:groupitem>
  </srrc:groupitems>
</srrc:equpara>
<srrc:outputchannel>
  <srrc:mode>source</srrc:mode>
  <srrc:datachannel>stream</srrc:datachannel>
</srrc:outputchannel>
```

### 2.3 执行接口 - items（B_SglFreqMeas, B_PScan, B_SglFreqDF, B_WBDF, B_MScanDF）

```xml
<srrc:equpara>
  <srrc:items>
    <srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
    ...
  </srrc:items>
</srrc:equpara>
<srrc:outputchannel>
  <srrc:mode>source</srrc:mode>
  <srrc:datachannel>stream</srrc:datachannel>
</srrc:outputchannel>
```

### 2.4 B_StopMeas

```xml
<srrc:equpara xsi:nil="true"/>
<srrc:taskid>C7BF3346-3306-11F1-8000-00E05E68066A</srrc:taskid>
```

---

## 3. 响应格式

### 3.1 成功响应

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
      <srrc:appid>123456</srrc:appid>
      <srrc:userid>RX_admin</srrc:userid>
      <srrc:priority>9</srrc:priority>
      <srrc:executetime>0</srrc:executetime>
      <srrc:mfid>53090001140012</srrc:mfid>
      <srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
      <srrc:equpara>...回显...</srrc:equpara>
      <srrc:taskid>UUID-FORMAT</srrc:taskid>
      <srrc:outputchannel>
        <srrc:mode>source</srrc:mode>
        <srrc:datachannel>stream</srrc:datachannel>
        <srrc:host>127.0.0.1</srrc:host>
        <srrc:port>9000</srrc:port>
        <srrc:stc>TIMESTAMP</srrc:stc>
      </srrc:outputchannel>
    </srrc:result>
  </srrc:responsebody>
</soapenv:Body>
```

### 3.2 失败响应

```xml
<soapenv:Header>
  <srrc:ProviderResponse>
    <srrc:bizResCd>BIZ-000002</srrc:bizResCd>
    <srrc:bizResText>错误描述</srrc:bizResText>
  </srrc:ProviderResponse>
</soapenv:Header>
<soapenv:Body>
  <srrc:responsebody>
    <srrc:error>
      <srrc:type>cancel</srrc:type>
      <srrc:code>ERROR_CODE</srrc:code>
      <srrc:text>错误描述</srrc:text>
    </srrc:error>
  </srrc:responsebody>
</soapenv:Body>
```

---

## 4. 错误码定义

| 错误类型 | bizResCd | 说明 |
|----------|----------|------|
| 成功 | BIZ-000001 | 调用成功 |
| 设备离线 | BIZ-000002 | 设备未连接（check_device_connected 失败） |
| 设备使用冲突 | BIZ-00002-conflict | 设备被其他任务占用 |
| 设备错误 | BIZ-000002 | RMCPTP 调用失败 |
| 参数错误 | BIZ-000002 | 请求参数无效 |
| 未知错误 | BIZ-000002 | 其他错误 |

---

## 5. outputchannel 配置

| 字段 | 值 |
|------|-----|
| mode | source |
| datachannel | stream |
| host | 127.0.0.1 |
| port | 9000 |
| stc | Unix timestamp (秒) |

---

## 6. taskid 格式

使用 Real Atom 格式：
```
C7BF3346-3306-11F1-8000-00E05E68066A
```

格式说明：
- 前8位：时间低32位
- 中4位：时间中16位
- 再4位：版本+时间高4位
- 后12位：MAC地址或其他节点标识

**实现**：使用 `uuid.uuid4()` 生成后取其大写格式（去掉横杠）

---

## 7. B_QueryDeviceInfo 完整 featurelist

Real Atom 返回的 featurelist 包含每个接口的参数定义：

```xml
<srrc:featurelist>
  <srrc:feature>
    <srrc:code>B_QueryDeviceInfo</srrc:code>
    <srrc:input></srrc:input>
  </srrc:feature>
  <srrc:feature>
    <srrc:code>B_SglFreqMeas</srrc:code>
    <srrc:input>
      <srrc:parameter>
        <srrc:name>frequency</srrc:name>
        <srrc:type>double</srrc:type>
        <srrc:defaultvalue>100000000</srrc:defaultvalue>
        <srrc:range>
          <srrc:startval>20000000</srrc:startval>
          <srrc:stopval>6000000000</srrc:stopval>
        </srrc:range>
        ...
      </srrc:parameter>
      ...
    </srrc:input>
  </srrc:feature>
  ...
</srrc:featurelist>
```

**Mock Atom 需实现**：完整的参数定义结构（ranges、listitems 等）

---

## 8. 设备基础信息

| 字段 | 值 |
|------|-----|
| mfid | 53090001140012 |
| equid | 51cd8dfe-e543-40c9-bdc3-a292766fee7f |
| equimanu | KYB |
| equmodel | MS845 |
| equname | MS845 |
| equsn | 12345678 |
| equstatus | 01 |
| equtype | 01 |
| maxtasknumber | 1 |

---

## 9. 参考文件

- captured/ - Real Atom 实测请求/响应报文
- ARCHIVE_20260408.md - Real Atom 联调成果归档
- 接口请求格式整理.md - 接口参数详情

---

## 10. 改造文件清单

| 文件 | 作用 | 改造内容 |
|------|------|----------|
| main_atom.py | Mock Atom 主服务 | 改造所有 SOAP 接口 |
| build_soap_response() | SOAP响应构建 | 支持完整回显格式 |

---

## 11. 改造优先级

| 优先级 | 接口 | 说明 |
|--------|------|------|
| P0 | B_QueryDeviceInfo | 最复杂，featurelist 结构 |
| P1 | B_StopMeas | 测试停止功能 |
| P2 | B_SglFreqMeas | 单频测量 |
| P3 | B_FScan | 频段扫描 |
| P4 | 其他执行接口 | 复用类似结构 |
