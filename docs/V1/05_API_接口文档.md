# 超短波监测管理一体化服务系统
# 接口文档（API）

| 版本 | 日期 | 作者 | 审核 | 变更内容 |
|------|------|------|------|----------|
| 1.0 | 2026-04-04 | AI Assistant | - | 初版创建 |

---

## 1. 文档概述

### 1.1 目的

本文档为超短波监测管理一体化服务系统的接口文档，定义系统的服务接口地址、输入输出参数、枚举类型、错误码、认证方式和请求/响应示例。

### 1.2 范围

本文档涵盖以下接口内容：
- SOAP Web Service接口定义
- 设备操作原子服务接口
- 标准服务接口
- 认证与鉴权机制
- 错误处理规范

### 1.3 接口基础信息

| 项目 | 说明 |
|------|------|
| 协议 | SOAP 1.1 / SOAP 1.2 |
| 编码 | UTF-8 |
| 命名空间 | `http://monitor.rrmp.gov.cn/services/` |
| WSDL地址 | `http://{host}:{port}/services?wsdl` |

---

## 2. 服务端点定义

### 2.1 代理服务（Proxy Service）

| 环境 | 地址 | 说明 |
|------|------|------|
| 开发环境 | `http://dev-monitor.local:8080/services` | 开发测试环境 |
| 测试环境 | `http://test-monitor.rrmp.gov.cn:8080/services` | 集成测试环境 |
| 生产环境 | `http://monitor.rrmp.gov.cn:8080/services` | 正式生产环境 |

### 2.2 原子服务（Atom Service）

| 环境 | 地址 | 说明 |
|------|------|------|
| 原子服务V3 | `http://localhost:9000/AtomSvcV3` | 真实设备服务 |
| 模拟服务 | `http://localhost:9001/MockService` | 模拟设备服务 |

### 2.3 服务列表

| 服务名称 | SOAP操作 | 说明 |
|----------|----------|------|
| SglFreqMeasure | 单频测量 | ITU标准单频点测量 |
| WBFFTMon | 宽带FFT观测 | 多FFT拼接频谱 |
| FScan | 扫频观测 | 频段扫描 |
| MScan | 频率表扫描 | 离散频点测量 |
| IFDF | 中频FFT测向 | 中频分析测向 |
| SglFreqDF | 单频测向 | 固定频点测向 |
| WBDF | 宽带FFT测向 | 频段内测向 |
| FScanDF | 扫频测向 | 扫描步进测向 |
| OccupancyMeas | 占用度测量 | 频段占用度统计 |
| DigitalSignalRec | 信号识别解调 | 数字信号处理 |
| SelfTest | 设备自检 | 设备状态自检 |
| QueryFacilityDevStatus | 状态查询 | 设备工作状态查询 |
| SetDevicePower | 电源控制 | 设备电源开关 |
| LinkAntennaDev | 天线控制 | 天线连接管理 |

---

## 3. SOAP接口通用定义

### 3.1 SOAP信封结构

**SOAP 1.1 请求信封：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:mon="http://monitor.rrmp.gov.cn/services/">
    <soap:Header>
        <!-- 认证头 -->
        <mon:AuthHeader>
            <mon:Token>xxx</mon:Token>
            <mon:Timestamp>2026-04-04T12:00:00Z</mon:Timestamp>
            <mon:Signature>xxx</mon:Signature>
        </mon:AuthHeader>
        <!-- 路由头 -->
        <mon:RouteHeader>
            <mon:MFID>BJ0001</mon:MFID>
            <mon:EQUID>01</mon:EQUID>
        </mon:RouteHeader>
    </soap:Header>
    <soap:Body>
        <!-- 服务请求内容 -->
    </soap:Body>
</soap:Envelope>
```

**SOAP 1.2 请求信封：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:mon="http://monitor.rrmp.gov.cn/services/">
    <s:Header>
        <!-- SOAP 1.2 头信息 -->
    </s:Header>
    <s:Body>
        <!-- 服务请求内容 -->
    </s:Body>
</s:Envelope>
```

### 3.2 响应信封结构

**成功响应：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <mon:Response xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <mon:ResultCode>0</mon:ResultCode>
            <mon:ResultMessage>Success</mon:ResultMessage>
            <mon:Data>
                <!-- 业务数据 -->
            </mon:Data>
        </mon:Response>
    </soap:Body>
