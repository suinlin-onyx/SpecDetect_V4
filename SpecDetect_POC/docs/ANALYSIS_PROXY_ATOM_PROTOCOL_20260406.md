# 代理服务与原子服务通信协议分析报告

| 版本  | 日期         | 作者     | 变更内容    |
| --- | ---------- | ------ | ------- |
| 1.0 | 2026-04-06 | Claude | 初次分析并归档 |

---

## 1. 概述

### 1.1 分析目的

明确**代理服务(Proxy)**与**原子服务(Atom)**之间的通信协议要求，核实当前实现与文档的差异。

### 1.2 涉及的文档

- 02_HLD_概要设计说明书.md
- 03_LLD_详细设计说明书.md
- 05_API_接口文档.md
- 06_RMCPTP_v2.0_无线电协议规范.md

---

## 2. 架构分层定义

### 2.1 文档中的架构

根据HLD第2.1节整体架构图：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Web应用层                                        │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ HTTP/SOAP
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         代理服务层 (Proxy Service)                          │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ SOAP/XML  ← 这里
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         原子服务层 (Atom Service)                           │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ RX-RMCPTP v2.0
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           设备层 (Device Layer)                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 各层通信协议

| 层级            | 文档要求协议             | 说明                 |
| ------------- | ------------------ | ------------------ |
| Web → Proxy   | **HTTP/SOAP**      | SOAP 1.1/1.2 + XML |
| Proxy → Atom  | **SOAP/XML**       | SOAP消息转发           |
| Atom → Device | **RX-RMCPTP v2.0** | 二进制协议，TCP通信        |

---

## 3. Proxy → Atom 通信协议分析

### 3.1 文档要求

**HLD 第5.3节 数据流接口：**

```
Web请求 ──▶ SOAP解析 ──▶ Schema验证 ──▶ 认证授权 ──▶ 路由分发
   │                                                        │
   ▼                                                        ▼
  XML    ───────────────────────────────────────────▶ 原子服务
格式验证                                               请求封装
```

**HLD 第5.2.1节 StartMeasure接口示例：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:mon="http://monitoring.example.com/schema/monitoring/v1">
  <soap:Header>
    <mon:AuthToken>xxx-xxx-xxx</mon:AuthToken>
  </soap:Header>
  <soap:Body>
    <mon:StartMeasureRequest>
      <mon:TaskID>task-001</mon:TaskID>
      <mon:ServiceType>SglFreqMeasure</mon:ServiceType>
      ...
    </mon:StartMeasureRequest>
  </soap:Body>
</soap:Envelope>
```

**LLD 第2.1.1节 SOAP处理类定义：**

```csharp
public class SoapMessageHandler
{
    public SoapVersion Version { get; set; }
    public XmlNamespaceManager NamespaceManager { }

    public SoapRequest ParseRequest(string xmlContent) { }
    public string BuildResponse(SoapResponse response) { }
    public string BuildFault(int errorCode, string errorMessage) { }
}
```

### 3.2 当前实际实现

**routes.py 第57-153行 `dispatch_to_atom_service()` 函数：**

```python
def dispatch_to_atom_service(operation: str, params: dict) -> dict:
    """将SOAP操作分发到原子服务"""
    try:
        if operation == 'StartMeasure':
            response = requests.post(
                f"{ATOM_BASE_URL}/monitor/sglfreq",
                json={'frequency': frequency, 'bandwidth': bandwidth},  # JSON!
                timeout=10
            )
            return response.json()
