# Proxy 公有信息

> 创建日期：2026-04-11
> 说明：Proxy-A 和 Proxy-B 链路的公有信息

---

## 1. RMCPTP 帧格式

### 1.1 帧头结构 (18字节)

| 字段 | 字节 | 字节序 | 说明 |
|------|------|--------|------|
| dwLength | 4 | 小端 | 帧长度 |
| tmStamp | 8 | 小端 | FILETIME时间戳 (1601-01-01起) |
| nVersion | 2 | **大端** | =7 (0x0007) |
| nMsgType | 1 | 小端 | 消息类型 |
| nFlags | 1 | 小端 | 标志位 |
| nCheckSum | 2 | 小端 | 校验和 |

### 1.2 消息类型 (nMsgType)

| 值 | 类型 | 说明 |
|----|------|------|
| 90 (0x5A) | REQUEST | 设备控制请求 |
| 6 | RESPONSE | 响应消息 |
| 0 | DATA | 数据帧 |

### 1.3 标志位 (nFlags)

| 值 | 说明 |
|----|------|
| 0x01 | 请求帧 |
| 0x00 | 响应帧 |

---

## 2. SOAP 接口定义

### 2.1 接口总览

| # | 接口 | 功能ID | 说明 |
|---|------|--------|------|
| 1 | B_QueryDeviceInfo | - | 设备信息查询 |
| 2 | B_QueryFaciDevStat | - | 设备状态查询 |
| 3 | B_StopMeas | - | 停止测量 |
| 4 | B_SglFreqMeas | 11 | 单频测量 |
| 5 | B_SglFreqDF | 13 | 单频测向 |
| 6 | B_FScan | 15 | 频段扫描 |
| 7 | B_FScanDF | 21 | 频段扫描测向 |
| 8 | B_MScan | 14 | 多信道扫描 |
| 9 | B_MScanDF | 32 | 多信道扫描测向 |
| 10 | B_PScan | 16 | 频谱扫描 |
| 11 | B_WBDF | 25 | 宽带测向 |

### 2.2 接口分类

| 分类 | 接口 | 设备连接 | 说明 |
|------|------|---------|------|
| 查询接口 | B_QueryDeviceInfo, B_QueryFaciDevStat | 不需要 | 直接返回数据 |
| 控制接口 | B_StopMeas | 不需要 | 停止任务 |
| 执行接口 | 其他7个 | 需要 | 需连接设备发送RMCPTP |

### 2.3 funcid 映射

| funcid | 接口 | 业务数据类型 |
|--------|------|-------------|
| 11 | B_SglFreqMeas | SGLFREQ (0x10) |
| 13 | B_SglFreqDF | DF (0x12) |
| 14 | B_MScan | DFSEARCH (0x14) |
| 15 | B_FScan | FSCAN (0x15) |
| 16 | B_PScan | PSCAN (0x17) |
| 21 | B_FScanDF | DF (0x12) |
| 25 | B_WBDF | WBMONDF (0x19) |
| 32 | B_MScanDF | IFDF (0x13) |

---

## 3. 业务数据类型

| 值 | 类型 | 说明 |
|----|------|------|
| 0x10 | SGLFREQ | 单频测量 |
| 0x11 | IFANALYSIS | 中频分析 |
| 0x12 | DF | 单频测向 |
| 0x13 | IFDF | 中频测向 |
| 0x14 | DFSEARCH | 搜索测向 |
| 0x15 | FSCAN | 频段扫描 |
| 0x16 | DSCAN | 数字扫描 |
| 0x17 | PSCAN | 频谱扫描 |
| 0x18 | SPANALYSIS | 频谱分析 |
| 0x19 | WBMONDF | 宽带监测测向 |

---

## 4. 端口分配

| 实例 | 端口 | 用途 |
|------|------|------|
| Proxy-A | 8080 | SOAP 代理服务 |
| Proxy-B | 8081 | SOAP 代理服务 |
| Mock Atom | 9090 | SOAP 服务端 |
| Real Atom | 8282 | SOAP 服务端 |
| Mock Device | 9000 | RMCPTP 服务端 |
| rmcp_proxy | 9996 | TCP 透明代理 |
| Real Device | 9997 | RMCPTP 服务端 |
| streamsrc | 18012 | 设备回调通道 |

---

## 5. streamsrc vs RMCPTP 双通道

| 通道 | 方向 | 角色 | 连接模式 | 用途 |
|------|------|------|----------|------|
| **streamsrc** | 设备→Atom | Atom是TCP服务端，设备是客户端 | **长连接** | 设备数据回调、心跳保活 |
| **RMCPTP** | Atom→Device | Atom是TCP客户端，设备是服务端 | **短连接** | SOAP业务命令/响应 |

---

**最后更新**: 2026-04-11
