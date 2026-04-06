# 频谱探测系统 - Python快速验证

## 项目概述

本项目用于验证频谱探测系统的核心业务流程，包括：
- Web → 代理服务 → 原子服务 → 虚拟设备 的完整数据链路
- SOAP协议解析与处理
- RMCPTP二进制协议封装与解析
- 多种业务场景模拟

## 项目结构

```
SpecDetect_POC/
├── app/                           # 应用代码
│   ├── proxy_service/             # 代理服务 (SOAP处理)
│   ├── atom_service/              # 原子服务 (业务逻辑)
│   │   └── services/              # 业务服务
│   │       ├── monitor.py         # 监测服务
│   │       ├── direction.py       # 测向服务
│   │       └── device.py          # 设备管理
│   └── mock_device/               # 虚拟设备
│       ├── tcp_server.py          # TCP服务器
│       ├── frame_builder.py       # RMCPTP帧构建
│       ├── data_generator.py      # 数据模拟器
│       └── scenarios/             # 模拟场景
├── config/
│   └── settings.py                # 配置文件
├── tests/                         # 测试代码
├── utils/                         # 工具函数
├── main_proxy.py                  # 代理服务入口
├── main_atom.py                   # 原子服务入口
├── main_mock.py                   # 虚拟设备入口
└── run_all.py                     # 一键启动脚本
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动所有服务

```bash
python run_all.py
```

### 3. 单独启动服务

```bash
# 启动虚拟设备 (端口 9000)
python main_mock.py

# 启动原子服务 (端口 9090)
python main_atom.py

# 启动代理服务 (端口 8080)
python main_proxy.py
```

## 服务说明

### 代理服务 (Proxy Service)

负责SOAP协议的解析与路由转发。

- **端口**: 8080
- **接口**:
  - `POST /soap` - SOAP请求入口
  - `GET /health` - 健康检查

### 原子服务 (Atom Service)

负责业务逻辑处理和命令封装。

- **端口**: 9090
- **接口**:
  - `GET /health` - 健康检查
  - `POST /device/connect` - 连接设备
  - `POST /device/disconnect` - 断开设备
  - `GET /device/status` - 设备状态
  - `POST /monitor/sglfreq` - 单频测量
  - `POST /monitor/fscan` - 频段扫描
  - `POST /direction/sglfreqdf` - 单频测向

### 虚拟设备 (Mock Device)

模拟真实设备的响应。

- **端口**: 9000
- **支持的场景**:
  - `normal` - 常规监测
  - `interference` - 干扰场景
  - `abnormal` - 异常场景
  - `boundary` - 边界场景
  - `stress` - 压力测试

## RMCPTP协议

帧头结构（18字节）：

| 字段 | 类型 | 长度 | 说明 |
|------|------|------|------|
| dwLength | uint32 | 4字节 | 报文长度 |
| tmStamp | uint64 | 8字节 | 时间戳 |
| nVersion | uint16 | 2字节 | 版本号 (0x0007) |
| nDataType | uint8 | 1字节 | 数据类型 |
| nFlags | uint8 | 1字节 | 标志位 |
| nCheckSum | uint16 | 2字节 | 校验和 |

## 运行测试

```bash
pytest tests/ -v
```

## 配置说明

编辑 `config/settings.py` 修改：
- 服务端口配置
- 协议参数
- 场景配置
- 日志级别
