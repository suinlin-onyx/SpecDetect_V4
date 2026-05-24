# TASKS 2026-04-24 PScan粘包问题 [已解决]

**解决日期**: 2026-04-24
**方案**: PScan 专用接收路径 `receive_pscan_raw()`，先提取 RMCP 控制帧，后续 buffer 视为 raw DSCAN 流

---

## 问题描述

PScan请求时，DSCAN数据帧(8031字节)解析失败。

### 错误日志
```
dw_length=2701132048 > 1500，可能为粘包或异常帧，进行帧头同步搜索...
帧头同步：未找到有效帧头
帧头同步未找到，跳过1字节继续
```

---

## 根因分析

**跳过操作破坏buffer**：
1. 响应帧(51字节)解析后，buffer剩余约8000字节
2. 代码假设粘包，开始逐字节跳过
3. 跳过操作把真正的RMCP帧头也跳过了
4. buffer变成纯频谱数据(`00 01 c6...`)，没有`00 07` (nVersion=7)

---

## 已尝试方案

| 方案 | 描述 | 结果 |
|------|------|------|
| 帧头同步机制 | dw_length>1500时搜索nVersion=7 | 失败，跳过破坏buffer |
| 扩大搜索范围 | 2000字节，加强验证 | 失败 |
| FSCAN解析DSCAN | 用FSCAN逻辑解析 | 失败 |
| 简化处理 | 信任parse_rmcp_frame验证 | 影响FSCAN，已回滚 |

---

## 关键发现

1. **buffer hexdump**: `100100a10f000000000000ea...` 是纯频谱，无帧头
2. **FSCAN正常**: 1053字节在范围内
3. **DSCAN异常**: 8031字节触发粘包判断

---

## 待解决问题

1. 粘包处理破坏buffer
2. DSCAN帧格式(8031字节)待确认
3. parse_dscan_payload的2000点限制

---

## 相关文件

- `src/atom/rmcp/client.py` - 帧头同步机制
- `src/atom/rmcp/frame.py` - 解析函数
- `docs/DSCAN_FRAME_FORMAT.md` - DSCAN帧格式

---

## 下一步

1. 抓包分析DSCAN原始帧格式
2. 参考rmcp_proxy验证逻辑
3. 考虑使用100ms间隔作为辅助判断
