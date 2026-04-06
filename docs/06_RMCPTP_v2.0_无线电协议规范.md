# 嵘兴无线电管理综合平台传输控制协议

**RX-RMCPTP v2.0**

| 项目 | 内容 |
|------|------|
| 项目名称 | 嵘兴无线电监测综合管理平台 |
| 版本号 | 1.9 |
| 更新日期 | 2012/7/5 |
| 编写者 | 杜小猛 |
| 公司 | 深圳市嵘兴实业发展有限公司 |

---

## 1. 概述

### 1.1 缩略语

| 简写 | 全拼 | 说明 |
|------|------|------|
| RX-RMCPTP | Rongxing Radio Manage Comprehensive Platform Transfer Protocol | 嵘兴无线电综合管理平台实时监测传输协议，用于客户端与服务之间进行数据传输 |

### 1.2 名词解释

| 名词 | 说明 |
|------|------|
| 测向统计时间 | 从设备读取测向数据的时间统计 |
| 监听统计时间 | 从设备读取音频数据的时间统计 |
| 监测统计时间 | 获得测向和音频之外的其他监测数据的时间统计 |
| 校验和 | 使用简单校验算法，保证数据完整性 |
| 数据单元 | 包含业务数据的最小内容 |
| 客户段 | 发送请求命令的通信方 |
| 中间服务 | 提供连续数据的综合平台服务 |
| 监测站设备组合标识 | 13位全国唯一编码（监测站编号8字符+设备组合标识3字符+相同设备组合序号2字符） |

### 1.3 通信连接说明

- **协议基础**: TCP/IP 应用协议
- **连接建立**: 每执行一功能，均单独建立一连接
- **通信流程**: 客户端发起连接 → 发送请求命令 → 服务端应答 → 业务处理 → 双方断开连接

---

## 2. 通用数据报文结构

### 2.1 帧头结构 (RMCPFRAME)

```cpp
#pragma pack(push,1)   
typedef struct tagRmcpFrame
{ 
    DWORD       dwLength;    // 报文长度(BYTE)	
    FILETIME    tmStamp;     // 报文产生时间
    WORD        nVersion;    // 报文版本号 (当前版本: 0x0007)
    BYTE        nDataType;   // 报文数据类型
    BYTE        nFlags;      // 报文标志 
    WORD        nCheckSum;   // 头校验和
} RMCPFRAME,*LPRMCPFRAME;
#pragma pack(pop)
```

### 2.2 报文标志位 (nFlags)

| Bit | 名称 | 说明 |
|-----|------|------|
| 0 | 数据可抛弃标志 | 数据是否可抛弃 |
| 1 | 电平数据标志 | 是否是电平数据 |
| 2 | 场强数据标志 | 是否是场强数据 |
| 4 | 频率放大标志 | 1表示频率被转换为1/10000Hz，0表示Hz |

### 2.3 报文数据类型 (nDataType)

| 值 | 数据类型 | 说明 |
|----|----------|------|
| 0 | 监测业务数据 | 业务数据 |
| 1 | 音频描述头 | 数据中包含音频数据描述头 |
| 2 | 音频数据 | 数据中包含音频数据流 |
| 3 | 分发请求 | 请求中间层发送的数据 |
| 4 | 信息数据 | 数据中包含文本信息 |
| 6 | 业务数据数据描述头 | 该数据帧包含的业务数据是自描述头 |
| 7 | 视频数据描述头 | - |
| 8 | 通知消息 | 中间服务的通知消息 |
| 11 | GPS数据 | - |

### 2.4 头校验和计算

1. 以无符号短整型形式读出时间、长度累加
2. 对结果作两次折半移位相加处理
3. 取反码得到校验和

---

## 3. 数据分发请求报文

```cpp
typedef struct {
    __int64 nTaskid;           // 请求分发数据的任务ID (-1表示获取通知消息)
    char    szUser[64];        // 用户名称
} RMCPREQUEST;
```

---

## 4. 业务数据类型

### 4.1 业务数据类型ID映射

