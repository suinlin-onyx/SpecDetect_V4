# SOAPProxy 打包文档

## 单文件打包

```bash
# 从 soap_proxy 根目录运行
packaging\build.bat
```

输出：`dist\SOAPProxy.exe`

## Win7 兼容性

PyInstaller `--onefile` 模式在 Windows 7 上缺少 `api-ms-win-core-sysinfo-l1-2-0.dll` 等 API Set DLL。

### 解决方案

1. **准备 runtime 目录**：从 `SpecDetect_Atom\runtime\` 复制所有 DLL 到 `soap_proxy\runtime\`
2. **修改 spec 文件**：自动收集 runtime 目录下的所有 DLL
3. **PyInstaller 打包时**：将 DLL 打包进 exe，运行时解压到 exe 同目录

### 实现细节

**spec 文件**：

```python
import glob as _glob
import os as _os

_spec_dir = os.path.abspath(os.path.dirname(SPEC))

_runtime_dir = os.path.join(_spec_dir, '..', 'runtime')
_binaries = []
if os.path.isdir(_runtime_dir):
    for _dll in _glob.glob(os.path.join(_runtime_dir, '*.dll')):
        _binaries.append((_dll, '.'))

a = Analysis(
    ['../transparent_proxy.py'],
    binaries=_binaries,
    ...
)
```

**encodings 模块**：Python 3.7 + PyInstaller onefile 需显式声明 encodings 模块：

```python
hiddenimports=[
    'encodings',
    'encodings.aliases',
    'encodings.ascii',
    'encodings.latin_1',
    'encodings.mbcs',
    'encodings.utf_8',
    ...
]
```

## 目录结构

```
soap_proxy/
├── dist/
│   └── SOAPProxy.exe          # 单文件打包输出
├── runtime/                    # Win7 兼容 DLL
│   ├── api-ms-win-*.dll
│   └── ...
└── packaging/
    ├── build.bat              # 打包脚本
    └── SOAPProxy.spec         # PyInstaller 配置
```

## 配置项

`config/proxy_settings.json`（首次运行自动生成）：

```json
{
  "soap_proxy": {
    "listen_host": "127.0.0.1",  // 绑定地址：127.0.0.1=本地, 0.0.0.0=所有网卡
    "listen_port": 8284,           // SOAP 代理监听端口
    "target_host": "127.0.0.1",   // 转发目标地址
    "target_port": 8282,           // 转发目标端口
    "output_host": "127.0.0.1"    // SINK模式outputchannel使用的地址
  },
  "log": {
    "dir": "logs"                  // 日志目录
  }
}
```
