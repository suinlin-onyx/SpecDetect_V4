# SOAP 接口规范与坑点记录

**创建日期**: 2026-05-14
**更新日期**: 2026-05-14
**依据**: 生产环境日志逆向分析

---

## 1. 概述

本文档记录 SpecDetect_Atom 的 SOAP 接口解析规范，包括请求/响应字段解析和已发现的坑点。

> **注意**: 项目 WSDL 中 `input` 定义为 `xsd:string`，不描述具体业务字段结构。本文档基于生产环境实际报文逆向分析得出。

---

## 2. B_FScan 请求报文结构

### 2.1 完整请求示例

```
POST /53090001140010/MS950/B_FScan HTTP/1.1
SOAPAction: B_FScan
Content-Type: text/xml; charset=UTF-8
Host: 172.18.114.196:8282

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
  <soapenv:Header>
    <srrc:MonitorHeader>
      <srrc:TransId>530000-01-0006-14205150465215363</srrc:TransId>
      <srrc:BizKey>B_FScan</srrc:BizKey>
      <srrc:PSCode>PS-530900-01-0061-0005</srrc:PSCode>
      <srrc:BSCode>BS-530900-01-0061-0005</srrc:BSCode>
      <srrc:appCode>530000-01-0006</srrc:appCode>
      <srrc:appName>标准频谱探测</srrc:appName>
      <srrc:platFormCode>530000-01-0001</srrc:platFormCode>
      <srrc:platFormName>一体化平台</srrc:platFormName>
    </srrc:MonitorHeader>
  </soapenv:Header>
  <soapenv:Body>
    <srrc:requestbody>
      <srrc:appid>530000-01-0167:标准频谱探测</srrc:appid>
      <srrc:equid>5327d8e3-e04c-4ce0-90cf-605725dd8862</srrc:equid>
      <srrc:equpara>
        <srrc:groupitems>
          <srrc:groupitem>
            <srrc:groupid>1</srrc:groupid>
            <srrc:items>
              <srrc:item>
                <srrc:paraname>gain</srrc:paraname>
                <srrc:paravalue>AGC</srrc:paravalue>
              </srrc:item>
              <srrc:item>
                <srrc:paraname>rfworkmode</srrc:paraname>
                <srrc:paravalue>0</srrc:paravalue>
              </srrc:item>
              <srrc:item>
                <srrc:paraname>stopfreq</srrc:paraname>
                <srrc:paravalue>108000000</srrc:paravalue>
              </srrc:item>
              <srrc:item>
                <srrc:paraname>startfreq</srrc:paraname>
                <srrc:paravalue>87000000</srrc:paravalue>
              </srrc:item>
              <srrc:item>
                <srrc:paraname>step</srrc:paraname>
                <srrc:paravalue>25000</srrc:paravalue>
              </srrc:item>
              <srrc:item>
                <srrc:paraname>scanmode</srrc:paraname>
                <srrc:paravalue>0</srrc:paravalue>
              </srrc:item>
            </srrc:items>
          </srrc:groupitem>
        </srrc:groupitems>
      </srrc:equpara>
      <srrc:executetime>0</srrc:executetime>
      <srrc:mfid>53090001140010</srrc:mfid>
      <srrc:outputchannel>
        <srrc:mode>sink</srrc:mode>
        <srrc:datachannel>stream</srrc:datachannel>
        <srrc:host>172.18.98.5</srrc:host>
        <srrc:port>8332</srrc:port>
        <srrc:stc>994205162</srrc:stc>
      </srrc:outputchannel>
      <srrc:priority>0</srrc:priority>
      <srrc:taskid>6d5c405f-8c17-4e74-ae6c-8c2a7423967c</srrc:taskid>
      <srrc:userid>53350004</srrc:userid>
    </srrc:requestbody>
  </soapenv:Body>
</soapenv:Envelope>
```

### 2.2 关键字段解析

