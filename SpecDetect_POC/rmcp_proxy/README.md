# RMCP TCP 流量监听代理

## 功能

1. **TCP透明代理** - 监听本地端口，转发请求到目标设备
2. **流量记录** - 记录原始二进制数据和结构化日志
3. **帧头解析** - 实时解析RMCP协议帧头
4. **XML解析** - 自动识别并记录XML请求内容

## 使用方法

### 1. 修改设备配置

将设备配置 `config/devinfo/*.xml` 中的设备地址指向代理：

```xml
<!-- 修改前 -->
<station serverip="172.18.114.231" serverport="9999" .../>

<!-- 修改后 -->
<station serverip="127.0.0.1" serverport="9998" .../>
```

### 2. 启动代理

```bash
cd C:/Users/YangLei/Downloads/atom/rmcp_proxy
python rmcp_proxy.py
```

### 3. 触发通信

通过 RXAtomTestTool3.exe 或其他工具发起请求。

### 4. 查看记录

代理会自动在 `capture/` 目录下创建记录文件：
- `capture_*.raw` - 原始二进制流量（Wireshark可用）
- `capture_*.log` - 结构化文本日志
- `capture_*.json` - JSON格式记录

## 控制台输出示例

```
[2026-04-10 18:00:00.123] C->S  REQUEST      len=700   ver=7 flags=0x01 from=127.0.0.1:12345
[2026-04-10 18:00:00.456] S->C  RESPONSE    len=51    ver=7 flags=0x00 from=172.18.114.231:9999
[2026-04-10 18:00:00.789] S->C  DATA_29      len=1053  ver=7 flags=0x01 from=172.18.114.231:9999
```

## 配置

编辑 `config.py` 修改以下配置：

```python
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9998
DEVICE_HOST = "172.18.114.231"
DEVICE_PORT = 9999
LOG_DIR = "C:/Users/YangLei/Downloads/atom/rmcp_proxy/capture"
```

## 命令行选项

```bash
python rmcp_proxy.py           # 启动代理
python rmcp_proxy.py --test     # 运行测试
python rmcp_proxy.py --help     # 显示帮助
```

## 验证步骤

1. 确保设备配置已修改
2. 启动代理: `python rmcp_proxy.py`
3. 检查控制台输出是否有连接信息
4. 触发设备通信
5. 查看 `capture/` 目录下的日志文件

## 注意事项

- 验证完成后记得将设备配置改回原值
- 确保防火墙允许9998端口
- 原始文件可以用Wireshark打开分析
