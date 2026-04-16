# 工具与日志路径汇总

**创建时间**: 2026-04-15
**用途**: Atom streamsrc 滤波分析相关工具和日志路径

---

## 日志文件

### streamsrc 日志
```
experimental\logs\
  streamsrc_raw_20260414_215726.log      # streamsrc 原始帧 (65 bytes 分片帧)
  spectrum_20260414_215726.log          # streamsrc 频谱日志 (重组后)
```

### rmcp 日志
```
rmcp_proxy\capture\
  raw_fscan_20260414_215655.log         # rmcp 原始 FSCAN 数据
  capture_20260414_215014.log            # rmcp 流量日志
  capture_20260414_215014.json           # rmcp JSON 格式
  connections_20260414_215014.csv        # rmcp 连接记录
```

---

## 抓包工具

```
D:\arvin\claude_workspace\RawCap.exe              # RawCap 抓包工具 (Windows)
D:\arvin\claude_workspace\loopback.pcap           # 旧版抓包数据
```

### streamsrc pcap 文件
```
experimental\
  streamsrc_capture_*.pcap                      # streamsrc 抓包 (旧)
  capture_all_*.pcap                            # 综合抓包 (旧)
  logs\capture_streamsrc.pcap
```

---

## 测试程序

```
experimental\
  atom_streamsrc_listener.py           # streamsrc 测试工具 (连接 18012)
  verify_parser.py                     # 离线解析验证脚本

rmcp_proxy\
  rmcp_proxy.py                        # rmcp 代理/抓包 (连接 9996)

run_all.py                             # 一键启动所有服务
```

---

## 任务文档

```
experimental\
  TASKS_20260415_atom_filter_analysis.md  # 当前分析任务
  TASKS_20260413_atom_streamsrc_listener.md
  TASKS_20260413_atom_soap_capture.md
```

---

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Atom (Real) | 8282 | SOAP 服务 |
| streamsrc | 18012 | Atom 数据回调通道 |
| rmcp_proxy | 9996 | RMCPTP 透明代理 |
| 设备 | 1449 | RMCPTP 服务端 |

---

## 数据格式对比

| 属性 | streamsrc | rmcp |
|------|-----------|------|
| 端口 | 18012 | 9996 |
| 帧大小 | 65 bytes (分片) | 1053 bytes |
| 电平数 | 18/帧 (分片), 529/完整 | 512 |
| 原始值范围 | [0, 24933] | [-1055, -289] |
| 无效值 | -32768 | 无 |
| 格式 | dBuV → dBm | 直接 dBm (raw/10) |
