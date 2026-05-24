# Task: Sink 模式推送标准帧格式

## 日期

2026-05-23

## 背景

当前 Sink 模式推送的是设备私有 streamsrc 帧格式（62B 帧头 + byte-pair 频谱），与 GWJ003/004 §5.17 定义的标准监测数据帧格式不一致。通过抓取 RXAtomSvcV3（原始 Atom）的 Sink 数据流，确认了标准帧格式的实际结构。

## 目标

为 Sink 模式 FSCAN 实现 GWJ004 §5.17 标准帧格式推送，与 RXAtomSvcV3 行为对齐。Source 模式保持现有 streamsrc 格式不变。

## 协议分析

### GWJ003/004 关键发现

- `outputchannel mode`: `sink`=服务消费方指定, `source`=服务提供方指定
- 所有示例均为 `mode='source'`，Sink 无实操示例
- §5.17 定义标准数据帧格式
- UUID 注册帧在 GWJ004 中无定义，系设备私有协议

### RXAtomSvcV3 抓包验证

#### 帧头 (24B, GWJ004 §5.17)

| 偏移  | 字段     | 字节  | 类型        | 值                                   |
| --- | ------ | --- | --------- | ----------------------------------- |
| 0   | LEADER | 4   | UINT32 BE | 0xEEEEEEEE                          |
| 4   | VER    | 2   | UINT8×2   | [0x01, 0x00]                        |
| 6   | STC    | 4   | UINT32 LE | 通道标识                                |
| 10  | TS     | 9   | struct    | 年(2)+月(1)+日(1)+时(1)+分(1)+秒(1)+毫秒(2) |
| 19  | PL     | 4   | UINT32 LE | 载荷总长 = 1 + 4 + DL                   |
| 23  | EL     | 1   | UINT8     | 0                                   |

#### 帧类型

| DT    | 值          | 说明  | DATA                        |
|:-----:|:----------:| --- | --------------------------- |
| UUID  | 102 (0x66) | 注册帧 | 36B ASCII GUID              |
| FSCAN | 12 (0x0C)  | 频谱帧 | 33B metadata + INT16 LE × n |

#### UUID 帧

- 65 字节总长，在 TpOpen 后、连接设备前发送
- 发送给 Sink outputchannel 远端

#### 私有元数据 (33B)

来自 RXAtomSvcV3 抓包，与 frame.py `_PRIVATE_METADATA_BAND1/2/3` 逐字节一致：

| 偏移      | 字节  | 值             | 含义        | Band间变化 |
| ------- | --- | ------------- | --------- |:-------:|
| [0:2]   | 2   | 0xA101        | 设备 magic  | 不变      |
| [2:4]   | 2   | 0x0005        | 子类型 magic | 不变      |
| [4:8]   | 4   | 0             | zeros     | 不变      |
| [8:16]  | 8   | FLOAT64       | 频段特征值 A   | 变化      |
| [16:24] | 8   | FLOAT64       | 频段特征值 B   | 变化      |
| [24:28] | 4   | 0xC3500000    | 固定 magic  | 不变      |
| [28:30] | 2   | 0x0046/0xA146 | 频段标识      | Band3不同 |
| [30:32] | 2   | 0x0002/0x0001 | 频段序号      | Band3不同 |
| [32]    | 1   | 0x00          | 尾 padding | 不变      |

RXAtom vs frame.py 对比（33B 完全相同）：

```
Band1: 01a10500 00000000 80e854a041000000 30c5daa141000000 000050c34600020000  ← 一致
Band2: 01a10500 00000000 8088dba141000000 306561a341000200 000050c34600020000  ← 一致
Band3: 01a10500 00000000 802862a341000000 808a9fa441000400 000050c346a1010000  ← 一致
```

## 实现

### 文件

| 文件                                      | 操作      | 内容                        |
| --------------------------------------- |:-------:| ------------------------- |
| `stream/standard_frame.py`              | 新建      | 标准 GWJ004 帧构建             |
| `service.py` `_handle_fscan_sink()`     | 改 5 行   | TpOpen 后发 UUID 帧          |
| `service.py` `_start_sink_push()` fscan | 改 ~20 行 | 标准帧 + 复用元数据 + INT16 LE    |
| `stream/frame.py`                       | 不改      | 提供 `_get_band_metadata()` |
| `stream/server.py`                      | 不改      | Source 模式不变               |
| `session.py`                            | 不改      | BandCollector 不变          |

### 解耦验证

- Source 模式: `_handle_fscan()` → `_match_and_start_stream()` → `_push_frame()` — 未修改
- Sink 模式: `_handle_fscan()` → `_handle_fscan_sink()` → `_start_sink_stream()` → `_start_sink_push()` — 仅 fscan 分支
- 两条路径互不调用

### 修复历程

| #   | 问题                       | 根因                                                | 修复                        |
| --- | ------------------------ | ------------------------------------------------- | ------------------------- |
| 1   | Atom 返回 0 bytes (10s 超时) | Proxy `modify_outputchannel()` 未更新 Content-Length | 动态计算 + 更新                 |
| 2   | 推送线程崩溃                   | `self._push_callback` 不存在                         | 改为 `self._push_frame`     |
| 3   | 外部目标 7s 断开               | 缺少 UUID 注册帧                                       | 标准 DT=102 UUID 帧          |
| 4   | 元数据与 RXAtom 不匹配          | `build_metadata()` 自行设计格式                         | 复用 `_get_band_metadata()` |

## 版本

| 组件        | 版本    |
| --------- | ----- |
| SGAtom    | 1.1.9 |
| SOAPProxy | 1.1.7 |

## 后续

- [ ] MSCAN 标准帧（DT=13）
- [ ] PScan / SglFreqMeas 标准帧
- [ ] Sink 模式端到端验证（与 TestTool 联调）