</soap:Envelope>
```

**错误响应（SOAP Fault）：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault>
            <faultcode>soap:Server</faultcode>
            <faultstring>Service error message</faultstring>
            <detail>
                <mon:ErrorDetail xmlns:mon="http://monitor.rrmp.gov.cn/services/">
                    <mon:ErrorCode>ERR_001</mon:ErrorCode>
                    <mon:ErrorMessage>设备连接失败</mon:ErrorMessage>
                </mon:ErrorDetail>
            </detail>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>
```

---

## 4. 认证与鉴权

### 4.1 认证方式

系统支持以下认证方式：

| 认证方式 | 说明 | 适用场景 |
|----------|------|----------|
| Token认证 | 使用访问令牌 | Web Service调用 |
| Basic认证 | 用户名密码Base64编码 | 内部服务调用 |
| OAuth 2.0 | OAuth标准认证 | 第三方系统集成 |

### 4.2 Token认证流程

```
1. 客户端调用认证服务获取Token
2. 客户端在后续请求的Header中携带Token
3. 服务端验证Token有效性
4. Token过期后需重新获取
```

### 4.3 认证接口

**接口地址：** `POST /services/AuthService`

**请求参数：**

```xml
<soap:Body>
    <mon:AuthRequest>
        <mon:Username>admin</mon:Username>
        <mon:Password>encrypted_password</mon:Password>
        <mon:ClientId>client_app_001</mon:ClientId>
        <mon:GrantType>password</mon:GrantType>
    </mon:AuthRequest>
</soap:Body>
```

**响应参数：**

```xml
<mon:AuthResponse>
    <mon:AccessToken>eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...</mon:AccessToken>
    <mon:TokenType>Bearer</mon:TokenType>
    <mon:ExpiresIn>7200</mon:ExpiresIn>
    <mon:RefreshToken>refresh_token_value</mon:RefreshToken>
</mon:AuthResponse>
```

### 4.4 鉴权头字段

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Token | String | 是 | 访问令牌 |
| Timestamp | DateTime | 是 | 请求时间戳 |
| Signature | String | 是 | 签名（MD5/SHA256） |
| Nonce | String | 否 | 随机数（防重放） |

---

## 5. 单频测量服务接口 (SglFreqMeasure)

### 5.1 接口定义

| 属性 | 值 |
|------|------|
| 操作名称 | SglFreqMeasure |
| 数据类型ID | 0x10 (SGLFREQ) |
| 服务类型 | 原子服务 / 标准服务 |

### 5.2 请求参数

```xml
<mon:SglFreqMeasureRequest>
    <!-- 基础参数 -->
    <mon:TaskID>Task_20260404_001</mon:TaskID>
    <mon:Frequency>95800000</mon:Frequency>
    <mon:Span>200000</mon:Span>
    <mon:ReferenceLevel>-30</mon:ReferenceLevel>
    <mon:RBW>1000</mon:RBW>
    <mon:VBW>100</mon:VBW>
    <mon:Detector>AVERAGE</mon:Detector>
    <mon:SweepTime>100</mon:SweepTime>

    <!-- ITU测量参数 -->
    <mon:ITUTypes>
        <mon:ITUType>1</mon:ITUType>  <!-- 信号电平 -->
        <mon:ITUType>2</mon:ITUType>  <!-- 频率偏移 -->
        <mon:ITUType>5</mon:ITUType>  <!-- 信噪比 -->
    </mon:ITUTypes>

    <!-- 设备参数 -->
    <mon:AntennaID>ANT001</mon:AntennaID>
    <mon:Gain>10</mon:Gain>
    <mon:Attenuation>0</mon:Attenuation>

    <!-- 结果参数 -->
    <mon:ResultStorageType>DATABASE</mon:ResultStorageType>
    <mon:ResultFormat>BINARY</mon:ResultFormat>
</mon:SglFreqMeasureRequest>
```