| 字段路径 | 示例值 | 说明 | 解析状态 |
|----------|--------|------|----------|
| `requestbody/appid` | `530000-01-0167:标准频谱探测` | 应用标识 | ✅ 已实现 |
| `requestbody/userid` | `53350004` | 用户标识 | ✅ 已实现 |
| `requestbody/mfid` | `53090001140010` | 设备厂商标识 | ✅ 已实现 |
| `requestbody/equid` | `5327d8e3-e04c-4ce0-90cf-605725dd8862` | 设备唯一标识 | ✅ 已实现 |
| `requestbody/taskid` | `6d5c405f-8c17-4e74-ae6c-8c2a7423967c` | 任务标识 | ✅ 已实现 |
| `requestbody/priority` | `0` | 优先级 | ✅ 已实现 |
| `requestbody/executetime` | `0` | 执行时间 | ✅ 已实现 |
| `equpara/groupitems/groupitem/items/item/paraname` | `startfreq` | 扫描参数名 | ✅ 已实现 |
| `equpara/groupitems/groupitem/items/item/paravalue` | `87000000` | 扫描参数值 | ✅ 已实现 |
| `outputchannel/mode` | `sink` | 输出模式 | ✅ 已实现 |
| `outputchannel/datachannel` | `stream` | 数据通道类型 | ✅ 已实现 |
| `outputchannel/host` | `172.18.98.5` | streamsrc 主机 | ✅ 已实现 |
| `outputchannel/port` | `8332` | streamsrc 端口 | ✅ 已实现 |
| `outputchannel/stc` | `994205162` | 同步通道号 | ✅ 已实现 |

### 2.3 Header 中字段

| 字段路径 | 示例值 | 说明 | 解析状态 |
|----------|--------|------|----------|
| `MonitorHeader/TransId` | `530000-01-0006-14205150465215363` | 事务ID | ❌ 未解析 |
| `MonitorHeader/BizKey` | `B_FScan` | 业务键 | ❌ 未解析 |
| `MonitorHeader/PSCode` | `PS-530900-01-0061-0005` | PS代码 | ❌ 未解析 |
| `MonitorHeader/BSCode` | `BS-530900-01-0061-0005` | BS代码 | ❌ 未解析 |
| `MonitorHeader/appCode` | `530000-01-0006` | 应用代码 | ❌ 未解析 |
| `MonitorHeader/appName` | `标准频谱探测` | 应用名称 | ❌ 未解析 |
| `MonitorHeader/platFormCode` | `530000-01-0001` | 平台代码 | ❌ 未解析 |
| `MonitorHeader/platFormName` | `一体化平台` | 平台名称 | ❌ 未解析 |

---

## 3. B_FScan 响应报文结构

### 3.1 正确响应示例 (原版 Atom)

```
HTTP/1.1 200 OK
Server: gSOAP/2.8
Content-Type: text/xml; charset=utf-8
Content-Length: 1874
Connection: close

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:ns1="base"
  xmlns:src="http://www.srrc.org.cn">
  <soapenv:Header>
    <srrc:ProviderResponse>
      <srrc:bizResCd>BIZ-000001</srrc:bizResCd>
      <srrc:bizResText>调用成功</srrc:bizResText>
    </srrc:ProviderResponse>
  </soapenv:Header>
  <soapenv:Body>
    <srrc:responsebody>
      <srrc:result>
        <srrc:appid>530000-01-0167:标准频谱探测</srrc:appid>
        <srrc:userid>53350004</srrc:userid>
        <srrc:priority>0</srrc:priority>
        <srrc:executetime>0</srrc:executetime>
        <srrc:mfid>53090001140010</srrc:mfid>
        <srrc:equid>5327d8e3-e04c-4ce0-90cf-605725dd8862</srrc:equid>
        <srrc:equpara>...</srrc:equpara>
        <srrc:outputchannel>
          <srrc:mode>source</srrc:mode>
          <srrc:datachannel>stream</srrc:datachannel>
          <srrc:host>172.18.98.5</srrc:host>
          <srrc:port>18012</srrc:port>
          <srrc:stc>994205162</srrc:stc>
        </srrc:outputchannel>
      </srrc:result>
    </srrc:responsebody>
  </soapenv:Body>
</soapenv:Envelope>
```

### 3.2 响应字段映射规则

| 响应字段 | 来源 | 说明 |
|----------|------|------|
| `appid` | **请求** `requestbody/appid` | 应与请求一致 |
| `userid` | **请求** `requestbody/userid` | 应与请求一致 |
| `mfid` | **请求** `requestbody/mfid` | 应与请求一致 |
| `equid` | **请求** `requestbody/equid` | 应与请求一致 |
| `priority` | **请求** `requestbody/priority` | 应与请求一致 |
| `executetime` | **请求** `requestbody/executetime` | 应与请求一致 |
| `taskid` | **生成** | 需生成新UUID |
| `equpara` | **请求** `requestbody/equpara` | 透传扫描参数 |
| `outputchannel/mode` | `source` | 固定值 |
| `outputchannel/datachannel` | `stream` | 固定值 |
| `outputchannel/host` | **配置** | streamsrc 监听地址 |
| `outputchannel/port` | **配置** | streamsrc 监听端口 |
| `outputchannel/stc` | **生成** | 使用请求中的值 |

---

## 4. 坑点记录

### 4.1 坑点 1: 字符编码错误 ⚠️ CRITICAL