| 业务数据类型 | 数据种类ID (Hex) |
|--------------|------------------|
| 单频测量 (SGLFREQ) | 0x10 |
| 中频分析 (IFANALYSIS) | 0x11 |
| 单频测向 (DF) | 0x12 |
| 中频测向 (IFDF) | 0x13 |
| 离散扫描 (MSACN) | 0x14 |
| 频段扫描 (FSCAN) | 0x15 |
| 数字扫描 (DSCAN) | 0x16 |
| 频谱扫描 (PSCAN) | 0x17 |
| 频谱分析 (SPANALYSIS) | 0x18 |
| 时域分析 (TDANALYSIS) | 0x19 |
| 搜索测向 (DFSEARCH) | 0x14 |
| 频率测向 (SCANDF) | 0x15 |
| 离散信号搜索 (MSEARCH) | 0x16 |
| 信号搜索 (FSEARCH) | 0x17 |
| ITU测量 (ITU) | 0x18 |
| 宽带监测测向 (WBMONDF) | 0x19 |
| 中频宽带测向 (IFDFEXT) | 0x1A |
| 跳频监测 | 0x1B |
| 宽带监测 (WMON) | 0x1C |
| IQ数字解调 (DIGDEM) | 0x1D |
| 宽带扫描 | 0x1E |
| 能量探测 (EDETN) | 0x1F |
| 离散测向 | 0x20 |
| 信号测量 (SIGNALMEAS) | 0x21 |
| 信号识别 (MODREC) | 0x22 |
| 信号告警 (SINA) | 0x23 |
| 和差信号 | 0x24 |
| IQ | 0x25 |
| DDC解调 (DDCDEM) | 0x26 |
| 空间谱测向 (SSDF) | 0x27 |
| 多信道监听 (MULTICHAN) | 0x28 |
| 旋转云台 (ACDF) | 0x29 |
| 视频 | 0x2A |
| 调制模式识别 (DEMREC) | 0x2B |
| 双/多信道分析 (MULCHANANA) | 0x2C |
| 信号压制 | 0x2D |
| 模拟电视 (ANALOGTV) | 0x2E |
| 数字电视 (DIGITALTV) | 0x2F |
| 电视图像 (TVBMP) | 0x30 |
| 荧光谱 (DPX) | 0x31 |
| 摄像头 | 0x32 |
| 频点分析 (FREQMEAS) | 0x33 |

---

## 5. 业务数据描述头

### 5.1 描述头结构 (RMCPBUSINESSHEAD)

```cpp
#pragma pack(push,1)   
typedef struct tagRmcpBusinessHead
{ 
    BYTE         nMonType;      // 业务数据类型
    DWORD        nArrays;       // 业务数组长度	
    CHAR         pOffset[1];    // 业务偏移占位指针
} RMCPBUSINESSHEAD,*LPRMCPBUSINESSHEAD;
#pragma pack(pop)
```

### 5.2 各业务类型描述头定义

#### 5.2.1 单频测量 SGLFREQ (0x10)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | 业务数据类型 = 0x10 |
| nArrays | long | 4 | ITU测量数据个数 |
| freq | __int64 | 8 | 固定频率设定频率 |
| szAntenna | char[64] | 64 | 天线名 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| szITUName | char[16] | 16 | ITU数据名称 |
| fMinValue | float | 4 | 缺省最小值 |
| szUnit | char[10] | 10 | 单位 |

#### 5.2.2 中频分析 IFANALYSIS (0x11)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x11 |
| nArrays | long | 4 | 动态数组数目 |
| freq | __int64 | 8 | 中频分析设定频率 |
| span | __int64 | 8 | 测量跨距(Hz) |
| Ifbw | __int64 | 8 | 中频带宽(Hz) |

#### 5.2.3 中频测向 IFDF (0x13)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x13 |
| nArrays | long | 4 | 动态数组数目 |
| freq | __int64 | 8 | 测量中心频率(Hz) |
| span | __int64 | 8 | 测量跨距(Hz) |
| Ifbw | __int64 | 8 | 频带宽(Hz) |

#### 5.2.4 频段扫描 FSCAN (0x15)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x15 |
| nArrays | long | 4 | 频段扫描段数 |

动态部分 (nArrays组):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| startfreq | __int64 | 8 | 开始频率 |
| endfreq | __int64 | 8 | 结束频率 |
| Step | __int64 | 8 | 步长频率 |
| nPoints | int | 4 | 本段点数 |

