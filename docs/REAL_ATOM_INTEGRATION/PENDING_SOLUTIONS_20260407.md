# Real Atom 联调 - 待执行方案归档

> 创建日期：2026-04-07
> 更新日期：2026-04-07
> 状态：待执行

---

## 任务背景

**项目**: 频谱探测系统 POC (SpecDetect_V4)
**目标**: 完成 Proxy-B → Real Atom → Mock Device 完整链路测试
**阻塞问题**: Real Atom 收到 SOAP 请求后崩溃 (Access Violation)

**相关文档**:
- `docs/REAL_ATOM_INTEGRATION/ARCHIVE_20260407.md` - 已归档问题
- `docs/REAL_ATOM_INTEGRATION/PROGRESS.md` - 测试进度

---

## 待执行方案

### 方案1: 分析 SOAP 请求格式差异

**思路**: 对比我们发送的请求与 YL_workspace 原始请求的差异

**操作步骤**:
1. 使用 YL_workspace 的原始请求报文 `B_SglFreqMeas.xml` 直接发送
2. 添加 `resulttype`、`outputchannel` 等我们遗漏的字段
3. 确认 `equid` 必须使用 **GUID 格式** (`8f1b953d-d618-4d4f-a106-81c47183af3c`) 而不是 station id (`53090006`)

**参考文件** (只读，不能修改):
```
D:\arvin\YL_workapace\RXAtomSvcV3\服务请求报文\B_SglFreqMeas.xml
```

**预期结果**: 使用正确格式后 Real Atom 不崩溃

---

### 方案3: 编写设备模拟器连接 Real Atom

**思路**: Mock Device 应作为客户端，主动连接 Real Atom 的 streamsrc 端口

**实现步骤**:
1. Mock Device 主动连接 Real Atom 的 streamsrc 端口 (当前随机如 18012)
2. 按照 RMCPTP 协议发送设备注册帧
3. 实现心跳机制保持连接
4. 响应 Real Atom 发起的测量命令

**参考文档**:
```
docs/06_RMCPTP_v2.0_无线电协议规范.md
```

**架构图**:
```
当前错误模式:
  Mock Device (服务器:9000) ← 无法 → Real Atom (服务器:streamsrc)

正确模式:
  Mock Device (客户端) → 连接 → Real Atom streamsrc端口 (18012)
                        ↓
                    发送 RMCPTP 设备注册帧
```

**关键代码位置**:
- `app/mock_device/tcp_server.py` - 需要改造为客户端模式
- `app/mock_device/frame_builder.py` - RMCPTP 帧构建

---

### 方案4: 尝试不同配置组合

**思路**: 逐步调整配置，找到不崩溃的组合

**配置矩阵**:

| 配置项 | 当前值 | 尝试值1 | 尝试值2 | 尝试值3 |
|--------|--------|---------|---------|---------|
| streamsrc ip | 127.0.0.1 | 空 | 192.168.x.x | 172.18.114.x |
| streamsrc port | 空 | 18012 | 9999 | 9000 |
| devinfo serverip | 127.0.0.1 | 192.168.x.x | 172.18.114.x | 原配置 |
| devinfo serverport | 9000 | 9999 | 原配置 | 任意 |
| mfid | 53090001140007 | 原配置 | - | - |
| equid | GUID | 原配置 | station id | - |

**测试顺序建议**:
1. 先用 YL 原始配置（streamsrc=172.18.114.166, station=172.18.114.231:9999）
2. 逐步替换为 127.0.0.1

**配置文件**:
```
D:\arvin\claude_workspace\RXAtomSvcV3\config\atomsvcconfig.xml
D:\arvin\claude_workspace\RXAtomSvcV3\config\devinfo\*.xml
```

---

### 方案5: 使用 YL_workspace 环境测试

**思路**: 在 YL_workspace 环境中验证 Real Atom 行为

**操作步骤** (在YL_workspace环境中):
1. 在 YL_workspace 机器上启动 Real Atom
2. 使用原始配置文件（不修改）
3. 观察 Real Atom 初始化过程
4. 用 Wireshark 抓包分析设备通信

**注意**: YL_workspace 中的配置文件是只读的，只能观察不能修改

**优点**: YL 配置下 Real Atom 不崩溃，可以观察正常行为

**需要的工具**:
- Wireshark (抓包)
- YL_workspace 机器 (或虚拟机)

**观察点**:
1. Real Atom 启动后的日志
2. 收到请求时的 TCP 通信
3. 与设备的完整 RMCPTP 帧交互

---

## 下一步行动

**推荐顺序**:
1. **方案1** - 使用原始请求格式（最简单）
2. **方案4** - 调整配置组合（需要多次尝试）
3. **方案3** - 编写设备模拟器（架构改变）
4. **方案5** - 使用 YL 环境（需要额外资源）

**立即可执行**:
```bash
# 启动服务
cd D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC
python run_all.py --dual

# 测试 Proxy-A (8080) - 应该正常工作
curl -X POST http://127.0.0.1:8080/soap -H "Content-Type: text/xml" -d @/path/to/YL_request.xml
```

---

## 记忆恢复命令

新 Claude 会话中执行：
```bash
cat D:\arvin\claude_workspace\SpecDetect_V4\docs\REAL_ATOM_INTEGRATION\PENDING_SOLUTIONS_20260407.md
cat D:\arvin\claude_workspace\SpecDetect_V4\docs\REAL_ATOM_INTEGRATION\ARCHIVE_20260407.md
```

---

**归档时间**: 2026-04-07
