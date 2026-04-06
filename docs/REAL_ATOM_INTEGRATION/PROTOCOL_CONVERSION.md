# 协议转换流程分析

> 创建日期：2026-04-06
> 更新日期：2026-04-06

---

## 整体架构

```
[外部系统]
     ↓ SOAP/HTTP
[Proxy Service] :8080 / :8081
     ↓ SOAP/HTTP
[Atom Service] :9090 / :8282
     ↓ RMCPTP v2.0 / TCP
[Device] :9000
```

---

## 协议转换流程

### 链路说明

| 链路 | 协议 | 格式 | 说明 |
|------|------|------|------|
| 外部 → Proxy | SOAP | XML over HTTP | 客户端发送 SOAP 请求 |
| Proxy → Atom | SOAP | XML over HTTP | Proxy 转发请求到 Atom |
| Atom → Device | RMCPTP v2.0 | 二进制帧 over TCP | Atom 与设备通信 |

---

## 示例：SGLFREQ 单频测量

### 第1步：外部发送 SOAP 请求

```http
POST /soap HTTP/1.1
Host: 127.0.0.1:8080
Content-Type: text/xml; charset=utf-8

<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <StartMeasure>
      <Frequency>100000000</Frequency>
      <Bandwidth>120000</Bandwidth>
    </StartMeasure>
  </soap:Body>
</soap:Envelope>
```

### 第2步：Proxy 解析并转发到 Atom（SOAP 格式）

```http
POST http://127.0.0.1:9090/services HTTP/1.1
Content-Type: text/xml; charset=utf-8

<ns0:StartMeasure xmlns:ns0="http://monitor.rrmp.gov.cn/services/">
  <ns0:Frequency>100000000</ns0:Frequency>
  <ns0:Bandwidth>120000</ns0:Bandwidth>
</ns0:StartMeasure>
```

**关键代码**：`routes.py` 第469-526行 `dispatch_to_atom_service()`

### 第3步：Atom 构建 RMCPTP 二进制帧

```python
# main_atom.py 第236-237行
builder = RMCPTPBuilder()
frame = builder.build_sglfreq_command(frequency, antenna)
```

**RMCPTP 帧结构**（18字节帧头 + 业务数据）：

```
|----------------------- 帧头 (18字节) -----------------------|----- 业务数据 -----|
| dwLength | tmStamp       | Ver  |Type|Flag| Chk | nBdType | nArrays | frequency... |
| 4字节    | 8字节         | 2字节| 1字节|1字节| 2字节 | 1字节    | 4字节     | 8字节        |
```

**帧头格式**：
- `dwLength`: 4字节 - 业务数据长度
- `tmStamp`: 8字节 - FILETIME 时间戳
- `nVersion`: 2字节 - 协议版本 (0x0007)
- `nDataType`: 1字节 - 数据类型 (0x00=命令)
- `nFlags`: 1字节 - 标志位
- `nCheckSum`: 2字节 - 帧头校验和

**关键代码**：`protocol_builder.py` 第21-107行

### 第4步：Device 解析并返回 RMCPTP 响应帧

Device 解析接收到的二进制帧，提取业务参数，执行测量，返回响应帧。

**关键代码**：`mock_device/tcp_server.py` 第92-198行

### 第5步：Atom 解析 RMCPTP 响应，构建 SOAP 响应

```python
# main_atom.py 第248-252行
result = {'frequency': frequency, 'bandwidth': bandwidth}
if payload and len(payload) > 20:
    result['amplitude'] = struct.unpack('!f', payload[20:24])[0]
```

### 第6步：返回 SOAP 响应给 Proxy

```xml
<ns0:Response xmlns:ns0="http://monitor.rrmp.gov.cn/services/">
  <ns0:ResultCode>0</ns0:ResultCode>
  <ns0:ResultMessage>Success</ns0:ResultMessage>
  <ns0:Data>
    <ns0:frequency>100000000</ns0:frequency>
    <ns0:amplitude>-60.5</ns0:amplitude>
  </ns0:Data>
</ns0:Response>
```

---

## 业务类型定义

| 类型 | 值 | 说明 |
|------|------|------|
| SGLFREQ | 0x10 | 单频测量 |
| IFANALYSIS | 0x11 | 中频分析 |
| DF | 0x12 | 单频测向 |
| IFDF | 0x13 | 中频测向 |
| FSCAN | 0x15 | 频段扫描 |

---

## 关键代码位置

| 文件 | 功能 | 关键函数/类 |
|------|------|-------------|
| `app/proxy_service/routes.py` | SOAP 请求解析和转发 | `dispatch_to_atom_service()` |
| `main_atom.py` | 业务逻辑处理 | `start_sglfreq()` |
| `app/atom_service/protocol_builder.py` | RMCPTP 帧构建 | `RMCPTPBuilder.build_sglfreq_command()` |
| `app/mock_device/tcp_server.py` | RMCPTP 响应处理 | `CommandParser.parse_frame()` |

---

**最后更新**: 2026-04-06
