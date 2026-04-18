# SpecDetect UI-Atom 开发指南

**创建日期**: 2026-04-13
**更新日期**: 2026-04-13

---

## 1. 开发环境

### 1.1 目录结构

```
SpecDetect_UI_Atom/
├── SpecDetect_Client/          # Client 应用
├── SpecDetect_Atom/            # Atom Service 应用
├── config/                     # 配置文件
│   └── devinfo/               # 设备预设
└── docs/                      # 文档
```

### 1.2 依赖

```bash
# Client
pip install flask flask-sockets websocket-client

# Atom
pip install flask flask-sockets pyrmcp
```

### 1.3 启动

```bash
# Terminal 1: 启动 Atom
cd SpecDetect_Atom
python main.py

# Terminal 2: 启动 Client
cd SpecDetect_Client
python main.py
```

---

## 2. 配置说明

### 2.1 Client 配置 (SpecDetect_Client/config/settings.json)

```json
{
  "client": {
    "host": "127.0.0.1",
    "port": 8080,
    "ws_port": 8081
  },
  "atom": {
    "host": "127.0.0.1",
    "soap_port": 8282
  },
  "preset": {
    "devinfo_dir": "../../config/devinfo"
  }
}
```

### 2.2 Atom 配置 (SpecDetect_Atom/config/settings.json)

```json
{
  "atom": {
    "host": "127.0.0.1",
    "soap_port": 8282,
    "ws_port": 8081
  },
  "device": {
    "host": "100.72.95.36",
    "port": 1449
  }
}
```

### 2.3 设备预设 XML

设备预设存储在 `config/devinfo/` 目录，每个设备一个 XML 文件。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<device>
    <id>设备ID</id>
    <equid>设备唯一标识</equid>
    <name>设备名称</name>
    <parameters>
        <parameter name="参数名" value="参数值" />
    </parameters>
</device>
```

---

## 3. 接口定义

### 3.1 SOAP 接口 (Client → Atom)

| 接口 | 方法 | 说明 |
|------|------|------|
| /connect | POST | 连接设备 |
| /disconnect | POST | 断开设备 |
| /status | GET | 查询连接状态 |
| /B_FScan | POST | 频段扫描 |
| /B_SglFreqDF | POST | 单频测向 |
| /B_MScan | POST | 多信道扫描 |
| /B_MScanDF | POST | 多信道扫描测向 |
| /B_StopMeas | POST | 停止测量 |

### 3.2 WebSocket 回调 (Atom → Client)

| 事件 | 说明 |
|------|------|
| connected | 设备连接成功 |
| disconnected | 设备断开 |
| streaming_start | streaming 开始 |
| streaming_data | streaming 数据帧 |
| streaming_end | streaming 结束 |
| error | 错误信息 |

---

## 4. 开发任务

### 4.1 Phase 1: 基础框架

- [ ] 创建 Client Flask 应用框架
- [ ] 创建 Atom Flask 应用框架
- [ ] 配置 JSON 文件加载
- [ ] WebSocket 基础通信

### 4.2 Phase 2: PresetMgr

- [ ] 解析设备预设 XML
- [ ] 设备切换逻辑
- [ ] UI 设备列表展示

### 4.3 Phase 3: SOAP↔RMCP Bridge

- [ ] SOAP 请求解析
- [ ] RMCP 帧构建
- [ ] RMCP 响应解析
- [ ] 设备 TCP 连接管理

### 4.4 Phase 4: 数据处理

- [ ] FSCAN 数据解析
- [ ] streaming 数据回调
- [ ] UI 图表展示

---

## 5. 参考资料

- 协议文档: `docs/RX-RMCPTP_通信协议v2.0_通用协议_整理.md`
- RMCP 开发规范: `docs/RMCP_开发规范.md`
- 实验代码: `SpecDetect_POC/experimental/`

---

## 6. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-13 | 初始版本 |
