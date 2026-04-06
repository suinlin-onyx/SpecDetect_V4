# 频谱探测系统测试规范

## 1. 测试范围

| 测试类型 | 覆盖范围 | 执行方式 |
|---------|---------|---------|
| 单元测试 | MonitorService、DirectionService 的解析逻辑 | pytest |
| 集成测试 | HTTP接口 → Atom Service → Mock Device 完整链路 | run_test_suite.py |
| 压力测试 | 快速连续请求、并发请求 | run_test_suite.py |
| 异常测试 | 设备未连接、请求超时、协议错误 | run_test_suite.py |
| 自动化测试 | 全链路自动化测试 | `python run_test_suite.py` |

---

## 2. 测试用例设计

### 2.1 按业务类型

| 业务类型 | 接口路径 | 说明 |
|---------|---------|------|
| SGLFREQ | POST /monitor/sglfreq | 单频测量 |
| FSCAN | POST /monitor/fscan | 频段扫描 |
| IFANALYSIS | POST /monitor/ifanalysis | 中频分析 |
| DF | POST /direction/df | 单频测向 |
| IFDF | POST /direction/ifdf | 中频测向 |
| WBFFT | POST /direction/wbfft | 宽带FFT |

### 2.2 按设备类型

| 设备类型 | 支持业务 | 测试优先级 |
|---------|---------|-----------|
| MS950 | SGLFREQ, IFANALYSIS, FSCAN | P0 |
| MS845 | SGLFREQ, IFANALYSIS, FSCAN | P1 |
| MS970 | SGLFREQ, IFANALYSIS, FSCAN, DF, IFDF | P1 |
| MD1000 | 所有业务类型 | P1 |

### 2.3 边界测试

- **频率范围边界**：设备支持的最小/最大频率
- **不支持的业务**：设备不具备的业务类型应返回 ERR_3004
- **设备未连接**：未连接时发送请求应返回 ERR_DEVICE_OFFLINE

---

## 3. 测试数据

### 3.1 模拟数据生成
使用 `data_generator.py` 生成模拟数据，支持以下场景：

| 场景 | 说明 |
|-----|------|
| normal | 常规监测，噪声底-100dBm |
| interference | 干扰场景，多个信号叠加 |
| abnormal | 异常场景，噪声提高 |
| boundary | 边界场景，频率/幅度在边界值 |
| stress | 压力测试，100个信号 |

### 3.2 默认测试参数

```json
{
  "frequency": 100_000_000,
  "bandwidth": 120_000,
  "start_freq": 100_000_000,
  "end_freq": 200_000_000,
  "step": 1_000_000,
  "span": 1_000_000,
  "ifbw": 100_000
}
```

---

## 4. 验证点

### 4.1 数据格式正确性

| 业务类型 | 验证项 | 期望值 |
|---------|-------|-------|
| SGLFREQ | amplitude | -120 ~ -20 dBm |
| FSCAN | point_count | 与实际 levels 数量一致 |
| FSCAN | levels[i] | -120 ~ -20 dBm |
| IFANALYSIS | spectrum 数量 | 与 n_arrays 一致 |
| IFANALYSIS | center_level | -120 ~ -20 dBm |
| DF | azimuth | 0 ~ 360 度 |
| DF | quality | 0 ~ 1 |

### 4.2 协议帧验证（通过 Hook 日志）

- 帧头结构：18字节，包含校验和
- business_type：首字节应为对应的业务类型
- payload_length：应与实际数据长度一致

### 4.3 错误处理验证

| 场景 | 期望错误码 | 错误信息 |
|-----|-----------|---------|
| 设备未连接 | ERR_DEVICE_OFFLINE (3001) | 设备未连接 |
| 不支持的业务 | ERR_DEVICE_NOT_SUPPORTED (3004) | 设备不支持业务类型 |
| 频率超范围 | ERR_FREQ_OUT_OF_RANGE (4004) | 频率超出范围 |

### 4.4 稳定性验证

- 快速连续10次请求后服务不崩溃
- 快速连续20次请求后服务不崩溃
- 快速连续50次请求后服务不崩溃

---

## 5. 测试流程

### 5.1 测试前准备

```bash
# run_all.py 会自动清理残留进程，直接启动即可
python run_all.py
```

> **自动清理机制**：run_all.py 启动前会自动检测并终止占用端口 9000/9090/8080/19000 的残留进程。
python main_mock.py --device MS950 &
python main_atom.py &
```

### 5.2 单元测试流程

```bash
# 直接测试解析函数（Python脚本）
python -c "
from app.atom_service.services.monitor import MonitorService
from app.atom_service.services.direction import DirectionService
import struct

# 构造测试payload并验证解析结果
"
```

### 5.3 集成测试流程

```bash
# 1. 连接设备
curl -X POST http://127.0.0.1:9090/device/connect

