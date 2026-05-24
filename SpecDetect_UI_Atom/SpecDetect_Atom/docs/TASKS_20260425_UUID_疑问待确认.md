# TASKS 2026-04-25 UUID 帧疑问 [待确认]

**创建日期**: 2026-04-25

---

## 疑问：UUID 帧是否应该发送给 test tool？

### 背景

根据 commit `eb3c` 的日志：
```
fix: SglFreq streamsrc帧与真实设备完全对齐
- build_uuid_frame: 客户端连接后首帧注册，indicator=0x0129
```

### 添加原因：
- 分析真实设备的二进制抓包 (`stream_B_SglFreqMeas_18013_150706_378968.bin`)
- 发现设备连接后首先发送 UUID 帧
- 为完全对齐真实设备行为，所以添加了 `build_uuid_frame()`

### 结论：
- UUID 帧是所有模式通用的，不是 FSCAN/MSCAN/PScan 特有的
- 它是真实设备的连接握手行为
- 当前的 test tool 不兼容 UUID 帧格式，导致把它当数据解析（PL:41 错误帧）

---

## 待确认问题

| # | 问题 | 答案 |
|---|------|------|
| 1 | test tool 是否需要支持 UUID 帧解析？ | 待确认 |
| 2 | 如果 test tool 不支持，是否应该跳过 UUID 帧发送？ | 待确认 |
| 3 | 真实设备连接时也会发送 UUID 帧，届时 test tool 是否需要正确处理？ | 待确认 |

---

## 当前状态

- `client.sendall(uuid_frame)` 在 `server.py:167` 已被注释
- UUID 帧发送逻辑保留在代码中，作为配置选项待定

---

## 相关文件

- `src/atom/stream/frame.py` - `build_uuid_frame()`
- `src/atom/stream/server.py:163-170` - UUID 帧发送逻辑