**参数说明：**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| TaskID | String | 否 | 自动生成 | 任务标识 |
| Frequency | Int64 | 是 | - | 测量频率(Hz)，范围：1MHz~6GHz |
| Span | Int64 | 否 | 200kHz | 跨距(Hz) |
| ReferenceLevel | Double | 否 | -30 | 参考电平(dBm) |
| RBW | Int64 | 否 | 1000 | 分辨率带宽(Hz) |
| VBW | Int64 | 否 | 100 | 视频带宽(Hz) |
| Detector | String | 否 | AVERAGE | 检波模式：AVERAGE/PEAK/RMS |
| SweepTime | Int32 | 否 | 100 | 扫描时间(ms) |
| ITUTypes | Int[] | 否 | [1] | ITU测量类型列表 |
| AntennaID | String | 否 | default | 天线标识 |
| Gain | Double | 否 | 0 | 增益(dB) |
| Attenuation | Double | 否 | 0 | 衰减(dB) |
| ResultStorageType | String | 否 | DATABASE | 存储类型 |
| ResultFormat | String | 否 | BINARY | 结果格式 |

### 5.3 响应参数

```xml
<mon:SglFreqMeasureResponse>
    <mon:ResultCode>0</mon:ResultCode>
    <mon:ResultMessage>Success</mon:ResultMessage>
    <mon:TaskID>Task_20260404_001</mon:TaskID>
    <mon:Data>
        <mon:DataID>Data_20260404_001</mon:DataID>
        <mon:DataType>0x10</mon:DataType>
        <mon:Frequency>95800000</mon:Frequency>
        <mon:MeasureTime>2026-04-04T12:00:00Z</mon:MeasureTime>
        <mon:SignalLevel>-45.25</mon:SignalLevel>
        <mon:FreqOffset>125.5</mon:FreqOffset>
        <mon:ModulationType>FM</mon:ModulationType>
        <mon:ITUResults>
            <mon:ITUResult>
                <mon:Type>1</mon:Type>
                <mon:Name>信号电平</mon:Name>
                <mon:Value>-45.25</mon:Value>
                <mon:Unit>dBm</mon:Unit>
            </mon:ITUResult>
            <mon:ITUResult>
                <mon:Type>2</mon:Type>
                <mon:Name>频率偏移</mon:Name>
                <mon:Value>125.5</mon:Value>
                <mon:Unit>Hz</mon:Unit>
            </mon:ITUResult>
            <mon:ITUResult>
                <mon:Type>5</mon:Type>
                <mon:Name>信噪比</mon:Name>
                <mon:Value>35.8</mon:Value>
                <mon:Unit>dB</mon:Unit>
            </mon:ITUResult>
        </mon:ITUResults>
    </mon:Data>
</mon:SglFreqMeasureResponse>
```

---

## 6. 扫频观测服务接口 (FScan)

### 6.1 接口定义

| 属性 | 值 |
|------|------|
| 操作名称 | FScan |
| 数据类型ID | 0x15 (FSCAN) |
| 服务类型 | 原子服务 / 标准服务 |

### 6.2 请求参数

```xml
<mon:FScanRequest>
    <mon:TaskID>Task_20260404_002</mon:TaskID>
    <mon:StartFreq>80000000</mon:StartFreq>
    <mon:EndFreq>1000000000</mon:EndFreq>
    <mon:Step>10000</mon:Step>
    <mon:RBW>3000</mon:RBW>
    <mon:ReferenceLevel>-40</mon:ReferenceLevel>
    <mon:Attenuation>10</mon:Attenuation>
    <mon:SweepTime>1000</mon:SweepTime>
    <mon:MaxHold>false</mon:MaxHold>
    <mon:AttMode>AUTO</mon:AttMode>
    <mon:AntennaID>ANT001</mon:AntennaID>
    <mon:ResultStorageType>DATABASE</mon:ResultStorageType>
</mon:FScanRequest>
```

**参数说明：**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| TaskID | String | 否 | - | 任务标识 |
| StartFreq | Int64 | 是 | - | 起始频率(Hz) |
| EndFreq | Int64 | 是 | - | 终止频率(Hz) |
| Step | Int64 | 否 | 自动计算 | 频率步进(Hz) |
| RBW | Int64 | 否 | 3000 | 分辨率带宽(Hz) |
| ReferenceLevel | Double | 否 | -40 | 参考电平(dBm) |
| Attenuation | Double | 否 | 0 | 衰减量(dB) |
| SweepTime | Int32 | 否 | 1000 | 扫描时间(ms) |
| MaxHold | Boolean | 否 | false | 最大保持 |
| AttMode | String | 否 | AUTO | 衰减模式：AUTO/MANUAL |
| AntennaID | String | 否 | default | 天线标识 |
| ResultStorageType | String | 否 | DATABASE | 存储类型 |

### 6.3 响应参数