# 2. 发送业务请求
curl -X POST http://127.0.0.1:9090/monitor/sglfreq \
  -H "Content-Type: application/json" \
  -d '{"frequency":100000000}'

# 3. 检查健康状态
curl http://127.0.0.1:9090/health
```

### 5.4 压力测试流程

```bash
# 快速连续请求（10次）
for i in {1..10}; do
  curl -s -X POST http://127.0.0.1:9090/monitor/sglfreq \
    -H "Content-Type: application/json" \
    -d '{"frequency":100000000}' &
done
wait

# 混合并发请求
for i in {1..20}; do
  curl -s -X POST http://127.0.0.1:9090/monitor/sglfreq ... &
  curl -s -X POST http://127.0.0.1:9090/monitor/fscan ... &
  curl -s -X POST http://127.0.0.1:9090/monitor/ifanalysis ... &
done
wait
```

### 5.5 测试后验证

```bash
# 确认服务仍在运行
curl http://127.0.0.1:9090/health
netstat -ano | grep -E "9000.*LISTENING|9090.*LISTENING"
```

### 5.6 自动化测试流程（推荐）

使用自动化测试脚本 `run_test_suite.py` 执行完整测试：

```bash
cd D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC
python run_test_suite.py
```

**自动化测试脚本自动执行以下测试项：**

| 阶段 | 测试项 | 说明 |
|-----|-------|------|
| 0 | 服务状态检查 | 检查 Atom/Mock/Proxy 服务健康状态 |
| 1 | SGLFREQ 集成测试 | 设备连接、单频测量、amplitude范围验证 |
| 2 | FSCAN 集成测试 | 频段扫描、point_count与levels一致性、levels范围验证 |
| 3 | IFANALYSIS 集成测试 | 中频分析、spectrum非空验证、center_level范围验证 |
| 4 | DF 错误处理测试 | MS950不支持DF业务，验证返回错误 |
| 5 | 快速连续请求测试 | 10次SGLFREQ请求，验证无崩溃 |
| 6 | 混合并发请求测试 | 5轮×4种业务，验证成功率 |
| 7 | 错误处理测试 | 基础错误处理验证 |
| 8 | pytest 单元测试 | 运行 tests/ 目录下所有单元测试 |

**自动化测试输出示例：**

```
============================================================
频谱探测系统 - 自动化测试套件
============================================================
测试时间: 2026-04-05 23:21:08
测试环境: Atom=http://127.0.0.1:9090, Mock=http://127.0.0.1:9000, Proxy=http://127.0.0.1:8080

[0] 服务状态检查...
  [PASS] Atom Service
  [FAIL] Mock Device - 连接超时
  [FAIL] Proxy Service - 连接失败

[1] 集成测试: SGLFREQ 单频测量...
  [PASS] 设备连接
  [PASS] SGLFREQ请求
  [PASS] amplitude范围(-120~-20)

...

============================================================
测试汇总
============================================================

总计: 通过=18, 失败=2
```

**预期测试结果：**
- 集成测试: 全部通过
- 压力测试: 全部通过
- 单元测试: 33 passed, 1 skipped

---

## 6. 测试执行检查清单

### 6.1 前置检查
- [ ] 端口 9000/9090/8080 无残留进程
- [ ] 缓存已清理

### 6.2 单元测试
- [ ] SGLFREQ 解析正确（amplitude 范围 -120~-20）
- [ ] FSCAN 解析正确（point_count 与 levels 一致）
- [ ] IFANALYSIS 解析正确（spectrum 数量正确）
- [ ] DF 解析正确（azimuth 范围 0~360）

### 6.3 集成测试
- [ ] SGLFREQ 接口返回 success:true
- [ ] FSCAN 接口返回 success:true
- [ ] IFANALYSIS 接口返回 success:true
- [ ] DF 接口（MS950）返回 ERR_3004

### 6.4 压力测试
- [ ] 10次快速请求无崩溃
- [ ] 20次快速请求无崩溃
- [ ] 50次快速请求无崩溃

### 6.5 错误处理
- [ ] 设备未连接时正确返回 ERR_DEVICE_OFFLINE
- [ ] 不支持的业务正确返回 ERR_3004

### 6.6 自动化测试（run_test_suite.py）
- [ ] 服务状态检查通过
- [ ] SGLFREQ/FSCAN/IFANALYSIS 集成测试通过
- [ ] 压力测试通过（10次连续请求无崩溃）
- [ ] pytest 单元测试全部通过（33 passed, 1 skipped）

---

## 7. 测试结果记录

每次测试应记录：

| 项目 | 内容 |
|-----|------|
| 测试日期 | YYYY-MM-DD |
| 测试人员 | 姓名 |
| 测试环境 | 设备类型、场景配置 |
| 测试结果 | 通过/失败/阻塞 |
| 发现问题 | 描述及严重程度 |
| 回归验证 | 是否影响已有功能 |

---

## 8. 已知回归风险点

以下为历史修复记录，测试时应重点关注：

| 风险点 | 修复日期 | 修复版本 |
|-------|---------|---------|
| business_type 字节跳过导致解析偏移错误 | 2026-04-05 | v1 |
| nArrays 偏移量错误（FSCAN/IFANALYSIS） | 2026-04-05 | v1 |
| 快速并发导致连接状态混乱 | 2026-04-05 | v1 |
| 端口残留导致服务启动失败（run_all.py 自动清理） | 2026-04-05 | v1 |
| test_parse_frame_checksum_error 帧偏移错误（校验和位于索引16-17） | 2026-04-05 | v1.1 |
| test_frame_builder_generates_valid_frame dwLength计算错误（应包含business_type字节） | 2026-04-05 | v1.1 |
| test_build_response_frame 同上 | 2026-04-05 | v1.1 |
| **run_async函数未清理待处理任务，导致第3次请求卡住** | 2026-04-05 | v1.2 |
| **run_async修复：关闭事件循环前取消所有待处理任务** | 2026-04-05 | v1.2 |
| **run_all.py使用管道捕获输出，缓冲区满导致服务阻塞** | 2026-04-06 | v1.3 |
| **run_all.py修复：输出重定向到日志文件，不再使用管道** | 2026-04-06 | v1.3 |

---

## 9. 附录

### 9.1 常用 curl 命令模板

```bash
# 连接设备
curl -X POST http://127.0.0.1:9090/device/connect