#### 5.2.5 频谱分析 SPANALYSIS (0x18)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x18 |
| nArrays | long | 4 | 特殊监测类型个数 |
| curvecount | short | 2 | 曲线条数 |
| Indexclearwrite | byte | 1 | 实时曲线索引号(无实时曲线值为0xFF) |
| Reflevel | float | 4 | 曲线参考电平 |
| Unit | char[10] | 10 | 曲线电平单位 |
| nParamLen | long | 4 | 参数字串长度 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| param | char[] | nParamLen | 监测参数字符串 |

#### 5.2.6 ITU测量 ITU (0x18)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x18 |
| nArrays | long | 4 | ITU测量数据个数 |
| freq | __int64 | 8 | 固定频率设定频率 |
| szAntenna | char[64] | 64 | 天线名 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| szITUName | char[16] | 16 | ITU数据名称 |
| fMinValue | float | 4 | 缺省最小值 |
| szUnit | char[10] | 10 | 单位 |

#### 5.2.7 宽带监测 WMON (0x1C)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x1C |
| nArrays | long | 4 | 扫描段数 |
| level | float | 4 | 参考电平 |
| unit | char[10] | 10 | 参考电平单位 |
| nResultNum | long | 4 | 扩展数据数 = 9 |

扩展数据标识 (20字节):
| 偏移 | 名称 | 单位 |
|------|------|------|
| 0-19 | TimeSymbol | s |
| 20-29 | FreqSymbol | Hz |
| 30-49 | RbwSymbol | Hz |
| 50-69 | AlarmsnrSymbol | dB |
| 70-89 | AlarmsRateSymbol | kHz |
| 90-109 | AlarmdevSymbol | kHz |
| 110-129 | ModemSymbol | - |
| 130-149 | AlarmconSymbol | % |
| 150-169 | PreciousTimeSymbol | s |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nStartFreq | float | 4 | 开始频率 |
| nStopFreq | float | 4 | 结束频率 |
| rbw | float | 4 | 带宽 |

#### 5.2.8 能量探测 EDETN (0x1F)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x1F |
| nArrays | long | 4 | 扫描段数 |
| level | float | 4 | 参考电平 |
| unit | char[10] | 10 | 参考电平单位 |
| nResultNum | long | 4 | 扩展数据数 = 5 |

扩展数据标识 (20字节):
| 偏移 | 名称 | 单位 |
|------|------|------|
| 0-19 | TimeSymbol | s |
| 20-39 | FreqSymbol | Hz |
| 40-59 | RbwSymbol | Hz |
| 60-79 | alarmamplSymbol | dBm |
| 80-99 | PreciousTimeSymbol | s |

#### 5.2.9 信号识别 MODREC (0x22)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x22 |
| nArrays | long | 4 | = 0 |
| level | float | 4 | 参考电平 |
| unit | char[10] | 10 | 参考电平单位 |
| nResultNum | long | 4 | 扩展数据数 = 9 |
| nCentFreq | __int64 | 8 | 中心频率 |
| nSpan | __int64 | 8 | 跨距 |
| nIFBW | __int64 | 8 | 带宽 |

#### 5.2.10 DDC解调 DDCDEM (0x26)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x26 |
| nArrays | long | 4 | 动态数组数目 |
| freq | __int64 | 8 | 中频分析设定频率 |
| span | __int64 | 8 | 测量跨距(Hz) |
| demfreq | __int64 | 8 | 解调频率 |
| Demifbw | __int64 | 8 | 解调带宽 |

#### 5.2.11 空间谱测向 SSDF (0x27)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x27 |
| nArrays | long | 4 | 动态数组数目 |
| freq | __int64 | 8 | 测量中心频率(Hz) |
| span | __int64 | 8 | 跨距(Hz) |
| ifbw | __int64 | 8 | 中频带宽(Hz) |

#### 5.2.12 多信道监听 MULTICHAN (0x28)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x28 |
| nArrays | long | 4 | 监测数据的通道总数 |
| AudioLength | long | 4 | 音频数据长度 |