```xml
<mon:FScanResponse>
    <mon:ResultCode>0</mon:ResultCode>
    <mon:ResultMessage>Success</mon:ResultMessage>
    <mon:TaskID>Task_20260404_002</mon:TaskID>
    <mon:Data>
        <mon:DataID>Data_20260404_002</mon:DataID>
        <mon:DataType>0x15</mon:DataType>
        <mon:StartFreq>80000000</mon:StartFreq>
        <mon:EndFreq>1000000000</mon:EndFreq>
        <mon:Step>10000</mon:Step>
        <mon:PointCount>91999</mon:PointCount>
        <mon:MeasureTime>2026-04-04T12:00:00Z</mon:MeasureTime>
        <mon:ReferenceLevel>-40</mon:ReferenceLevel>
        <mon:SpectrumMin>-80.5</mon:SpectrumMin>
        <mon:SpectrumMax>-25.3</mon:SpectrumMax>
        <mon:SpectrumAvg>-55.2</mon:SpectrumAvg>
        <mon:SignalsDetected>15</mon:SignalsDetected>
        <mon:PeakFreq>95800000</mon:PeakFreq>
        <mon:PeakLevel>-25.3</mon:PeakLevel>
        <mon:SpectrumData encoding="base64">/9j/4AAQ...</mon:SpectrumData>
    </mon:Data>
</mon:FScanResponse>
```

---

## 7. 设备状态查询接口

### 7.1 接口定义

| 属性 | 值 |
|------|------|
| 操作名称 | QueryFacilityDevStatus |
| 服务类型 | 原子服务 |

### 7.2 请求参数

```xml
<mon:QueryFacilityDevStatusRequest>
    <mon:StationID>BJ0001</mon:StationID>
    <mon:EquipmentID>01</mon:EquipmentID>
    <mon:QueryDetail>true</mon:QueryDetail>
</mon:QueryFacilityDevStatusRequest>
```

**参数说明：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| StationID | String | 是 | 监测站编号(8字符) |
| EquipmentID | String | 否 | 设备组合标识(3字符)，为空则查询全部 |
| QueryDetail | Boolean | 否 | 是否查询详细信息 |

### 7.3 响应参数

```xml
<mon:QueryFacilityDevStatusResponse>
    <mon:ResultCode>0</mon:ResultCode>
    <mon:ResultMessage>Success</mon:ResultMessage>
    <mon:StationID>BJ0001</mon:StationID>
    <mon:StationName>北京监测站</mon:StationName>
    <mon:Equipments>
        <mon:EquipmentStatus>
            <mon:EquipmentID>01</mon:EquipmentID>
            <mon:EquipmentName>主接收机</mon:EquipmentName>
            <mon:Status>RUNNING</mon:Status>
            <mon:OnlineStatus>ONLINE</mon:OnlineStatus>
            <mon:CurrentFrequency>95800000</mon:CurrentFrequency>
            <mon:CurrentMode>FM</mon:CurrentMode>
            <mon:CPULoad>25</mon:CPULoad>
            <mon:MemoryUsage>45</mon:MemoryUsage>
            <mon:Temperature>42</mon:Temperature>
            <mon:LastHeartbeat>2026-04-04T12:00:00Z</mon:LastHeartbeat>
            <mon:Capabilities>
                <mon:Capability>
                    <mon:Type>SGLFREQ</mon:Type>
                    <mon:Supported>true</mon:Supported>
                </mon:Capability>
                <mon:Capability>
                    <mon:Type>FSCAN</mon:Type>
                    <mon:Supported>true</mon:Supported>
                </mon:Capability>
            </mon:Capabilities>
        </mon:EquipmentStatus>
    </mon:Equipments>
</mon:QueryFacilityDevStatusResponse>
```

---

## 8. 数据流推送接口 (Stream)

### 8.1 概述

数据流推送使用Stream模式，支持实时监测数据的推送。

### 8.2 订阅请求

```xml
<mon:StreamSubscribeRequest>
    <mon:SubscriptionID>Sub_20260404_001</mon:SubscriptionID>
    <mon:ServiceType>SGLFREQ</mon:ServiceType>
    <mon:Frequency>95800000</mon:Frequency>
    <mon:UpdateInterval>100</mon:UpdateInterval>
    <mon:CallbackURL>http://client.example.com/callback</mon:CallbackURL>
    <mon:DataFormat>BINARY</mon:DataFormat>
</mon:StreamSubscribeRequest>
```

### 8.3 推送数据格式

