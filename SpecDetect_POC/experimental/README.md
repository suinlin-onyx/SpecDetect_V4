# 实验性功能: 直接 SOAP → RMCP 发送到设备

## 目的

绕过 Atom，直接将 SOAP 请求转换为 RMCP 帧并发送到真实设备。

## 架构对比

### 原有链路
```
TestTool → SOAP Proxy → Real Atom → Device
                          (转换发生在这里)
```

### 实验链路
```
TestTool → SOAP Proxy → [实验程序] → Device
                      (直接 SOAP → RMCP 转换并发送)
```

## 文件

- `soap_to_rmcp_direct.py` - 主程序

## 使用方法

```python
from soap_to_rmcp_direct import send_soap_to_device, test_interface

# 发送 SOAP 请求
result = send_soap_to_device(soap_xml, host='100.72.95.36', port=1449)

if result['success']:
    print(f"Action XML: {result['action_xml']}")
    print(f"RMCP Frame: {result['rmcp_frame_hex']}")
    print(f"Response: {result['response']}")
else:
    print(f"Error: {result['error']}")
```

## 测试接口

```bash
cd experimental
python soap_to_rmcp_direct.py
```

## 待验证接口

1. B_MScan (funcid=14) - 多信道扫描
2. B_MScanDF (funcid=16) - 多信道扫描测向
3. B_PScan (funcid=13) - 频谱扫描
4. B_QueryFaciDevStat - 设备状态查询

## 注意事项

- 这是实验性代码，不要影响现有功能
- 所有修改都在此目录中进行
- 设备地址: 100.72.95.36:1449 (从 capture 确定)