# 单频测量
curl -X POST http://127.0.0.1:9090/monitor/sglfreq \
  -H "Content-Type: application/json" \
  -d '{"frequency":100000000}'

# 频段扫描
curl -X POST http://127.0.0.1:9090/monitor/fscan \
  -H "Content-Type: application/json" \
  -d '{"start_freq":100000000,"end_freq":200000000}'

# 中频分析
curl -X POST http://127.0.0.1:9090/monitor/ifanalysis \
  -H "Content-Type: application/json" \
  -d '{"frequency":100000000,"span":1000000}'

# 单频测向
curl -X POST http://127.0.0.1:9090/direction/df \
  -H "Content-Type: application/json" \
  -d '{"frequency":100000000}'

# 设备状态
curl http://127.0.0.1:9090/health
```

### 9.2 端口说明

| 端口 | 服务 | 说明 |
|-----|------|-----|
| 9000 | Mock Device | 虚拟设备服务器 |
| 9090 | Atom Service | 原子服务（HTTP API） |
| 8080 | Proxy Service | 代理服务（聚合页面） |

### 9.3 自动化测试脚本

#### 快速开始

```bash
cd D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC
python run_test_suite.py
```

#### 脚本功能

`run_test_suite.py` 是频谱探测系统的自动化测试套件，提供：
- **一站式测试执行**：无需手动执行多个测试步骤
- **服务健康检查**：自动验证 Atom/Mock/Proxy 服务状态
- **完整测试覆盖**：集成测试、压力测试、单元测试全覆盖
- **详细测试报告**：清晰的 PASS/FAIL 输出和汇总统计

#### 测试阶段说明

| 阶段 | 测试内容 |
|-----|---------|
| 0 | 服务状态检查 - 验证 Atom(9090)、Mock(9000)、Proxy(8080) 服务 |
| 1 | SGLFREQ - 单频测量集成测试 |
| 2 | FSCAN - 频段扫描集成测试 |
| 3 | IFANALYSIS - 中频分析集成测试 |
| 4 | DF - 单频测向错误处理测试 |
| 5 | 快速连续请求 - 10次SGLFREQ压力测试 |
| 6 | 混合并发请求 - 5轮×4种业务压力测试 |
| 7 | 错误处理测试 |
| 8 | pytest单元测试 - 运行 tests/ 目录下所有测试 |

#### 单独运行 pytest 单元测试

```bash
# 运行所有单元测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_atom.py -v
python -m pytest tests/test_flow.py -v
python -m pytest tests/test_mock.py -v
python -m pytest tests/test_proxy.py -v

# 运行特定测试用例
python -m pytest tests/test_atom.py::TestRMCPTPParser::test_parse_valid_frame -v
```

#### 依赖服务

自动化测试需要以下服务运行：

| 端口 | 服务 | 启动命令 |
|-----|------|---------|
| 9090 | Atom Service | `python main_atom.py` |
| 9000 | Mock Device | `python main_mock.py` |
| 8080 | Proxy Service | `python main_proxy.py` |

或使用 `python run_all.py` 一键启动所有服务。

---

*文档版本：v1.4*
*最后更新：2026-04-06*
*更新内容：*
- *8. 已知回归风险点：新增 run_all.py 管道阻塞问题及修复记录*
- *run_all.py：输出重定向到 logs/service_*.log，不再使用管道*
- *修复后测试结果：集成测试全部通过，压力测试全部通过，单元测试 33 passed, 1 skipped*