```xml
<!-- Stream推送数据包 -->
<mon:StreamData>
    <mon:SubscriptionID>Sub_20260404_001</mon:SubscriptionID>
    <mon:SequenceNumber>1001</mon:SequenceNumber>
    <mon:Timestamp>2026-04-04T12:00:00.100Z</mon:Timestamp>
    <mon:DataType>0x10</mon:DataType>
    <mon:Data encoding="base64">AQsCERERERER...</mon:Data>
</mon:StreamData>
```

---

## 9. 错误码定义

### 9.1 系统错误码

| 错误码 | 错误名称 | HTTP状态 | 说明 |
|--------|----------|----------|------|
| 0 | SUCCESS | 200 | 成功 |
| 1001 | ERR_AUTH_FAILED | 401 | 认证失败 |
| 1002 | ERR_AUTH_TOKEN_EXPIRED | 401 | Token过期 |
| 1003 | ERR_AUTH_PERMISSION_DENIED | 403 | 权限不足 |
| 1004 | ERR_AUTH_INVALID_SIGNATURE | 401 | 签名无效 |

### 9.2 服务错误码

| 错误码 | 错误名称 | HTTP状态 | 说明 |
|--------|----------|----------|------|
| 2001 | ERR_SERVICE_NOT_FOUND | 404 | 服务不存在 |
| 2002 | ERR_SERVICE_UNAVAILABLE | 503 | 服务不可用 |
| 2003 | ERR_SERVICE_TIMEOUT | 504 | 服务超时 |
| 2004 | ERR_SERVICE_PARAM_INVALID | 400 | 参数无效 |

### 9.3 设备错误码

| 错误码 | 错误名称 | HTTP状态 | 说明 |
|--------|----------|----------|------|
| 3001 | ERR_DEVICE_OFFLINE | 503 | 设备离线 |
| 3002 | ERR_DEVICE_BUSY | 503 | 设备忙 |
| 3003 | ERR_DEVICE_FAULT | 503 | 设备故障 |
| 3004 | ERR_DEVICE_NOT_SUPPORTED | 400 | 设备不支持该操作 |
| 3005 | ERR_DEVICE_CONNECT_FAILED | 503 | 设备连接失败 |
| 3006 | ERR_DEVICE_PARAM_ERROR | 400 | 设备参数错误 |

### 9.4 业务错误码

| 错误码 | 错误名称 | HTTP状态 | 说明 |
|--------|----------|----------|------|
| 4001 | ERR_TASK_NOT_FOUND | 404 | 任务不存在 |
| 4002 | ERR_TASK_RUNNING | 409 | 任务已在运行 |
| 4003 | ERR_TASK_CANCELLED | 410 | 任务已取消 |
| 4004 | ERR_FREQ_OUT_OF_RANGE | 400 | 频率超出范围 |
| 4005 | ERR_ANTENNA_NOT_CONNECTED | 400 | 天线未连接 |
| 4006 | ERR_DATA_STORAGE_FAILED | 500 | 数据存储失败 |

---

## 10. 枚举类型定义

### 10.1 任务模式 (TaskMode)

```xml
<xs:simpleType name="TaskMode">
    <xs:restriction base="xs:string">
        <xs:enumeration value="REAL_TIME">
            <xs:annotation>
                <xs:documentation>实时任务</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="SCHEDULED">
            <xs:annotation>
                <xs:documentation>定时任务</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="ON_DEMAND">
            <xs:annotation>
                <xs:documentation>按需任务</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
    </xs:restriction>
</xs:simpleType>
```

### 10.2 任务状态 (TaskStatus)

```xml
<xs:simpleType name="TaskStatus">
    <xs:restriction base="xs:string">
        <xs:enumeration value="PENDING">待执行</xs:enumeration>
        <xs:enumeration value="RUNNING">执行中</xs:enumeration>
        <xs:enumeration value="COMPLETED">已完成</xs:enumeration>
        <xs:enumeration value="FAILED">失败</xs:enumeration>
        <xs:enumeration value="CANCELLED">已取消</xs:enumeration>
        <xs:enumeration value="PAUSED">已暂停</xs:enumeration>
    </xs:restriction>
</xs:simpleType>
```

### 10.3 设备状态 (DeviceStatus)

