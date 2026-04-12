# 任务清单 - Atom数据整理器开发

## 目标

模拟 Atom 解析设备原始数据，填充元数据字段。

## 背景

| 数据来源 | LEADER | VER | STC | PL | EL | 频段信息 |
|---------|--------|-----|-----|----|----|---------|
| 设备原始 (rmcp_proxy) | 271 (简化) | 0 | 0 | 0 | 0 | 全部为0 |
| 用户测试应用回调 | 0xEEEE1DE6 (标准) | 1 | 有值 | 1062 | 0 | 完整数据 |

**结论**: Atom 对设备原始数据进行重组，补充元数据后回调给用户。

---

## 任务列表

### Task 1: 分析简化格式 payload 结构
**状态**: ✅ 已完成

简化格式 payload 结构 (1035 字节):
- Byte 0-3: LEADER = 271 (0x10F)
- Byte 4: VER = 2
- Byte 5-10: 保留 (0)
- Byte 11-end: 电平数据 ((len-11)/2 水平 × 2 字节)

---

## 电平解码公式（重要发现）

### 问题
设备发送的电平原始值（如 -612）是什么含义？

### 分析过程

1. **rmcp_proxy 原始数据**: `[-612, -575, -673, ...]`
2. **用户日志显示值**: `[-61, -57, -67, ...]`
3. **关系**: -612 ÷ 10 = -61.2 ≈ -61

### 结论

**设备编码**: 实际 dBm 值 × 10 = 发送的原始值
- 设备内部 ADC 得到 -61.2 dBm
- 编码为 -612 发送（节省传输空间）
- 我们收到后需要 ÷10 解码

**解码公式**:
```
dBm = signed_short / 10.0
```

例如:
| 原始值 | ÷10 | dBm |
|--------|------|-----|
| -612 | -61.2 | -61.2 dBm |
| -575 | -57.5 | -57.5 dBm |
| -673 | -67.3 | -67.3 dBm |

### 代码实现

```python
# 简化格式电平解码
offset = 11
while offset + 1 < len(payload):
    val = struct.unpack('<h', payload[offset:offset+2])[0]
    dbm = round(val / 10.0, 1)  # 解码: dBm×10 → dBm
    levels.append(dbm)
    offset += 2
```

---

### 修正历史
- 最初错误使用 ÷256
- 2026-04-12 18:15 通过 18:11 时段数据对比确认正确公式为 ÷10

---

### Task 2: 对照协议文档找出字段映射
**状态**: ✅ 已完成

通过 rmcp_proxy 抓包数据分析:
- nArrays = (payload长度 - 11) / 2 = 512
- 频段信息由请求参数填充 (startfreq, stopfreq, step)
- 标准格式 LEADER = 0xEEEE1DE6 = -286331154

---

### Task 3: 实现 AtomDataFormatter 类
**状态**: ✅ 已完成

已创建 `experimental/atom_data_formatter.py`

核心功能:
- 解析简化格式 payload (offset=11, ÷10)
- 填充标准格式元数据 (LEADER=0xEEEE1DE6, VER=1 等)
- 根据请求参数填充频段信息

---

### Task 4: 集成到 streaming_receiver.py
**状态**: ✅ 已完成

已更新 `streaming_receiver.py`:
- 添加 `AtomDataFormatter` 导入
- `receive_streaming_data()` 新增 `request_params` 参数
- `save_to_json()` 更新字段映射 (LEADER, TS 等)
- 修正简化格式解析: offset=11, ÷10
- 测试通过: 28 帧, 512 levels/帧, 标准格式输出

---

## 任务完成总结

| Task | 状态 | 说明 |
|------|------|------|
| Task 1: 分析简化格式 payload 结构 | ✅ | 11字节头 + offset=11 电平数据 |
| Task 2: 对照协议文档 | ✅ | nArrays 计算方式: (len-11)/2 |
| Task 3: 实现 AtomDataFormatter | ✅ | `experimental/atom_data_formatter.py` |
| Task 4: 集成到 streaming_receiver | ✅ | 使用 request_params 传递频率参数 |

**创建文件**:
- `experimental/atom_data_formatter.py` - Atom 数据整理器
- `experimental/TASKS_20260412_atom_parser.md` - 任务文档

**输出文件**:
- `experimental/data/streaming_fscan_fixed_20260412_181406.json` - 修正后的测试数据

**关键修正**:
- 电平公式: ÷256 → ÷10 (通过 18:11 时段数据对比确认)

根据 Task 1-2 的分析结果，实现数据整理器：

```python
class AtomDataFormatter:
    """模拟 Atom 对设备原始数据的整理"""

    def __init__(self, request_params: dict):
        """
        初始化时需要传入请求参数（用于填充频率信息）
        request_params: {
            'startfreq': '137MHz',
            'stopfreq': '173MHz',
            'step': '25kHz',
            'total_channels': 1441,  # 可选，从请求中计算
            ...
        }
        """

    def format_fscan_data(self, raw_payload: bytes) -> dict:
        """
        将设备原始 payload 转换为标准 FSCAN 格式
        返回包含完整元数据的字典
        """
```

---

### Task 4: 验证输出格式
**状态**: 待开始

对比整理后的数据与用户测试应用的回调格式：
- LEADER = 0xEEEE1DE6
- VER = 1
- STC = 时间戳
- PL = payload 长度
- 频段信息完整

---

### Task 5: 集成到 streaming_receiver.py
**状态**: 待开始

将 AtomDataFormatter 集成到现有的 streaming 解析流程中。

---

## 参考：用户测试应用回调格式（期望输出）

```
LEADER:-286331154 VER:1 STC:1775980586 TS:2026-4-12 15:56:29:443 PL:1062 EL:0
解析原子数据帧体:
扫频频谱观测数据:DT:12 DL:1057
频段序号:1  信道总数:1441
起始频率:137.0000MHz  结束频率:149.7750MHz  起始频率序号: 0
步长:25.0000kHz  帧信道数量:512
```

**注意**: 用户的频率范围是 137-149.775MHz（不是 137-173MHz），可能是不同测试。

---

## 字段对应关系（待破解）

| 标准格式字段 | 来源/计算方式 |
|------------|-------------|
| LEADER | 固定值 0xEEEE1DE6 |
| VER | 固定值 1 |
| STC | 时间戳（从 RMCP 帧头获取？） |
| TS | 帧时间戳 |
| PL | payload 长度 |
| EL | 固定值 0 |
| DT | 数据类型标识（待确认） |
| DL | 数据长度 |
| 频段序号 | 待确认 |
| 信道总数 | 从 startfreq/stopfreq/step 计算 |
| 起始频率 | 请求参数 |
| 结束频率 | 请求参数 |
| 步长 | 请求参数 |
| 帧信道数量 | 从 payload 大小计算（每2字节一个电平） |

---

**创建时间**: 2026-04-12 17:50