动态部分 (nArrays组):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| Index | byte | 1 | 通道索引 |
| freq | __int64 | 8 | 开始频率 |
| span | __int64 | 8 | 跨距 |
| Ifbw | __int64 | 8 | 带宽 |

#### 5.2.13 旋转云台 ACDF (0x29)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x29 |
| nArrays | long | 4 | 动态数组数目 |
| freq | __int64 | 8 | 测量中心频率(Hz) |

#### 5.2.14 调制模式识别 DEMREC (0x2B)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x2B |
| nArrays | long | 4 | ITU个数 |
| freq | __int64 | 8 | 中频分析设定频率 |
| span | __int64 | 8 | 测量跨距(Hz) |
| Ifbw | __int64 | 8 | 中频带宽(Hz) |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| szITUName | char[16] | 16 | ITU数据名称 |
| fMinValue | float | 4 | 缺省最小值 |
| szUnit | char[10] | 10 | 单位 |

#### 5.2.15 双/多信道分析 MULCHANANA (0x2C)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x2C |
| nArrays | long | 4 | 信道个数 |

动态部分 (nArrays组):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| freq | __int64 | 8 | - |
| span | __int64 | 8 | - |
| ifbw | __int64 | 8 | - |
| ITU项个数 | int | 4 | (为零表示没有ITU测量项) |

---

## 6. 业务数据报文

### 6.1 业务数据结构 (RMCPBUSINESSDATA)

```cpp
#pragma pack(push,1)   
typedef struct tagRmcpBusinessData
{ 
    BYTE         nBdType;      // 业务数据类型
    SHORT        nFlags;       // 业务数据标志 	
    DWORD        nArrays;      // 业务数组数目
    DWORD        nOffset;      // 业务数组偏移   
    CHAR         pOffset[1];  // 业务数组偏移占位   
} RMCPBUSINESSDATA,*LPRMCPBUSINESSDATA;
#pragma pack(pop)
```

### 6.2 业务数据标志位 (nFlags)

| Bit | 说明 |
|-----|------|
| 0 | 基础业务数据 |
| 1 | 自动背噪数据 |
| 2 | 占用度统计数据 |
| 3 | 手工背噪数据 |
| 4-15 | 保留 |

### 6.3 各业务数据类型数据格式

#### 6.3.1 单频测量 SGLFREQ (0x10)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x10 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | ITU测量结果数目 |
| nOffset | long | 4 | 相对首索引偏移 |
| freq | __int64 | 8 | 实际工作频率 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | float | 4 | 测量项结果 (nArrays组) |
| occ | short | 2 | 占用度 (1个占用度值*100) |
| thr | short | 2 | 手工门限 (1个手工门限值*100) |

#### 6.3.2 中频分析 IFANALYSIS (0x11)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x11 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 频谱曲线点数目 |
| nOffset | long | 4 | = 0 |
| freq | __int64 | 8 | 实际工作频率 |
| Level | short | 2 | 中心电平(实际值*100) |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | short | 2 | 电平 (频谱电平实际值*100, nArrays组) |

#### 6.3.3 单频测向 DF (0x12)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x12 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 动态数组数目 |
| nOffset | long | 4 | 相对首索引偏移 |
| Level | short | 2 | 电平(实际值*100) |
| DfLevel | short | 2 | 测向电平(实际值*100) |
| Qulity | float | 4 | 测向质量 |
| Azumith | float | 4 | 方位角 |
| Elevation | float | 4 | 俯仰角 |
| compass | float | 4 | 罗盘值 |

#### 6.3.4 中频测向 IFDF (0x13)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x13 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 频谱曲线点数目 |
| nOffset | long | 4 | 相对首索引偏移 |
| Level | short | 2 | 电平(实际值*100) |
| DfLevel | short | 2 | 测向电平(实际值*100) |
| Qulity | float | 4 | 测向质量 |
| Azumith | float | 4 | 方位角 |
| Elevation | float | 4 | 俯仰角 |
| compass | float | 4 | 罗盘值 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | short | 2 | 电平 (频谱电平实际值*100, nArrays组) |

#### 6.3.5 频段扫描 FSCAN (0x15)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x15 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 离散扫描数点数 |
| nOffset | long | 4 | 相对首索引偏移 |