```xml
<xs:simpleType name="DeviceStatus">
    <xs:restriction base="xs:string">
        <xs:enumeration value="ONLINE">在线</xs:enumeration>
        <xs:enumeration value="OFFLINE">离线</xs:enumeration>
        <xs:enumeration value="FAULT">故障</xs:enumeration>
        <xs:enumeration value="MAINTENANCE">维护中</xs:enumeration>
    </xs:restriction>
</xs:simpleType>
```

### 10.4 检波模式 (Detector)

```xml
<xs:simpleType name="Detector">
    <xs:restriction base="xs:string">
        <xs:enumeration value="AVERAGE">平均值检波</xs:enumeration>
        <xs:enumeration value="PEAK">峰值检波</xs:enumeration>
        <xs:enumeration value="RMS">有效值检波</xs:enumeration>
        <xs:enumeration value="SAMPLE">采样检波</xs:enumeration>
    </xs:restriction>
</xs:simpleType>
```

### 10.5 调制类型 (ModulationType)

```xml
<xs:simpleType name="ModulationType">
    <xs:restriction base="xs:string">
        <xs:enumeration value="FM">调频</xs:enumeration>
        <xs:enumeration value="AM">调幅</xs:enumeration>
        <xs:enumeration value="USB">上边带</xs:enumeration>
        <xs:enumeration value="LSB">下边带</xs:enumeration>
        <xs:enumeration value="CW">等幅报</xs:enumeration>
        <xs:enumeration value="FSK">频移键控</xs:enumeration>
        <xs:enumeration value="PSK">相移键控</xs:enumeration>
        <xs:enumeration value="QAM">正交幅度调制</xs:enumeration>
        <xs:enumeration value="OFDM">正交频分复用</xs:enumeration>
        <xs:enumeration value="UNKNOWN">未知</xs:enumeration>
    </xs:restriction>
</xs:simpleType>
```

### 10.6 ITU测量类型 (ITUType)

```xml
<xs:simpleType name="ITUType">
    <xs:restriction base="xs:int">
        <xs:enumeration value="1">
            <xs:annotation>
                <xs:documentation>信号电平(dBm)</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="2">
            <xs:annotation>
                <xs:documentation>频率偏移(Hz)</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="3">
            <xs:annotation>
                <xs:documentation>调制深度(%)</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="4">
            <xs:annotation>
                <xs:documentation>频偏(Hz)</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="5">
            <xs:annotation>
                <xs:documentation>信噪比(dB)</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
        <xs:enumeration value="6">
            <xs:annotation>
                <xs:documentation>占用带宽(Hz)</xs:documentation>
            </xs:annotation>
        </xs:enumeration>
    </xs:restriction>
</xs:simpleType>
```

---

## 11. WSDL定义概要

### 11.1 服务定义

```xml
<wsdl:definitions name="MonitorService"
    targetNamespace="http://monitor.rrmp.gov.cn/services/"
    xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
    xmlns:tns="http://monitor.rrmp.gov.cn/services/">

    <!-- 消息定义 -->
    <wsdl:message name="SglFreqMeasureRequest">
        <wsdl:part name="parameters" element="tns:SglFreqMeasureRequest"/>
    </wsdl:message>

    <wsdl:message name="SglFreqMeasureResponse">
        <wsdl:part name="parameters" element="tns:SglFreqMeasureResponse"/>
    </wsdl:message>

    <!-- 端口类型定义 -->
    <wsdl:portType name="MonitorServicePortType">
        <wsdl:operation name="SglFreqMeasure">
            <wsdl:input message="tns:SglFreqMeasureRequest"/>
            <wsdl:output message="tns:SglFreqMeasureResponse"/>
            <wsdl:fault name="ServiceFault" message="tns:ServiceFault"/>
        </wsdl:operation>
        <!-- 其他操作... -->
    </wsdl:portType>

    <!-- 绑定定义 -->
    <wsdl:binding name="MonitorServiceSoapBinding"
        type="tns:MonitorServicePortType">
        <soap:binding style="document"
            transport="http://schemas.xmlsoap.org/soap/http"/>
        <wsdl:operation name="SglFreqMeasure">
            <soap:operation
                soapAction="http://monitor.rrmp.gov.cn/services/SglFreqMeasure"/>
            <wsdl:input>
                <soap:body use="literal"/>
            </wsdl:input>
            <wsdl:output>
                <soap:body use="literal"/>
            </wsdl:output>
            <wsdl:fault name="ServiceFault">
                <soap:fault name="ServiceFault" use="literal"/>
            </wsdl:fault>
        </wsdl:operation>
    </wsdl:binding>

    <!-- 服务定义 -->
    <wsdl:service name="MonitorService">
        <wsdl:port name="MonitorServicePort"
            binding="tns:MonitorServiceSoapBinding">
            <soap:address
                location="http://monitor.rrmp.gov.cn:8080/services"/>
        </wsdl:port>
    </wsdl:service>
</wsdl:definitions>
```

