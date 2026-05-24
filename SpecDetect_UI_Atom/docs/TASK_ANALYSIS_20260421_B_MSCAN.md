# 任务: B_MScan streamsrc 数据分析

**创建日期**: 2026-04-21
**优先级**: 最高
**状态**: 进行中

---

## 目标

通过 soap_proxy 抓取 Real Atom → testool 的 streamsrc 数据，分析 B_MScan 接口的 DT=13 MSCAN 帧格式。

## 数据来源

- SOAP 请求/响应: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\logs\`
- streamsrc 数据: `stream_B_MScan_18013_*.bin`

## 已确认信息

### streamsrc 帧结构

| 字段   | offset | 大小  | 说明             |
| ---- | ------ | --- | -------------- |
| Sync | 0-3    | 4B  | 0xEEEEEEEE     |
| VER  | 4-5    | 2B  | 1 (LE)         |
| STC  | 6-9    | 4B  | 同步通道号          |
| TS   | 10-17  | 8B  | FILETIME       |
| PL   | 18-19  | 2B  | payload长度 (BE) |
| EL   | 20-21  | 2B  | 错误码            |
| PAD  | 22-23  | 2B  | 填充             |
| DT   | 24     | 1B  | 13 = MSCAN     |
| DL   | 25     | 1B  | 16             |

### DT=13 MSCAN 数据格式

根据抓包分析和 testool 输出:

- 频率个数: 1
- 频率: 100.0000MHz
- 电平: 动态值 (29-66 range)

### 帧间隔问题

- 帧位置: 0, 65, 110, 155, 200, 245, 290, 335...
- 帧1(DT=201): 65 bytes
- 帧2+(DT=13): 45 bytes 间隔
- PL=21 但帧长45字节，与 26+21=47 不符

**可能原因**: TCP粘包/重传导致捕获文件不连续

## 待分析项

1. DT=13 MSCAN payload 实际格式
2. 帧长与PL不匹配的原因
3. 频率/电平字段在 payload 中的位置

## 验证数据

testool 解析结果:

```
频率表扫描数据:DT:13 DL:16 
频率个数:1  频率:100.0000MHz,  电平44
```

## 相关文件

- soap_proxy: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\transparent_proxy.py`
- streamsrc 捕获: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\logs\stream_B_MScan_*.bin`