**问题**: 响应使用 `charset=gb2312` 和 `encoding="gb2312"`，导致中文乱码。

**现象**:
- bizResText 显示为 `óɹ` 而非 `调用成功`

**根因**: `preset/device_preset.py` 中 XML 生成使用 GB2312 编码。

**生产环境对比**:
| 字段 | 原版 Atom (正确) | 当前版本 Atom (错误) |
|------|------------------|---------------------|
| Content-Type | `charset=utf-8` | `charset=gb2312` |
| XML encoding | `UTF-8` | `gb2312` |
| bizResText | `调用成功` | `óɹ` |

**修复方案**: 将 XML 编码改为 UTF-8。

**涉及文件**: `src/preset/device_preset.py`

---

### 4.2 坑点 2: 设备信息硬编码 ⚠️ HIGH

**问题**: 响应中的 `mfid` 和 `equid` 使用硬编码值，而非从请求中解析。

**现象**: 客户端校验设备ID失败。

**根因**: `service.py` 中 `_handle_fscan()` 等方法返回硬编码值。

**代码位置**: `src/atom/service.py` 第 228-229 行:

```python
# 错误: 硬编码
mfid='53090001140012',
equid='51cd8dfe-e543-40c9-bdc3-a292766fee7f',

# 正确: 应使用 params 中的值
mfid=params.get('mfid', ''),
equid=params.get('equid', ''),
```

**生产环境对比**:
| 字段 | 请求值 | 当前版本返回 (错误) |
|------|--------|---------------------|
| mfid | `53090001140010` | `53090001140012` |
| equid | `5327d8e3-e04c-4ce0-90cf-605725dd8862` | `51cd8dfe-e543-40c9-bdc3-a292766fee7f` |

**修复方案**:
1. 确认 `soap/parser.py` 已正确解析 `mfid` 和 `equid` 到 `params`
2. `service.py` 中使用 `params.get('mfid')` 和 `params.get('equid')`

**涉及文件**:
- `src/atom/service.py`
- `src/atom/soap/parser.py`

---

### 4.3 坑点 3: appid/userid 未解析 ⚠️ HIGH

**问题**: `appid` 和 `userid` 字段在请求中已传递，但未被解析。

**根因**: `soap/parser.py` 的解析逻辑只解析了 `taskid`, `mfid`, `equid`，未解析 `appid`, `userid`。

**当前解析代码** (`soap/parser.py` 第 130-134 行):
```python
for field in ['taskid', 'mfid', 'equid']:
    pattern = f'<[^>]*:{field}[^>]*>([^<]+)</[^>]*:{field}>'
    match = re.search(pattern, body_content, re.IGNORECASE)
    if match:
        result[field] = match.group(1).strip()
```

**修复方案**: 添加 `appid` 和 `userid` 到解析列表。

```python
for field in ['taskid', 'mfid', 'equid', 'appid', 'userid']:
```

**涉及文件**: `src/atom/soap/parser.py`

---

### 4.4 坑点 4: SOAP 命名空间缺失 ⚠️ MEDIUM

**问题**: 响应 XML 缺少完整的命名空间声明。

**原版 Atom 命名空间**:
```xml
xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xmlns:xsd="http://www.w3.org/2001/XMLSchema"
xmlns:ns1="base"
xmlns:src="http://www.srrc.org.cn"
```

**当前版本 Atom** 只有基本的 `xmlns:srrc`。

**影响**: 严格的 SOAP 客户端可能验证失败。

**修复方案**: 在 `preset/device_preset.py` 的模板中添加完整命名空间。

**涉及文件**: `src/preset/templates/_envelope.xml`

---

## 5. 解析代码实现

### 5.1 请求解析流程

```
HTTP Request
    ↓
parse_http_header()  [soap/parser.py:12-55]
    ↓ 提取 method, path, SOAPAction, headers
parse_soap_body()   [soap/parser.py:108-147]
    ↓ 提取 body_content
extract_soap_request() [soap/parser.py:150-169]
    ↓
{ headers, body, method, namespace, params }
    ↓
service.py: _handle_soap_request()
    ↓ 分派到 _handle_fscan() 等
```

### 5.2 关键解析代码