```

**实际使用的协议：**

- HTTP POST
- Content-Type: `application/json`
- 请求体: `{"frequency": 100000000, "bandwidth": 120000}`

### 3.3 差异对比

| 项目               | 文档要求                    | 实际实现             | 状态    |
| ---------------- | ----------------------- | ---------------- | ----- |
| **协议**           | SOAP 1.1/1.2 + XML      | HTTP + JSON      | ❌ 不匹配 |
| **Content-Type** | text/xml                | application/json | ❌ 不匹配 |
| **请求格式**         | SOAP Envelope + Body    | JSON对象           | ❌ 不匹配 |
| **认证头**          | SOAP Header + AuthToken | 无                | ❌ 缺失  |
| **路由信息**         | MFID/EQUID路由键           | 无                | ❌ 缺失  |

### 3.4 数据流示意

**文档要求：**

```
Client ──XML SOAP──▶ Proxy ──XML SOAP──▶ Atom
```

**实际实现：**

```
Client ──JSON──▶ Proxy ──JSON──▶ Atom
```

---

## 4. Atom → Device 通信协议分析

### 4.1 文档要求

**HLD 架构图标注：**

```
Atom ──▶ RX-RMCPTP v2.0 ──▶ Device
```

**LLD 第2.2.1节 设备通信类：**

```csharp
public class DeviceCommunicator
{
    private const int HEARTBEAT_INTERVAL_MS = 30000;
    private const byte PROTOCOL_VERSION = 0x07;

    public async Task ConnectAsync(string host, int port) { }
    public async Task<DeviceResponse> SendCommandAsync(DeviceCommand command) { }
    private async Task SendFrameAsync(byte[] frame) { }
}
```

**LLD 第2.2.2节 RMCPTP协议解析类：**

```csharp
public class RmcpProtocolParser
{
    public const int FRAME_HEADER_SIZE = 18;

    public static class BusinessTypes
    {
        public const byte SglFreq = 0x10;
        public const byte IfAnalysis = 0x11;
        public const byte Df = 0x12;
        public const byte IfDf = 0x13;
        public const byte Fscan = 0x15;
    }
}
```

### 4.2 当前实际实现

**device_client.py：**

```python
class DeviceClient:
    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def send_and_receive(self, frame: bytes):
        self.writer.write(frame)
        header = await self.reader.read(RMCPTPParser.HEADER_SIZE)
        length = int.from_bytes(header[0:4], 'little')
        data = await self.reader.read(length)
        return header_info, payload, raw_frame
```

**protocol_builder.py:**

```python
class RMCPTPBuilder:
    def build_frame(self, business_type: int, payload: bytes) -> bytes:
        dw_length = len(payload) + 1  # 包含business_type
        frame = struct.pack('<I', dw_length)  # 4字节长度
        frame += b'\x00' * 12            # 12字节保留
        frame += bytes([0x07, business_type])  # 版本+类型
        frame += b'\x00' * 2            # 2字节校验和(占位)
        frame += bytes([business_type])  # 业务类型
        frame += payload                 # 数据载荷
        return frame
```

### 4.3 差异对比

| 项目        | 文档要求                    | 实际实现            | 状态      |
| --------- | ----------------------- | --------------- | ------- |
| **协议**    | RX-RMCPTP v2.0          | RMCPTP (名称略有不同) | ⚠️ 基本一致 |
| **版本标识**  | PROTOCOL_VERSION = 0x07 | 0x07            | ✅ 一致    |
| **帧头长度**  | 18字节                    | 18字节            | ✅ 一致    |
| **心跳机制**  | 30000ms间隔               | ❌ 未实现           | ❌ 缺失    |
| **校验和算法** | 两折半移位相加取反               | 与文档一致           | ✅ 已实现   |

---

## 5. 完整数据流对比

### 5.1 文档要求的数据流

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ 客户端 │────▶│ 代理   │────▶│ 原子   │────▶│ 设备   │────▶│ 数据   │
│        │ SOAP │ 服务   │SOAP │ 服务   │RMCPTP│        │     │ 采集   │
└────────┘ XML  └────────┘ XML └────────┘二进制└────────┘     └────────┘
   │              │              │              │              │
   ▼              ▼              ▼              ▼              ▼
1.发起请求    2.认证鉴权   3.服务路由    4.命令封装    5.开始采集
              │
              ▼
         6.返回任务ID
```

