# GWJ SOAP stream 输出通道元素

**日期**: 2026-04-15
**来源**: GWJ001/GWJ002/GWJ003-2015 (docx)
**作用**: 明确 SOAP 如何声明 stream 数据通道，补充 `GWJ_STREAM_MODE_NOTES.md`

---

## 一、`<outputchannel>` 元素（GWJ003 所有业务通用）

### SOAP 响应模板

```xml
<outputchannel mode='source' type='stream'>
  <stream host='172.18.225.78' port='5000' stc='101'/>
</outputchannel>
```

或文件通道：

```xml
<outputchannel mode='sink' type='URL'>
  <URL host='IP' port='端口' URI='文件'/>
</outputchannel>
```

### 字段含义

| 字段 | 含义 |
|---|---|
| `mode` | source / sink / 指定方 |
| `type` | stream / URL |
| `host` | 数据流监听主机 IP |
| `port` | 数据流监听 TCP 端口 |
| `stc` | stream 标签，唯一标识通道（= RMCPTP/GWJ004 的 STC） |
| `URI` | URL 类型时的文件路径 |

---

## 二、业务覆盖范围（GWJ003）

所有下列业务的 SOAP 响应都用同一套 `<outputchannel>` 机制：

- 4.1 ITU 单频测量 (ITUMon)
- 4.2 宽带 FFT 频谱观测 (WBFFTMon)
- 4.3 扫频频谱观测 (FSCAN)
- 4.4 频率表扫描 (MSCAN)
- 4.5 中频 FFT 测向 (IFDF)
- 4.6 单频测向 (SFDF)
- 4.7 宽带 FFT 测向 (WBDF)
- 4.x 扫频测向、频率表扫描测向
- 信号截收类服务

---

## 三、异步传输模型（GWJ001 §7.2, GWJ003 §4.x）

```
Step 1  Client ──SOAP 请求──► Atom/Device
Step 2  Atom  ──SOAP 响应──► Client
        (响应体含 <outputchannel><stream host port stc>)
Step 3  Client ──TCP connect host:port──► Atom
        ◄── 持续接收数据流 (GWJ004 帧流 或 私有流)
Step 3'  或: Client 定期轮询 URL 获取文件（URL 通道）
```

---

## 四、STC 语义统一

| 层 | 名称 | 位置 | 作用 |
|---|---|---|---|
| SOAP | `stc` 属性 | `<stream stc='101'>` | 流标签 |
| GWJ004 数据帧头 | STC | 帧头 UINT32 | 唯一标识一路传输通路 |
| RMCPTP | STC | 业务头 | 同上 |

三层语义一致，作为**多路 stream 复用时的通道区分键**。

---

## 五、Atom streamsrc 与 SOAP 规定的对照

| SOAP 规定 | streamsrc (18012) 实测 | 吻合? |
|---|---|---|
| `<stream host port stc>` 作为响应 | 端口 18012（本地） | 端口对上 |
| stc 作为流标签 | streamsrc 帧内未见显式 STC 字段 | ✗ 私有省略 |
| type='stream' (纯 TCP) | TCP 长连接 | ✓ |
| URL 文件通道 | 未观察 | — |
| 帧格式 GWJ004 (LEADER+VER+STC+TS+PL+EL) | 0xEEEEEEEE + FILETIME + 私有 offset | 部分吻合 |

**结论**：Atom streamsrc 是 SOAP stream 通道的**私有简化实现**：
- 端口/TCP 流机制遵循国标
- 帧内字段（STC、电平精度、LEADER 后结构）被替换为 Atom 私有格式

---

## 六、参考

- `GWJ_STREAM_MODE_NOTES.md` — stream 传输模式补充
- `DATA_FLOW_END_TO_END.md` — 端到端数据流
- `ATOM_DOC_GAP.md` — 国标文档未覆盖的 Atom 行为