动态部分 (根据nFlags可选):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | short | 2 | 电平(频谱电平实际值*100, nArrays组) |
| thr | short | 8 | 自动背噪 (电平实际值*100, 可选) |
| occ | __int64 | 8 | 占用度 (高4字节有效采样次数,低4字节总采样次数, 可选) |
| thr | short | 2 | 手工背噪 (电平实际值*100, 可选) |

#### 6.3.6 频谱分析 SPANALYSIS (0x18)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x18 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 曲线点数 |
| nOffset | long | 4 | 相对首索引偏移 |
| Indexcurve | short | 2 | 曲线索引值 |
| freq | __int64 | 8 | 中心频率 |
| span | __int64 | 8 | 跨距 |
| DatakindLen | long | 4 | 特殊监测值字符串长度 |
| DataKindsValue | char[] | DatakindLen | 特殊监测字符串 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | short | 2 | 电平(频谱电平实际值*100, nArrays组) |

#### 6.3.7 搜索测向 DFSEARCH (0x14)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x14 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 本包数据所含数据组数 |
| nOffset | long | 4 | 相对首索引偏移 |
| DataType | int | 4 | 1=频点信息, 2=测向数据, 3=频谱数据 |

DataType=1时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| Frequency | __int64 | 8 | 测量频率 |
| Band | __int64 | 8 | 测向带宽 |
| IFBW | __int64 | 8 | 中频带宽 |

DataType=2时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| DfLevel | short | 2 | 测向电平(实际值*100) |
| Qulity | unsigned short | 2 | 测向质量(实际值*100) |
| Azumith | unsigned short | 2 | 方位角(实际值*100) |
| Elevation | short | 2 | 俯仰角(实际值*100) |
| Compass | unsigned short | 2 | 罗盘值(实际值*100) |
| occ | __int64 | 8 | 占用度(可选) |
| thr | short | 2 | 手工背噪(可选) |

DataType=3时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| Centerlevel | short | 2 | 中心电平(实际电平值*100) |
| LevelCount | int | 4 | 电平个数 |

#### 6.3.8 ITU测量 ITU (0x18)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x18 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | ITU测量结果数目 |
| nOffset | long | 4 | 相对首索引偏移 |
| freq | __int64 | 8 | 实际工作频率 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | float | 4 | 测量项结果 (nArrays组) |

#### 6.3.9 宽带监测 WMON (0x1C)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x1C |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 动态数组数目 |
| nOffset | long | 4 | = 0 |
| dataType | BYTE | 1 | 0=原始数据, 1=扩展数据 |

dataType=0时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| fStartFreq | float | 4 | 开始频率 |
| fStopFreq | float | 4 | 结束频率 |
| Overlap | BYTE | 1 | 过载标识 |
| value | short | 2 | 电平值(nArrays个) |

dataType=1时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | float | 4 | 扩展数据(nArrays-3个) |
| AlarmDesc | char[32] | 32 | 调制类型描述 |
| value | float | 4 | 可信度 |
| value | float | 4 | 子时间 |

#### 6.3.10 能量探测 EDETN (0x1F)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x1F |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 动态数组数目 |
| nOffset | long | 4 | = 0 |
| dataType | BYTE | 1 | 0=原始数据, 1=扩展数据 |

dataType=0时: 同WMON原始数据格式

dataType=1时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | float | 4 | 扩展数据(nArrays个) |

#### 6.3.11 信号识别 MODREC (0x22)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x22 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 动态数组数目 |
| nOffset | long | 4 | = 0 |
| dataType | BYTE | 1 | 0=原始数据, 1=扩展数据 |

dataType=0时: 同WMON原始数据格式

dataType=1时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | float | 4 | 扩展数据(nArrays-3个) |
| AlarmDesc | char[32] | 32 | 调制类型描述 |
| value | float | 4 | 可信度 |
| value | float | 4 | 子时间 |

#### 6.3.12 数字解调 DIGDEM (0x1D)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x1D |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | IQ数据总数 |
| nOffset | long | 4 | = 0 |
| Unit | char[4] | 4 | IQ数据类型 |
| Time stamp | __int64 | 8 | 时间戳 |