**soap/parser.py - 字段解析**:
```python
def parse_soap_body(body: bytes, soap_action_header: str = None) -> Optional[Dict]:
    """解析 SOAP Body"""
    # 1. 提取 Body 内容
    body_match = re.search(r'<[^>]*:Body[^>]*>(.+)</[^>]*:Body>', text, re.IGNORECASE | re.DOTALL)
    if not body_match:
        return None
    body_content = body_match.group(1)

    # 2. 提取方法名 (优先从 SOAPAction)
    method, ns = _extract_method_from_xml(body_content, soap_action_header)

    # 3. 解析业务字段
    result = {
        'soap_action': soap_action_header,
        'method': method,
        'namespace': ns,
        'body': body_content
    }

    # 4. 关键字段解析 (需包含 appid, userid)
    for field in ['taskid', 'mfid', 'equid', 'appid', 'userid']:
        pattern = f'<[^>]*:{field}[^>]*>([^<]+)</[^>]*:{field}>'
        match = re.search(pattern, body_content, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()

    # 5. 解析扫描参数
    params = ['startfreq', 'stopfreq', 'step', 'gain', 'rfworkmode', 'scanmode', 'dfmode']
    for param in params:
        pattern = f'<[^>]*:{param}[^>]*>([^<]+)</[^>]*:{param}>'
        match = re.search(pattern, body_content, re.IGNORECASE)
        if match:
            result[param] = match.group(1).strip()

    return result
```

### 5.3 响应构建

**service.py - _handle_fscan()**:
```python
def _handle_fscan(self, request: dict) -> bytes:
    params = request.get('params', {})

    # 从请求中获取设备标识 (params 来自 parser 解析结果)
    mfid = params.get('mfid', '')
    equid = params.get('equid', '')
    appid = params.get('appid', '')
    userid = params.get('userid', '')

    # 生成 taskid 和 stc
    taskid = params.get('taskid', f"FSCAN-{int(time.time())}")
    stc = int(time.time())

    # 使用模板构建响应，传入真实值
    return self.preset_manager.build_response(
        'B_FScan',
        appid=appid,          # 使用请求中的值
        userid=userid,        # 使用请求中的值
        taskid=taskid,
        mfid=mfid,           # 使用请求中的值
        equid=equid,         # 使用请求中的值
        priority=params.get('priority', '0'),
        executetime=params.get('executetime', '0'),
        startfreq=params.get('startfreq', '137000000'),
        stopfreq=params.get('stopfreq', '173000000'),
        step=params.get('step', '25000'),
        gain=params.get('gain', 'AGC'),
        scanmode=params.get('scanmode', '0'),
        outputchannel_mode='source',
        outputchannel_datachannel='stream',
        outputchannel_host=self.config.streamsrc_ip,
        outputchannel_port=self.config.streamsrc_port,
        outputchannel_stc=stc
    )
```

---

## 6. 其他接口字段

### 6.1 B_QueryFaciDevStat

**请求字段**:
| 字段 | 路径 | 说明 |
|------|------|------|
| mfid | requestbody/mfid | 设备厂商标识 |
| equid | requestbody/equid | 设备唯一标识 |

**响应字段**:
| 字段 | 来源 | 说明 |
|------|------|------|
| mfid | 请求透传 | |
| mfname | devinfo XML | 从设备预置文件读取 |
| equid | 请求透传 | |
| equname | devinfo XML | 从设备预置文件读取 |
| state | 固定值 | idle/busy |

### 6.2 B_QueryDeviceInfo

**请求字段**:
| 字段 | 路径 | 说明 |
|------|------|------|
| mfid | requestbody/mfid | 设备厂商标识 |
| equid | requestbody/equid | 设备唯一标识 |

**响应字段**: 来自 devinfo XML 模板

### 6.3 B_StopMeas

**请求字段**:
| 字段 | 路径 | 说明 |
|------|------|------|
| taskid | requestbody/taskid | 需关闭的任务ID |

**响应字段**: 无特殊字段

---

## 7. 测试验证

### 7.1 生产环境日志位置

```
生产环境日志/
├── 原版atom2026-5-14_20-50_logs/     # 原版 Atom 日志 (正常)
│   ├── transparent_20260514_202752.log
│   ├── 202951_743651_B_FScan_req.bin  # 请求样本
│   └── 202951_743651_B_FScan_res.bin  # 响应样本
└── atom_2026-5-14_20-50_logs/        # 当前版本 Atom 日志 (异常)
    ├── transparent_20260514_203416.log
    ├── 203442_412851_B_FScan_req.bin  # 请求样本
    └── 203442_412851_B_FScan_res.bin   # 响应样本
```

### 7.2 验证要点

1. **字符编码**: 响应 XML 使用 `charset=utf-8`
2. **字段一致性**: 响应 `mfid`/`equid`/`appid`/`userid` 与请求一致
3. **命名空间**: 包含完整 SOAP 命名空间声明
4. **bizResText**: 显示 `调用成功` 而非乱码

---

## 8. 修改记录

| 日期 | 修改内容 | 涉及文件 |
|------|----------|----------|
| 2026-05-14 | 创建本文档 | - |
| 2026-05-14 | 发现坑点 1-4 | 见各坑点 |
