# 真实 Atom 连接配置

> 创建日期：2026-04-06
> 更新日期：2026-04-06
> 用途：记录 Real Atom 的连接配置信息

---

## 重要更新 (2026-04-06)

### Real Atom 位置变更

| 项目 | 原路径 | 新路径 |
|------|--------|--------|
| Real Atom 服务 | `D:\arvin\vhf_monitoring_ws\RXAtomSvcV3` | `D:\arvin\claude_workspace\RXAtomSvcV3` |

### 设备连接配置变更

为了将 Real Atom 连接到 Mock Device (127.0.0.1:9000)，已修改以下配置：

| 配置文件 | 修改项 | 原值 | 新值 |
|----------|--------|------|------|
| `config/atomsvcconfig.xml` | `streamsrc ip` | `172.18.114.166` | `127.0.0.1` |
| `config/atomsvcconfig.xml` | `streamsrc port` | `""` | `9000` |
| `config/devinfo/53090001140007_*.xml` | `serverip` | `172.18.114.x` | `127.0.0.1` |
| `config/devinfo/53090001140007_*.xml` | `serverport` | `9999` | `9000` |

**目的**: Real Atom → Mock Device 直连测试

---

## 当前配置

### 开发环境（Mock Atom）

| 配置项 | 值 |
|--------|---|
| Host | 127.0.0.1 |
| Port | 9090 |
| 用途 | 本地开发测试 |
| 状态 | ✅ 正常 |

### 真实环境（Real Atom）

| 配置项 | 值 |
|--------|---|
| Host | 127.0.0.1 |
| Port | 8282 |
| 用途 | 真实设备通信测试 |
| 状态 | ✅ 已确认 |

---

## 配置目录结构

```
D:\arvin\claude_workspace\RXAtomSvcV3\
├── AtomSvcV3.exe          # 主程序
├── config/
│   ├── atomsvcconfig.xml  # SOAP 服务配置 + streamsrc
│   ├── devinfo/
│   │   └── 53090001140007_8f1b953d-d618-4d4f-a106-81c47183af3c.xml  # 设备信息
│   ├── devinfo_black/     # 原始设备配置（未修改）
│   ├── env/              # 环境配置
│   └── wsdl/             # WSDL 文件
│       └── 8282/         # Real Atom 端点 WSDL
└── log/                  # 日志目录
```

---

## 配置文件详解

### atomsvcconfig.xml

```xml
<system>
    <svc port="8282" atomprotocol="boer" ... />
    <streamsrc ip="127.0.0.1" port="9000" />  <!-- 修改后：指向 Mock Device -->
</system>
```

**streamsrc**: Real Atom 连接的设备地址

### devinfo/*.xml

```xml
<station id="53090006"
    serverip="127.0.0.1"    <!-- 修改后：指向 Mock Device -->
    serverport="9000"        <!-- 修改后：Mock Device 端口 -->
    protocol="rmcp"
    ... />
```

**station**: 监测站设备配置

---

## 端口对照表

| 系统 | Atom 类型 | 端口 | 说明 |
|------|-----------|------|------|
| SpecDetect_V4 | Mock Atom | 9090 | 本项目 Mock |
| SpecDetect_V4 | Mock Device | 9000 | 本项目 Mock Device |
| VHFMonitor_Python | Mock Atom | 8288 | 对方系统 Mock |
| VHFMonitor_Python | Real Atom | 8282 | 对方系统 Real (旧) |
| **RXAtomSvcV3** | **Real Atom** | **8282** | **Real Atom (新位置)** |

---

## 配置文件位置

### SpecDetect_V4 配置

| 文件 | 用途 |
|------|------|
| `SpecDetect_POC/config/settings_proxy_b.py` | Proxy-B 指向 Real Atom |

```python
REAL_ATOM_HOST = '127.0.0.1'
REAL_ATOM_PORT = 8282
```

### Real Atom 配置

| 文件 | 用途 |
|------|------|
| `RXAtomSvcV3/config/atomsvcconfig.xml` | streamsrc 指向 Mock Device |
| `RXAtomSvcV3/config/devinfo/*.xml` | station 指向 Mock Device |

---

## 切换步骤

### 启用 Real Atom → Mock Device 连接

1. **确认 Mock Device 运行** → `netstat -ano | grep ":9000"`
2. **重启 Real Atom** → 使配置生效
3. **验证连接** → 检查 Real Atom 日志

### 恢复原始配置（使用 devinfo_black）

1. 删除 `devinfo/` 下的文件
2. 复制 `devinfo_black/*` 到 `devinfo/`
3. 重启 Real Atom

---

## 注意事项

- 配置不持久化，重启后回归默认
- Real Atom 与 Mock Atom 的 SOAP 接口格式不同
- RMCPTP 协议版本需一致（当前 v2.0）
- 设备文件 `53090001140007` 对应 mfid=53090001140007

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `docs/REAL_ATOM_INTEGRATION/ISSUES.md` | 问题日志 |
| `docs/REAL_ATOM_INTEGRATION/PROGRESS.md` | 联调进度 |
| `docs/15_Atom_Device_架构分析_20260406.md` | Atom-Device 架构分析 |

---

**最后更新**: 2026-04-06
