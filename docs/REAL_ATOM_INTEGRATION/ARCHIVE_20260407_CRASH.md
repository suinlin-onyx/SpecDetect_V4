# 崩溃事件归档 - 2026-04-07

## 崩溃记录

| 项目 | 值 |
|------|------|
| 发生时间 | 2026-04-07 21:49:57 |
| 崩溃文件 | `D:\arvin\claude_workspace\RXAtomSvcV3\远端的crash\[2026-04-07 21：49：57]AtomSvcV3_crash.dmp` |
| 文件大小 | 120,927 bytes |

## 崩溃分析

**分析工具**: Python minidump解析器

**发现**:
- 文件签名: MDMP (有效MiniDuMP格式)
- .NET运行时字符串: ".vb_release.191206-1406" (VB.NET 6.0应用)
- ExceptionStream存在但数据全为0 (Code=0, Address=0)
- 崩溃dump未完成写入，异常信息不可用

**根因推测**:
请求间隔过短(3秒)导致远程Atom资源耗尽崩溃

## 错误测试流程 (已废弃)

```python
# 错误的流程
for operation in operations:
    send_request(operation)           # 发请求
    time.sleep(3)                    # ❌ 错误：只等3秒
    send_request('B_StopMeas')       # 发停止
    time.sleep(3)                    # ❌ 错误位置
```

## 正确测试流程

```python
# 正确的流程

# 阶段1: 连接设备
send_connect_request()
if wait_for_callback(timeout=20):  # 回调成功
    device_connected = True
else:                                # 超时20秒
    device_connected = False

# 阶段2: 接口测试循环
for operation in operations:
    send_request(operation)              # 发请求
    wait_for_callback(timeout=20)        # 等待回调或超时
    send_request('B_StopMeas')           # 发停止
    time.sleep(5)                        # 等5秒
```

## 待测试接口

| # | 接口 | resulttype | 是否需要停止 |
|---|------|------------|-------------|
| 1 | B_FScan | FSCAN | ✅ |
| 2 | B_FScanDF | WBDF | ✅ |
| 3 | B_MScan | MSCAN | ✅ |
| 4 | B_MScanDF | (空) | ✅ |
| 5 | B_PScan | PSCAN | ✅ |
| 6 | B_QueryDeviceInfo | (空) | ❌ |
| 7 | B_QueryFaciDevStat | (空) | ❌ |
| 8 | B_SglFreqDF | SFDF, audio | ✅ |
| 9 | B_SglFreqMeas | ITU, audio | ✅ |
| 10 | B_StopMeas | (空) | - |
| 11 | B_TaskModification | (空) | ❌ |
| 12 | B_WBDF | WBDF | ✅ |
