# SpecDetect 实验代码

本目录包含 streamsrc 协议分析的核心实现代码。

## 核心实现

| 文件 | 说明 |
|------|------|
| `atom_streamsrc_listener.py` | **主程序** - Atom streamsrc 监听器，接收 18012 端口数据并解析 FSCAN-529/FSCAN-434 分片帧 |
| `test_fscan529.py` | FSCAN-529 字节级结构分析工具 |
| `restart_services.py` | 服务重启工具 (AtomSvcV3 + rmcp_proxy) |
| `soap_to_rmcp_direct.py` | SOAP → RMCP 直接转换 (实验性) |

## streamsrc 协议解析

### 帧结构 (65 字节)

```
Offset 0-3:   0xEEEEEEEE (帧同步标记)
Offset 4-11:  FILETIME 时间戳
Offset 12-15: 帧序号
Offset 19:    FSCAN 类型 (0x26=FSCAN-529, 0x68=FSCAN-434)
Offset 28+:   电平数据 (18 int16)
```

### 元数据 (前 5 个 int16)

| 值 | 含义 |
|----|------|
| 256 | FFT 窗口参数 |
| 1441 | 总信道数 |
| 0, 0 | 保留 |
| -32768 | 无效值标记 |

### 重组算法

```python
# 分片缓冲拼接
buffer_529.extend(result['levels'])
while len(buffer_529) >= 529:
    spectrum = buffer_529[:529]
    buffer_529 = buffer_529[529:]
    output_spectrum('FSCAN-529', spectrum, elapsed)
```

## 使用方法

### 启动 streamsrc 监听

```bash
cd experimental
python atom_streamsrc_listener.py
```

### 分析 FSCAN-529 结构

```bash
python test_fscan529.py
```

### 重启服务

```bash
python restart_services.py
```

## 关键文档

| 文档 | 说明 |
|------|------|
| `TASKS_20260416_fscan529_byte_analysis.md` | FSCAN-529 字节级结构解析 (65B帧结构、元数据穿插、重组算法) |
| `TASKS_20260415_atom_filter_analysis.md` | Atom 滤波与变换分析 (streamsrc vs rmcp 数据对比) |
| `ATOM_STREAM_SRC_ANALYSIS.md` | Atom streamsrc 协议分析 |
| `PROTOCOL_RULES_SUMMARY.md` | 协议规则汇总 |

## 目录结构

```
experimental/
├── atom_streamsrc_listener.py  # 核心实现
├── test_fscan529.py            # 分析工具
├── restart_services.py         # 工具
├── README.md                   # 本文档
├── TASKS_*.md                  # 任务文档
├── archive/                    # 历史文档 (已归档)
├── scratch/                    # 中间脚本 (已归档)
├── data/                       # 测试数据
└── logs/                       # 运行日志
```

## 关键发现

1. **streamsrc 分片帧**: 每帧 65 字节，包含 18 int16 电平数据
2. **元数据穿插**: `[256,1441,0,0,-32768]` 均匀分布在重组 buffer 中，间隔 = 18
3. **完整帧判断**: 依靠 100ms 时间间隔区分频谱边界
4. **streamsrc vs rmcp**: streamsrc 是 rmcp 的实时压缩监测版本 (~3.8:1 压缩)