动态部分:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| value | short | 2 | IQ数据(一对值中的一个, nArrays组) |

#### 6.3.13 空间谱测向 SSDF (0x27)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x27 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 动态数组数目 |
| nOffset | long | 4 | = 0 |
| nType | byte | 1 | 0=测向数据, 1=频谱数据 |

nType=0时 (nArrays组):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nMonLevel | short | 2 | 监测电平(EFFF无效, 实际电平值*100) |
| compass | float | 4 | 实际罗盘值 |
| DfLevel | short | 2 | 测向电平(实际值*100) |
| Qulity | float | 4 | 实际测向质量 |
| Azumith | float | 4 | 实际方位角 |
| Elevation | float | 4 | 实际俯仰角 |

nType=1时 (nArrays组):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nLevel | short | 2 | 测向电平(实际值*100) |

#### 6.3.14 多通道监听 MULTICHAN (0x28)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x28 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | 频谱曲线点数目或音频数据长度 |
| nOffset | long | 4 | 相对首索引偏移(通道索引) |
| nCdType | byte | 1 | 0=监测数据, 2=音频业务 |

nCdType=0时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| freq | __int64 | 8 | 实际工作频率 |
| Level | short | 2 | 中心电平(实际值*100) |
| value | short | 2 | 电平(频谱电平实际值*100, nArrays组) |

nCdType=2时:
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| AudioData | char[] | nArrays | 音频业务数据 |

#### 6.3.15 荧光谱 DPX (0x31)

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| nBdType | byte | 1 | = 0x31 |
| nFlags | short | 2 | 业务数据标志 |
| nArrays | long | 4 | DPX数据组数 |
| nOffset | long | 4 | 相对首索引偏移 |
| nTotalPoints | long | 4 | 总点数 |
| nSampleRate | __int64 | 8 | 采样率 |
| nRBW | __int64 | 8 | 分辨率(Hz) |
| dRate | double | 8 | 采样比率 |
| nMinLevel | short | 2 | 最小幅度值(实际值*100) |

动态部分 (DPXDATA格式):
| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| mask | BYTE[20] | 20 | 160位掩码(bit位置表示-40dBuV~-120dBuV幅度值) |
| count | BYTE[] | 可变 | 非零掩码对应的数据个数 |

---

## 7. 调制模式类型定义

| 值 | 调制类型 | 说明 |
|----|----------|------|
| 0x01 | FM | 调频 |
| 0x02 | BPSK | 二相相移键控 |
| 0x03 | QPSK | 四相相移键控 |
| 0x04 | 8PSK | 八相相移键控 |
| 0x05 | 16QAM | 16进制正交调幅 |
| 0x06 | 32QAM | 32进制正交调幅 |
| 0x07 | 64QAM | 64进制正交调幅 |
| 0x08 | 128QAM | 128进制正交调幅 |
| 0x09 | 256QAM | 256进制正交调幅 |
| 0x0A | AM | 调幅 |
| 0x0B | SSB | 单边带 |
| 0x0C | DSB | 双边带 |
| 0x0D | RSB | 残余边带 |
| 0x0E | PAM | 脉冲调幅 |
| 0x0F | FSK | 频移键控 |
| 0x10 | PSK | 脉冲相移键控 |
| 0x11 | ASK | 振幅键控 |
| 0x12 | MSK | 最小频移键控 |
| 0x13 | GMSK | 高斯最小频移键控 |
| 0x14 | FM-FDM | 频分多路调频 |
| 0x15 | 512QAM | 512进制正交调幅 |
| 0x16 | FM-TV | 调频电视 |
| 0x17 | OFDM | 正交频分多路 |
| 0x18 | OQPSK | 交错四相调制 |
| 0x19 | π/4QPSK | π/4移相四相调制 |
| 0x1A | π/4DQPSK | π/4移相四相差分相移键控 |
| 0x1B | 其它 | - |
| 0x1C | 1024QAM | 1024进制正交调幅 |
| 0x1D | PWM | 脉冲宽度调制 |
| 0x00 | - | 不要求返回调制方式 |
| 0x03E7 (999) | - | 无法取得调制方式 |

---