---

## 12. 调用示例

### 12.1 单频测量调用示例

**请求（SOAP 1.1）：**

```bash
POST /services HTTP/1.1
Host: monitor.rrmp.gov.cn:8080
Content-Type: text/xml; charset=utf-8
SOAPAction: "http://monitor.rrmp.gov.cn/services/SglFreqMeasure"
Content-Length: 1254

<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:mon="http://monitor.rrmp.gov.cn/services/">
    <soap:Header>
        <mon:AuthHeader>
            <mon:Token>eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...</mon:Token>
            <mon:Timestamp>2026-04-04T12:00:00Z</mon:Timestamp>
            <mon:Signature>e3b0c44298fc1c149afbf4c8996fb924</mon:Signature>
        </mon:AuthHeader>
        <mon:RouteHeader>
            <mon:MFID>BJ0001</mon:MFID>
            <mon:EQUID>01</mon:EQUID>
        </mon:RouteHeader>
    </soap:Header>
    <soap:Body>
        <mon:SglFreqMeasureRequest>
            <mon:Frequency>95800000</mon:Frequency>
            <mon:Span>200000</mon:Span>
            <mon:ReferenceLevel>-30</mon:ReferenceLevel>
            <mon:RBW>1000</mon:RBW>
            <mon:VBW>100</mon:VBW>
            <mon:Detector>AVERAGE</mon:Detector>
            <mon:ITUTypes>
                <mon:int>1</mon:int>
                <mon:int>2</mon:int>
                <mon:int>5</mon:int>
            </mon:ITUTypes>
        </mon:SglFreqMeasureRequest>
    </soap:Body>
</soap:Envelope>
```

**响应：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <mon:SglFreqMeasureResponse xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <mon:ResultCode>0</mon:ResultCode>
            <mon:ResultMessage>Success</mon:ResultMessage>
            <mon:Data>
                <mon:SignalLevel>-45.25</mon:SignalLevel>
                <mon:FreqOffset>125.5</mon:FreqOffset>
                <mon:ITUResults>
                    <mon:ITUResult>
                        <mon:Type>1</mon:Type>
                        <mon:Value>-45.25</mon:Value>
                        <mon:Unit>dBm</mon:Unit>
                    </mon:ITUResult>
                </mon:ITUResults>
            </mon:Data>
        </mon:SglFreqMeasureResponse>
    </soap:Body>
</soap:Envelope>
```

### 12.2 错误响应示例

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault>
            <faultcode>soap:Server</faultcode>
            <faultstring>Device connection failed</faultstring>
            <detail>
                <mon:ErrorDetail xmlns:mon="http://monitor.rrmp.gov.cn/services/">
                    <mon:ErrorCode>3005</mon:ErrorCode>
                    <mon:ErrorCodeName>ERR_DEVICE_CONNECT_FAILED</mon:ErrorCodeName>
                    <mon:ErrorMessage>设备192.168.1.100连接失败</mon:ErrorMessage>
                    <mon:DeviceID>EQU001</mon:DeviceID>
                    <mon:Timestamp>2026-04-04T12:00:00Z</mon:Timestamp>
                </mon:ErrorDetail>
            </detail>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>
```

---

## 13. 附录

### 13.1 命名空间定义

| 前缀 | 命名空间URI |
|------|-------------|
| soap | http://schemas.xmlsoap.org/soap/envelope/ |
| soap12 | http://www.w3.org/2003/05/soap-envelope |
| xsd | http://www.w3.org/2001/XMLSchema |
| xsi | http://www.w3.org/2001/XMLSchema-instance |
| wsdl | http://schemas.xmlsoap.org/wsdl/ |
| tns | http://monitor.rrmp.gov.cn/services/ |

### 13.2 参考标准

- GWJ001-2015 平台架构规范
- GWJ002-2015 服务和接口规范
- SOAP 1.1 Specification (W3C Note)
- SOAP 1.2 Specification (W3C Recommendation)

---

**文档结束**
