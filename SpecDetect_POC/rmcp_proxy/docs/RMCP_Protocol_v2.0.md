# RX-RMCPTP 通信协议 v2.0

## 协议概述

RX-RMCPTP (Radio Monitoring and Control Protocol) 是嵘兴无线电监测综合平台使用的通信协议。

---

## 帧头结构 (RMCPFRAME) - 已验证

```c
#pragma pack(push, 1)
typedef struct tagRmcpFrame
{
    DWORD  dwLength;     // 帧长度 (4字节, 小端)
    FILETIME tmStamp;    // 时间戳 (8字节, 小端)
    WORD nVersion;       // 版本号 (2字节, 大端) = 7
    BYTE nMsgType;      // 消息类型 (1字节, 小端)
    BYTE nFlags;        // 标志 (1字节, 小端)
    WORD nCheckSum;     // 头校验和 (2字节, 小端)
} RMCPFRAME, *LPRMCPFRAME;
#pragma pack(pop)
```

**帧头大小**: 4 + 8 + 2 + 1 + 1 + 2 = 18 字节

### 字节序说明
- **小端序**: dwLength, tmStamp, nMsgType, nFlags, nCheckSum
- **大端序**: nVersion

---

## 消息类型 (nMsgType)

| 值 | 类型 | 说明 |
|----|------|------|
| 6 | RESP | 响应消息 |
| 90 | 0x5A | 请求消息 (设备控制) |

---

## 标志位定义 (nFlags)

| 位 | 说明 |
|----|------|
| 7-1 | 预留 |
| 0 | 请求/响应标志? (0=响应, 1=请求?) |

---

## 帧结构分类

### 1. 请求帧 (设备控制)

```
偏移0-3:   dwLength (帧长度, 小端)
偏移4-11:  tmStamp (8字节时间戳, 小端)
偏移12-13: nVersion = 7 (大端)
偏移14:    nMsgType = 90 (0x5A)
偏移15:    nFlags
偏移16-17: nCheckSum
偏移18+:   数据 (XML/SOAP格式)
```

**示例请求帧** (700字节):
- nMsgType = 90 (0x5A)
- 数据部分为XML格式

### 2. 响应帧 (设备控制响应)

```
偏移0-3:   dwLength (帧长度, 小端)
偏移4-11:  tmStamp (8字节时间戳, 小端)
偏移12-13: nVersion = 7 (大端)
偏移14:    nMsgType = 6
偏移15:    nFlags
偏移16-17: nCheckSum
偏移18+:   响应数据 (二进制格式)
```

**示例响应帧** (51字节):
- nMsgType = 6
- 包含操作结果状态

### 3. 数据帧 (持续传输)

```
偏移0-3:   dwLength (帧长度, 小端) = 1053, 863等
偏移4-11:  tmStamp (8字节时间戳, 小端)
偏移12-13: nVersion = 7 (大端)
偏移14:    nMsgType? (0x1D=29 或 0x5F=95)
偏移15:    nFlags = 1
偏移16-17: nCheckSum
偏移18+:   业务数据
```

**数据帧类型**:
- 1053字节帧: 包含完整业务数据
- 863字节帧: 可能是分包或不同数据类型

---

## 业务数据类型 (nDataType)

| 值 | 类型 | 说明 |
|----|------|------|
| 10 | AUDIO | 音频测量 |
| 11 | IFMEAS | 中频测量 |
| 12 | DF | 测向 |
| 13 | DSCAN | 离散扫描 |
| 14 | FSCAN | 频谱扫描 |
| 15 | PSCAN | 功率扫描 |
| 16 | ? | 数字扫描 |
| 17 | SPANALYSIS | 频谱分析 |
| 18 | TDANALYSIS | 时域分析 |
| 19 | DFSEARCH | 跳频检测 |
| 20 | SCANDF | 频率测量 |
| 21 | MSEARCH | 离散信号搜索 |
| 22 | FSEARCH | 频率搜索 |
| 23 | ITU | ITU监测 |
| 24 | WBMONDF | 宽带监测 |
| 25 | IFANALYSIS | 中频分析 |
| 26 | IFDFEXT | 中频解调 |
| 27 | DIGDEM | 数字解调 |
| 28 | DDCDEM | IQ解调 |
| 29 | ? | 噪声测量 |
| 30 | EDETN | 能量检测 |
| 31 | ? | 离散监测 |
| 32 | SIGNALMEAS | 信号测量 |
| 33 | TCI | TCI (实际为ITU) |
| 34 | MODREC | 信号识别 |
| 35 | SINA | 信号告警 |
| 36 | ? | 干扰信号 |
| 37 | ? | IQ占用度 |
| 38 | ? | GPS占用度 |
| 39 | ? | DDC占用度 |
| 40 | MULTICHAN | 多信道监测 |
| 41 | ACDF | 旋转变换 |
| 42 | ? | 音频 |
| 43 | DEMREC | 调制模式识别 |
| 44 | MULCHANANA | 双/多信道分析 |
| 45 | ? | 信号压扩 |
| 46 | ? | 模拟检波 |
| 47 | ? | 峰值检波 |
| 48 | ? | 频谱图 |
| 49 | ? | 偏置估算 |
| 50 | ? | 频率偏移 |
| 51 | ? | 业务 |

