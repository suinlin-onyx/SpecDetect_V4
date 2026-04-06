# 真实 Atom 联调测试计划

> 创建日期：2026-04-06
> 更新日期：2026-04-06
> 架构方案：方案A - 双 Proxy 并行模式

---

## 0. 文档策略

### 0.1 临时工作目录

`docs/REAL_ATOM_INTEGRATION/` 为**临时工作目录**，仅联调期间使用。

### 0.2 最终合并原则

联调完成后：
- **重要发现** → 合并到现有相关文档（如 `15_Atom_Device_架构分析.md`）
- **配置变更** → 更新 `CONFIG.md` 或 `settings.py`
- **临时目录** → 删除

---

## 1. 架构设计（方案A）

### 1.1 核心原则

1. **不影响原逻辑**：原有 8080→Mock Atom 链路完整保留
2. **并行比对**：新增 8081→Real Atom 链路，双通道同时存在
3. **零侵入**：不修改原有代码逻辑，只做扩展

### 0.2 架构图

```
                         ┌─────────────────────────────┐
                         │        客户端请求           │
                         └──────────────┬──────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                      │
                    ▼                                      ▼
            ┌───────────────┐                      ┌───────────────┐
            │  Proxy-A:8080 │                      │  Proxy-B:8081 │
            │   (原有链路)    │                      │   (新增链路)    │
            └───────┬───────┘                      └───────┬───────┘
                    │                                      │
                    ▼                                      ▼
            ┌───────────────┐                      ┌───────────────┐
            │  Mock Atom    │                      │  Real Atom    │
            │  127.0.0.1:9090│                    │  x.x.x.x:port │
            └───────────────┘                      └───────────────┘
```

### 0.3 端口分配

| 实例 | 端口 | 用途 | 状态 |
|------|------|------|------|
| Proxy-A | 8080 | 原有链路 → Mock Atom | ✅ 已有 |
| Proxy-B | 8081 | 新增链路 → Real Atom | ⬜ 待创建 |
| Atom | 9090 | Mock Atom 服务 | ✅ 已有 |
| Device | 9000 | Mock Device 服务 | ✅ 已有 |

### 0.4 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `run_all.py` | 修改 | 支持同时启动 Proxy-A 和 Proxy-B |
| `config/settings_proxy_b.py` | 新增 | Proxy-B 的独立配置 |
| `dual_request.py` | 新增 | 双通道同时请求工具 |
| `docs/REAL_ATOM_INTEGRATION/` | 扩展 | 补充方案A相关内容 |

---

## 1. 测试环境

### 1.1 组件版本

| 组件 | 版本 | 说明 |
|------|------|------|
| RMCPTP Protocol | v2.0 | 无线电协议版本 |
| Proxy | - | SOAP协议解析与路由 |
| Atom | ? | 真实Atom固件版本 |
| Device | ? | 真实设备型号 |

### 1.2 网络配置

| 连接 | 当前配置 | 目标配置 |
|------|----------|----------|
| Proxy → Atom | 127.0.0.1:9090 | x.x.x.x:port |

---

## 2. 测试用例

### TC-01: TCP 连接测试

| 项目 | 内容 |
|------|------|
| **目的** | 验证 Proxy 到 Real Atom 的 TCP 连通性 |
| **前置条件** | Real Atom 服务已启动 |
| **步骤** | 1. 配置 Real Atom 地址<br>2. 启动 Proxy<br>3. 检查连接日志 |
| **预期结果** | TCP 连接成功建立，无连接拒绝或超时 |
| **优先级** | P0 |

### TC-02: SGLFREQ 单点频率测量

| 项目 | 内容 |
|------|------|
| **目的** | 验证单点频率测量请求/响应正确 |
| **前置条件** | TC-01 通过 |
| **步骤** | 1. 发送 SGLFREQ 请求<br>2. 解析响应帧<br>3. 验证数据格式 |
| **预期结果** | 响应包含 frequency, level 等字段，格式符合协议 |
| **优先级** | P0 |

### TC-03: IFANALYSIS 中频分析

| 项目 | 内容 |
|------|------|
| **目的** | 验证中频分析功能 |
| **前置条件** | TC-01 通过 |
| **步骤** | 1. 发送 IFANALYSIS 请求<br>2. 解析响应帧 |
| **预期结果** | 响应包含 freq, level 字段 |
| **优先级** | P1 |

### TC-04: FSCAN 频谱扫描

| 项目 | 内容 |
|------|------|
| **目的** | 验证频谱扫描功能（动态数据格式） |
| **前置条件** | TC-01 通过 |
| **步骤** | 1. 发送 FSCAN 请求<br>2. 解析响应帧<br>3. 验证频谱数据数组 |
| **预期结果** | 响应包含频谱数据数组，长度符合 nArrays |
| **优先级** | P1 |

### TC-05: DF 测向功能

| 项目 | 内容 |
|------|------|
| **目的** | 验证测向功能 |
| **前置条件** | TC-01 通过 |
| **步骤** | 1. 发送 DF 请求<br>2. 解析响应帧 |
| **预期结果** | 响应包含 Azimuth, Elevation, Quality 等字段 |
| **优先级** | P2 |

