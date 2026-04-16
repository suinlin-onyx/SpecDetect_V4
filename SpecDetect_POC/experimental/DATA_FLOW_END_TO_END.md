# Device → Atom → SOAP → Client 端到端数据流分析

**日期**: 2026-04-15
**依据**: 抓包 (raw_fscan_*.log, streamsrc_raw_*.log) + GWJ004/GWJ006/RMCPTP 文档
**状态**: 段 1、段 2B 已验证；段 2A、段 3 主要靠文档

---

## 一、路径全图

```
┌──────────┐   RMCPTP        ┌──────────┐   ┌──► SOAP/HTTP        ┌────────┐
│ Device   │ ──TCP──────────►│  Atom    │───┤   (GWJ004 接口)     │ Client │
│ (接收机) │  (二进制帧)     │ (Svc V3) │   │                     │        │
│          │                 │          │   └──► streamsrc/TCP    │        │
└──────────┘                 └──────────┘       (18012, 私有流)   └────────┘
```

Atom 同时承担 **协议转换器**（RMCPTP→SOAP）和 **流转发器**（RMCPTP→streamsrc）。

---

## 二、段 1: Device → Atom

**协议**: RX-RMCPTP v2.0（设备私有二进制协议, TCP 长连接，设备主动推送）

**帧结构**:
```
[RMCPTP 帧头]
  nDataType   UINT8    = 0 (业务数据)
  nBdType     UINT8    = 15 (FSCAN) / 其他
  nFlags      INT16
  nArrays     UINT32   数组个数 (频段数)
  nOffset     UINT32   当前分片在整周期中的偏移 ★切片关键
[业务数据]
  每频段: startfreq, endfreq, step, nPoints, levels[INT16]
  电平 = 存储值 / 100  (单位 dBm)
```

**切分规则** (已验证, 来自 `raw_fscan_20260414_215655.log`):
- 1441 信道 FSCAN 切为 3 帧: 512 + 512 + 417
- 每帧间隔 ~100ms
- 靠 `nOffset` 重组 (0 → 512 → 1024)
- 帧大小: 1053 / 1053 / 863 bytes

---

## 三、段 2: Atom 内部处理（核心黑盒）

Atom 接收 RMCPTP 后 **分叉输出两条路**。

### 3A. Atom → SOAP (高精度)

- 解析 RMCPTP → 还原 dBm 浮点
- 按 GWJ004 帧格式封装
- 电平: `dBm × 10` → INT16 (0.1 dBμV)，SOAP 接口一般返回 dBm 浮点
- **保留 848 级动态范围**

### 3B. Atom → streamsrc (18012, 有损压缩) — 已验证

| 变换 | 现象 | 含义 |
|---|---|---|
| 量化 | 848 级 → 16 级 | ~5-bit 离散化 |
| 底噪压平 | -62.8 dBm 占 33% | 门限以下统一钉住 |
| 动态范围截断 | [-125.7, -13.4] → [-96.6, -28.7] | 上下边界压缩 |
| 切片重组 | 18 电平/帧 × ~30 帧 → 529 或 434 电平 | Atom 重新切片 |
| 无效值 | `0xEFFF` → `-32768` | 标识变更 |

**streamsrc 帧格式** (65 字节/帧):
```
offset 0-3   LEADER  0xEEEEEEEE
offset 4-11  FILETIME 时间戳
offset 12-17 保留 / 帧编号
offset 18    帧计数器
offset 19    FSCAN 类型 (0x26=FSCAN-529, 0x68=FSCAN-434)
offset 20-27 未知
offset 28+   18 个 INT16 电平 (原始值范围 [-32768, 24933])
```

### 3C. Atom 算法（未验证，国标未规定）
- 量化阈值、底噪门限、抽取率 = 厂商私有实现
- GWJ004/GWJ006 仅定义容器格式 (见 `ATOM_DOC_GAP.md`)
- 可能配置入口: `squelchthreshold`、`detector`、`samples`

---

## 四、段 3: Atom → SOAP → Client

**协议**: SOAP over HTTP (GWJ002/GWJ004)

- **控制面**: SOAP 请求/响应 (`<facility>`, `<startfreq>`, `<threshold>` 等 XML)
- **数据面**: SOAP 返回引用 + 二进制数据流 (GWJ004 §5.17)

**数据帧结构** (GWJ004):
```
LEADER(4) | VER(2) | STC(4) | TS(9) | PL(4) | EL(1)
  └─ DT(1) | DL(4) | DATA(N)
            └─ spectrum: 频率总数量 + 起始频率 + 步进
                       + 频率序号 + 频率数量 + 电平[INT16×m]
```

**切分规则**:
- 每帧 m 点 (典型 512)
- `频率序号` 指明在完整频谱中的偏移
- `STC` 标识通道 (多路并发时区分)

**传输**:
- 控制指令走 HTTP/XML
- 数据帧可能走独立 TCP，或嵌入 HTTP 响应
- `LEADER 0xEEEEEEEE` 是流同步锚点

---

## 五、三段对照

| 维度 | Device→Atom (RMCPTP) | Atom→streamsrc | Atom→SOAP (GWJ004) |
|---|---|---|---|
| 协议 | RX-RMCPTP v2.0 | 私有二进制 | SOAP/HTTP + GWJ004 帧流 |
| 帧头 | nDataType+nBdType+… | 0xEEEEEEEE+FILETIME | 0xEEEEEEEE+STC+TS |
| 切分字段 | `nOffset` | offset 19 + 时间间隔 | `频率序号`+`频率数量` |
| 每帧载荷 | 1 频段 (512/417 点) | 18 点 × 65B | m 点 (典型 512) |
| 电平精度 | dBm × 100 (INT16) | 16 级量化 | 0.1 dBμV (INT16) |
| 动态范围 | ~848 级 | 压缩至 16 级 | 完整 848 级 |
| 无效值 | 无统一 | `-32768` | `0xEFFF` |
| 单位 | dBm | dBm (归一化) | dBμV / dBm 可选 |

---

## 六、已验证 vs 未验证

### 已验证 (抓包 + 代码)
- RMCPTP 分片: 1441 = 512+512+417，靠 `nOffset`
- streamsrc 帧格式 (offset 0-19)、18 电平/帧、65 字节/帧
- streamsrc 量化到 16 级，底噪 -62.8 dBm 占 33%
- 时间对齐: streamsrc 与 rmcp Δ=13~49ms (同源)

### 未验证 (黑盒)
- Atom 量化算法 (μ-law? 等间隔? 查找表?)
- 529/434 的频段选取规则 (任务配置 or 动态)
- SOAP 数据面实际传输通道 (HTTP Body vs 独立 TCP)
- STC 在 streamsrc 中是否存在

### 后续工作
- Atom 二进制逆向
- SOAP 客户端真实调用抓包 (段 3 目前仅文档)
- 配置项 `squelchthreshold`/`detector` 调整验证

---

## 七、参考

- `PROTOCOL_RULES_SUMMARY.md` — 协议规则汇总
- `ATOM_STREAM_SRC_ANALYSIS.md` — streamsrc 协议分析
- `ATOM_DOC_GAP.md` — 国标文档未覆盖的 Atom 行为
- `GWJ006_FRAME_MAPPING.md` — GWJ006 帧字段 ↔ device 数据映射
- `ANALYSIS_DATA_COMPARISON.md` — rmcp vs streamsrc 数据对比
