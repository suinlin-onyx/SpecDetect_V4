# V2 验证: SOAP stream 响应指向 streamsrc 18012

**日期**: 2026-04-15
**方法**: 发 SOAP B_FScan 请求给 Atom (127.0.0.1:8282)，解析响应里的 `<outputchannel>`

## 结果

```
SOAP 响应 outputchannel:
  host = 127.0.0.1
  port = 18012            ← 与 streamsrc 监听端口一致 ✓
  stc  = 1776247195 (0x69DF619B)
```

## 结论

1. **国标 stream 通道 = streamsrc 18012** 完全确认
2. SOAP 响应里的 `<srrc:stc>` 是 UINT32（例：1776247195）
3. Atom 在 SOAP 响应里明确按国标 `<outputchannel type='stream'>` 格式回传

## 待查

- STC 是否编码进 streamsrc 帧头？
  - 本次 STC `0x69DF619B` (LE `9b61df69`) 未直接出现在旧 session 的 offset 4-11 `0100a851df69ea07` 里
  - 需要新捕获：**同一次 SOAP 调用 + streamsrc 抓包**配对，对比 STC 是否存在帧内
  - 推测：STC 可能在 offset 4-11 的某 4 字节子段，或在 offset 12-15 (末字节递增的那个)

## 修正先前文档

`DATA_FLOW_END_TO_END.md` 段 3 "SOAP 数据面实际传输通道" 从"未验证"改为**"已验证：独立 TCP 流，端口由 SOAP 响应声明"**。
