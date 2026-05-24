# B_MScan streamsrc 数据保存不完整问题

**创建日期**: 2026-04-21
**状态**: 待分析

---

## 问题现象

soap_proxy 透明代理保存 B_MScan 的 streamsrc 数据时，每帧只保存 45 bytes，而其他接口（FSCAN/PSCAN/SglFreqMeas）能完整保存 384 bytes/帧。

## 数据对比

| 接口 | 每帧收到 bytes | 每帧完整大小 | 保存状态 |
|------|---------------|-------------|---------|
| B_FScan | 384 | 384 | ✓ 正常 |
| B_PScan | 384 | 384 | ✓ 正常 |
| B_SglFreqMeas | 384 | 384 | ✓ 正常 |
| B_MScan | 45 | 384 | ✗ 不完整 |

## 日志分析

```
[STREAM/B_MScan] S->C: writing 45 bytes to file, total=45
[STREAM/B_MScan] S->C: writing 45 bytes to file, total=90
[STREAM/B_MScan] S->C: writing 45 bytes to file, total=135
...
```

## 可能原因

1. Real Atom 对 B_MScan 的 streamsrc 发送使用了不同的数据块大小（45 bytes）
2. 或者 Real Atom 在发送 B_MScan 数据时，TCP 发送行为与其他接口不同

## 待确认

需要 Real Atom 开发者检查：
- B_MScan streamsrc 的发送实现
- 是否与其他接口（FSCAN/PSCAN）使用不同的发送逻辑

## 相关文件

- soap_proxy: `D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\soap_proxy\transparent_proxy.py`
- pcap: `D:\arvin\claude_workspace\RXAtomSvcV3\2026-4\20260421_204823_8282_18012_9996.pcap`