---

## 设备控制请求示例

### XML请求格式

```xml
<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="15">
        <group index="0">
            <item name="startfreq" value="137MHz" />
            <item name="stopfreq" value="173MHz" />
            <item name="step" value="25kHz" />
            <item name="gainctrl" value="AGC"  />
            <item name="rfworkmode" value="0" />
            <item name="scanmode" value="0" />
            <item name="antpol" value="b4b9d6b1" />
            <item name="anttype" value="OFF" />
            <item name="ifatt" value="0" />
        </group>
    </parameter>
    <other_param />
</action>
```

### 请求参数说明

| 参数 | 说明 | 示例值 |
|------|------|--------|
| stationid | 站点ID | 53090001 |
| deviceid | 设备ID | 00106 |
| devicename | 设备名称 | MS845 |
| funcid | 功能ID | 15 |
| startfreq | 起始频率 | 137MHz |
| stopfreq | 结束频率 | 173MHz |
| step | 步进 | 25kHz |
| gainctrl | 增益控制 | AGC |
| rfworkmode | 射频工作模式 | 0 |
| scanmode | 扫描模式 | 0 |
| antpol | 天线极化 | b4b9d6b1 |
| anttype | 天线类型 | OFF |
| ifatt | 中频衰减 | 0 |

---

## AtomSvcV3.exe 内部帧解析

用户程序解析出的帧头字段（用于应用层显示）：

```
LEADER = -286331154 (0xEEEEEEEE - 未初始化/无效标记)
VER = 1
STC = 1775813919
TS = 2026-4-10 17:42:5:41
PL = 1062 (帧长度)
EL = 0
DT = 12 (测向/DF)
DL = 1057 (数据长度)
```

**注意**: 这些字段是 AtomSvcV3.exe 内部解析后的格式，与 TCP payload 的封装格式不同。

---

## 版本历史

- v1.9: 修正报文标志位，如果频率放大标志为1，表示频率被放大1000倍
- v1.8: 增加中频带测向、增加调制模式识别、频谱分析的描述头定义
- v1.7: 增加IQ数字解调(29)、DDC解调(38)、空间谱测向(39)、多信道监测(40)、旋转变换(41)协议定义
- v1.6: 添加宽带监测、能量探测、信号识别、信号告警
- v1.5: 调整频谱扫描返回占用度的数据格式为(有效采样/总采样)、调整所有的占用度数据长度为8字节
- v1.4: 添加通知消息接口
- v1.3: 修正数据校验
- v1.2: 添加音频数据格式
- v1.1: 修正业务数据传输格式
- v1.0: 建立初稿

---

## 注意事项

1. **字节序**: 大部分字段使用小端序，但 nVersion 使用大端序
2. **帧头校验和**: nCheckSum 计算方式需进一步确认
3. **业务数据传输**: 不需要接收方回应，通信服务可对业务进行异步处理

---

## 实际抓包记录 (2026-04-10)

### 抓包环境
- 接口: 以太网
- 端口: 9999
- 设备: 172.18.114.231

### 请求响应交互

1. **TCP三次握手** (帧1-3)
2. **客户端发送请求** (帧4): 700字节, nMsgType=90, XML格式
3. **设备返回响应** (帧5): 51字节, nMsgType=6, 二进制状态
4. **设备持续发送数据** (帧7+): 1053/863字节帧

### 帧头字段验证

| 帧类型 | 长度 | dwLength | nVersion | nMsgType | nFlags |
|--------|------|----------|----------|----------|--------|
| 请求帧 | 700B | 699 | 7(大端) | 90(0x5A) | 1 |
| 响应帧 | 51B | 51 | 7(大端) | 6 | 0 |
| 数据帧 | 1053B | 1053 | 7(大端) | 29(0x1D) | 1 |
| 数据帧 | 863B | 863 | 7(大端) | 95(0x5F) | 1 |
