# RMCP ↔ streamsrc 架构解耦设计 [已归档]

**创建日期**: 2026-04-22
**归档日期**: 2026-04-25
**状态**: 已归档 — 本文档为初始设计方案，实际实现采用了不同的目录结构

---

## 归档说明

本文档描述的 `protocol/` 目录结构**从未实现**。实际实现采用了以下结构：

```
实际结构:
atom/rmcp/        # RMCP 协议 (client.py, frame.py, logger.py)
atom/stream/      # streamsrc 推送 (server.py, frame.py)
atom/soap/        # SOAP 协议 (server.py, parser.py)
atom/service.py   # 协调层
atom/session.py   # 会话数据
```

设计原则（模块独立、职责单一、数据驱动）已体现在实际实现中。

---

## 原始设计文档

### 1. 设计原则

- **模块独立**: 各协议解析/帧生成模块独立，不相互依赖
- **职责单一**: 每个模块只负责一件事
- **数据驱动**: 实现依托于真实抓包数据，不自由发挥
- **接口稳定**: 推送流程稳定，帧生成可随时修改

### 2. 杜绝的问题

- 调整 MSCAN 功能时影响 FSCAN
- 不同请求结构体解析相互干扰
- 帧生成与推送流程耦合

### 3. 验证标准 (已达成)

1. 改 MSCAN 帧格式不影响 FSCAN ✅
2. 改 FSCAN payload 解析不影响 MSCAN ✅
3. streamsrc server 中无帧生成代码 ✅
4. 每种帧类型有独立函数 ✅