## 8. 通知消息

```cpp
#pragma pack(push,1)   
typedef struct tagRmcpNotifyFrame
{ 
    RMCPFRAME    rmcpFrame;    // 帧头
    SHORT        nServiceID;   // 服务ID
    SHORT        nNotifyID;    // 通知消息ID
    INT64        nTaskID;      // 任务ID
} RMCPNOTIFYFRAME,*LPRMCPNOTIFYFRAME;
#pragma pack(pop)
```

---

## 9. GPS数据

```cpp
#pragma pack(push,1)   
typedef struct tagRmcpGPSFrame
{ 
    RMCPFRAME    rmcpFrame;    // 帧头
    UINT         nStationID;   // 站点ID
    FLOAT        nLongitude;   // 经度
    FLOAT        nLatitude;    // 纬度
} RMCPGPSRAME,*LPRMCPGPSRAME;
#pragma pack(pop)
```

---

## 10. 通用频点分析协议 FREQMEAS (0x33)

该功能针对单频点，可根据设备不同返回ITU数据、频谱数据、IQ数据、音频数据中的一种或几种。

### 10.1 FLAGS位定义

| Bit | 内容 |
|-----|------|
| 0 | 信道编号 |
| 1 | 中心频率 |
| 2 | 电平 |
| 3 | 场强 |
| 4 | 测向电平 |
| 5 | 测向角度 |
| 6 | 测向质量 |
| 7 | 俯仰角 |
| 8 | 罗盘值 |
| 9 | IQ数据 |
| 10 | ITU测量结果 |
| 11 | 调制模式识别 |
| 12 | GPS结果 |
| 13 | TDOA结果 |
| 14 | 频谱 |
| 15 | 本包数据是否含描述头 |
| 16-31 | 保留 |

### 10.2 子数据结构

#### IQ数据
```cpp
struct IQPAIR {
    short  i;  // I路数据
    short  q;  // Q路数据
};
```

#### ITU测量结果
```cpp
struct {
    short nITUNum;      // ITU测量个数
    float fValue[0];    // ITU值
};
```

#### 调制模式识别
```cpp
struct {
    int   nModIndex;    // 调制模式类型
    float fProp;        // 识别概率
    char  szMod[32];   // 调制模式名字
};
```

#### GPS结果
```cpp
struct {
    char   szTime[16];      // UTC时间(hhmmss.sss)
    char   szDate[16];      // UTC日期(YYYYMMDD)
    bool   bValid;          // 定位是否有效
    double dLongi;          // 经度(度)
    char   cLongi;          // E-东经, W-西经
    double dLati;           // 纬度(度)
    char   cLati;           // N-北纬, S-南纬
    float  fAlti;           // 海拔(米)
    float  fSpeed;          // 速度(米/秒)
    float  fDirection;      // 移动方向[0-360)
    char   cMagOff;         // 磁偏角方向
    float  fMagOff;         // 磁偏角(度)
};
```

---

## 11. 版本历史

| 版本 | 作者 | 日期 | 变更内容 |
|------|------|------|----------|
| 1.9 | 杜小猛 | 2012/7/5 | 修正报文标志位，频率放大标志为1表示频率被放大1000倍 |
| 1.8 | - | 2011/12/14 | 增加中频宽带测向、调制模式识别、频谱分析描述头定义修正 |
| 1.7 | - | 2011/11/4 | 增加IQ数字解调、DDC解调、空间谱测向、多信道监听、旋转云台协议定义 |
| 1.6 | 杜小猛 | 2010/12/06 | 添加宽带监测、能量探测、信号识别、信号告警 |
| 1.5 | 杜小猛 | 2009/11/12 | 调整频段扫描返回占用度数据格式为(有效采样/总采样)，占用度数据长度8字节 |
| 1.4 | - | 2009-8-24 | 添加通知消息接口 |
| 1.3 | 杜小猛 | 2009-8-22 | 修正数据校验 |
| 1.2 | 杜小猛 | 2009-8-21 | 添加音频数据格式 |
| 1.1 | 杜小猛 | 2009-8-17 | 修正业务数据传输格式 |
| 1.0 | 杜小猛 | 2009-8-10 | 建立初稿 |