### 5.2 当前实际实现的数据流

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ 客户端 │────▶│ 代理   │────▶│ 原子   │────▶│ 虚拟   │────▶│ 数据   │
│        │JSON │ 服务   │JSON │ 服务   │RMCPTP│ 设备   │     │ 生成   │
└────────┘     └────────┘     └────────┘二进制└────────┘     └────────┘
   │              │              │              │
   ▼              ▼              ▼              ▼
1.发起请求    2.直接放行    3.HTTP路由    4.命令封装
              (无认证)       (REST API)    5.被动响应
```

---

## 6. 问题汇总

### 6.1 Proxy → Atom 通信问题

| 问题                    | 影响          | 优先级 |
| --------------------- | ----------- | --- |
| 使用HTTP/JSON代替SOAP/XML | 不符合文档架构要求   | P0  |
| 无认证头解析与验证             | 安全性不合规      | P0  |
| 无路由头(MFID/EQUID)处理    | 无法支持多设备路由   | P1  |
| SOAPAction未从Header提取  | 无法正确路由到原子服务 | P1  |

### 6.2 Atom → Device 通信问题

| 问题       | 影响         | 优先级 |
| -------- | ---------- | --- |
| 心跳机制未实现  | 无法维持设备连接保活 | P1  |
| 连接模式为短连接 | 每次请求建立新连接  | P2  |

---

## 7. 修复建议

### 7.1 Proxy → Atom 通信修复

```
Phase 1: 协议层修复 (P0)
┌─────────────────────────────────────────────────────────────┐
│ 修复任务 | 说明 | 优先级                                     │
├─────────────────────────────────────────────────────────────┤
│ SOAP消息构建 | Proxy→Atom使用SOAP Envelope封装请求 | P0    │
│ 认证头处理 | 解析AuthHeader并进行Token验证 | P0            │
│ SOAPAction处理 | 从SOAP Header提取SOAPAction进行路由 | P1  │
│ 错误处理 | 实现SOAP Fault格式错误响应 | P1                  │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Atom → Device 通信修复

```
Phase 2: 业务层修复 (P1)
┌─────────────────────────────────────────────────────────────┐
│ 修复任务 | 说明 | 优先级                                     │
├─────────────────────────────────────────────────────────────┤
│ 心跳机制 | 实现30秒间隔的心跳保活 | P1                       │
│ 连接池管理 | 复用TCP连接而非每次新建 | P2                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 附录

### 8.1 术语对照

| 术语         | 说明                                         |
| ---------- | ------------------------------------------ |
| SOAP       | Simple Object Access Protocol，XML格式的远程调用协议 |
| XML        | 可扩展标记语言                                    |
| JSON       | JavaScript Object Notation，轻量级数据交换格式       |
| RMCPTP     | Radio Monitoring Control Protocol，监测控制协议   |
| RX-RMCPTP  | RMCPTP协议的接收数据帧类型                           |
| MFID       | 站点标识符 (Monitoring Facility ID)             |
| EQUID      | 设备标识符 (Equipment ID)                       |
| SOAPAction | SOAP协议中指定操作名称的HTTP Header                  |

### 8.2 参考代码位置

| 文件                                     | 说明                        |
| -------------------------------------- | ------------------------- |
| `app/proxy_service/routes.py`          | Proxy路由，调用Atom使用HTTP/JSON |
| `app/proxy_service/soap_handler.py`    | SOAP处理器(仅解析请求，不转发SOAP)    |
| `app/atom_service/device_client.py`    | Atom与Device的TCP通信         |
| `app/atom_service/protocol_builder.py` | RMCPTP帧构建                 |
| `app/atom_service/protocol_parser.py`  | RMCPTP帧解析                 |

---

**分析完成**: 2026-04-06
**下一步行动**: 待用户确认修复优先级后开始实施
