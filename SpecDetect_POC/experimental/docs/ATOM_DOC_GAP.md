# Atom 内部处理：国标文档归档说明

**日期**: 2026-04-15
**结论**: GWJ004/GWJ006 均**未规定** Atom 如何压缩/量化/切片/转发设备信号。

## 两份文档覆盖范围

仅规定**数据结构、单位、帧格式**，不涉及处理算法。

| 规定项 | 内容 | 来源 |
|---|---|---|
| 电平编码 | INT16，单位 0.1 dBμV | GWJ004 t34-43，GWJ006 t10/t31/t37/t40 |
| 无效值 | `0xEFFF` | GWJ006 p206 |
| 单位 | dBm 或 dBμV | GWJ004 ampunit |
| 帧头 | STC 通道标识、TS 时间戳、二进制编码 | GWJ004 p1133-1140 |
| 静噪门限 | `squelchthreshold` (dBμV)、`squelchswitch` (on/off) | GWJ004 t9r13, t10r0 |
| 检波方式 | peak/avg/rms/qbk/… | GWJ004 t9r12 |

## 未涉及内容（属 Atom 私有实现）

- 多帧平均、平滑、降采样
- 量化等级（实测 streamsrc 仅 16 级，rmcp 848 级）
- 底噪压平（实测 -62.8 dBm 占 33%）
- 分片规则（streamsrc 65 字节/帧，18 电平/帧，529/434 重组）
- streamsrc 私有协议（18012 端口）

## 含义

Atom 输出 streamsrc 的量化/压缩/切片行为 = **厂商私有实现**，不是国标行为。
国标仅给出容器格式；压缩策略需继续靠抓包+代码逆向分析。

## 配置入口线索（可能可调）

- `squelchthreshold` + `squelchswitch`: 或与 -62.8 dBm 底噪门限相关
- `detector`: 检波方式可能影响输出分布
- `samples`: 采样点数