### TC-06: IFDF 中频测向

| 项目 | 内容 |
|------|------|
| **目的** | 验证中频测向功能 |
| **前置条件** | TC-01 通过 |
| **步骤** | 1. 发送 IFDF 请求<br>2. 解析响应帧 |
| **预期结果** | 响应结构同 DF |
| **优先级** | P2 |

---

## 3. 协议验证清单

### 3.1 帧头结构（18字节）

| 字段 | 长度 | 格式 | 验证 |
|------|------|------|------|
| dwLength | 4 | !I | □ |
| tmStamp | 8 | !Q | □ |
| nVersion | 2 | !H | □ |
| nDataType | 1 | B | □ |
| nFlags | 1 | B | □ |
| nCheckSum | 2 | !H | □ |

### 3.2 业务数据头（11字节）

| 字段 | 长度 | 格式 | 验证 |
|------|------|------|------|
| nBdType | 1 | B | □ |
| nFlags | 2 | H | □ |
| nArrays | 4 | I | □ |
| nOffset | 4 | I | □ |

### 3.3 响应数据体验证

| 类型 | 结构 | 验证 |
|------|------|------|
| SGLFREQ | freq(8) + itu_value(2) | □ |
| IFANALYSIS | freq(8) + level(2) | □ |
| DF | level(2) + df_level(2) + quality(4) + azimuth(4) + elevation(4) + compass(4) | □ |
| IFDF | 同DF结构 | □ |
| FSCAN | nBdType(1) + nArrays(4) + [level + 频谱数据] | □ |

---

## 4. 测试执行

### 4.1 命令

```bash
# 启动所有服务
python run_all.py

# 执行完整测试套件
python run_test_suite.py

# 执行特定测试
python run_test_suite.py --test sglfreq
python run_test_suite.py --test real_atom
```

### 4.2 日志级别

| 级别 | 说明 |
|------|------|
| DEBUG | 详细帧数据日志 |
| INFO | 基本流程日志 |
| WARNING | 异常警告 |
| ERROR | 错误信息 |

---

---

## 7. 开发流程（方案A详细步骤）

### 阶段1: 双Proxy基础设施搭建

| 步骤 | 内容 | 产出物 | 状态 |
|------|------|--------|------|
| 1.1 | 分析现有 `run_all.py` 启动逻辑 | 了解服务启动顺序 | ⬜ |
| 1.2 | 创建 `config/settings_proxy_b.py` | Proxy-B 独立配置 | ⬜ |
| 1.3 | 创建 Proxy-B 启动脚本 | 支持只启动 Proxy-B | ⬜ |
| 1.4 | 修改 `run_all.py` 支持双Proxy | `--dual` 参数 | ⬜ |
| 1.5 | 验证 Proxy-A (8080) 不受影响 | 原有链路正常 | ⬜ |
| 1.6 | 验证 Proxy-B (8081) 独立运行 | 新链路正常 | ⬜ |

### 阶段2: 双通道对比工具

| 步骤 | 内容 | 产出物 | 状态 |
|------|------|--------|------|
| 2.1 | 创建 `dual_request.py` | 同时发送双请求工具 | ⬜ |
| 2.2 | 创建 `diff_output.py` | 格式化差异输出 | ⬜ |
| 2.3 | 测试 SGLFREQ 双通道对比 | TC-07 | ⬜ |
| 2.4 | 测试其他业务双通道对比 | TC-08~TC-10 | ⬜ |

### 阶段3: 集成测试与差异记录

| 步骤 | 内容 | 产出物 | 状态 |
|------|------|--------|------|
| 3.1 | 执行 TC-01~TC-06（双通道）| 测试报告 | ⬜ |
| 3.2 | 记录差异到 ISSUES.md | 问题列表 | ⬜ |
| 3.3 | 更新 DIFF_ANALYSIS.md | 完整差异文档 | ⬜ |
| 3.4 | 更新 PROGRESS.md | 最终进度 | ⬜ |

---

## 8. 执行命令

### 8.1 启动命令

```bash
# 启动所有服务（原有模式）
python run_all.py

# 启动所有服务（双Proxy模式）
python run_all.py --dual

# 只启动 Proxy-B
python run_proxy_b.py
```

### 8.2 测试命令

```bash
# 双通道同时请求 SGLFREQ
python dual_request.py --service sglfreq --freq 100000000

# 双通道同时请求 IFANALYSIS
python dual_request.py --service ifanalysis --freq 100000000

# 对比输出（格式化差异）
python diff_output.py --result_a <mock_result> --result_b <real_result>
```

### 8.3 验证命令

```bash
# 验证 Proxy-A (8080) - Mock Atom
curl -X POST http://localhost:8080/services -H "Content-Type: text/xml" -d '...'

# 验证 Proxy-B (8081) - Real Atom
curl -X POST http://localhost:8081/services -H "Content-Type: text/xml" -d '...'
```

---

**计划制定**: 2026-04-06
**架构方案**: 方案A - 双Proxy并行
**下一步**: 阶段1 步骤1.1 - 分析现有 run_all.py 启动逻辑
