# SGAtom 打包指南

## 环境要求

- Python 3.7+ (Win7 兼容版本)
- PyInstaller 4.10+
- Windows 10/11 (打包机)

## 目录结构

```
SpecDetect_Atom/
├── src/                    # 源代码
├── config/                 # 配置文件
├── runtime/                # Win7 运行时 DLLs
├── docs/                   # 文档
├── SpecDetect_Atom.spec    # PyInstaller 配置
├── version_info.txt        # 版本信息
└── runtime_hook.py         # 运行时钩子
```

## 打包步骤

### 1. 清理旧构建

```bash
# 清理 dist 和 build 目录
rm -rf dist/* build/*
```

### 2. 确认版本号

编辑 `version_info.txt`，更新以下字段：

```python
filevers=(1, 0, 7, 0),    # 文件版本
prodvers=(1, 0, 7, 0),     # 产品版本
StringStruct(u'FileVersion', u'1.0.7'),
StringStruct(u'ProductVersion', u'1.0.7'),
```

### 3. 执行打包

```powershell
# 使用 Python37 (Win7 兼容版本)
Set-Location 'D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_UI_Atom\SpecDetect_Atom'

& 'C:\Users\tuoyi5\AppData\Local\Programs\Python\Python37\Scripts\pyinstaller.exe' `
    SpecDetect_Atom.spec `
    --distpath 'dist\SGAtom_v1.0.7'
```

### 4. 验证输出

```
dist/
└── SGAtom_v1.0.7/
    └── SGAtom.exe    # 单文件 exe (约 7MB)
```

## 完整部署包结构

exe 依赖以下文件，需与 exe 同目录部署：

```
SGAtom_v1.0.7/
├── SGAtom.exe           # 主程序
├── python37.dll          # Python 运行时
├── vcruntime140.dll      # Visual C++ 运行时
├── ucrtbase.dll          # Universal C Runtime
└── api-ms-win-*.dll      # Windows API DLLs (Win7 兼容)
```

## 运行时行为

首次运行 exe 时，会自动：

1. **复制 config 目录** - 从 exe 内置数据复制到 exe 同级
2. **创建 log 目录** - 与 config 同级，记录日志

```
exe 所在目录/
├── SGAtom.exe
├── config/      ← 首次运行自动复制
└── log/         ← 首次运行自动创建
    └── atom_*.log
```

## 常见问题

### UTF-8 BOM 错误

如果 Win7 上出现 `Unexpected UTF-8 BOM` 错误：

**原因：** `settings.json` 文件带有 BOM 头

**修复：** `config.py` 中使用 `encoding='utf-8-sig'` 读取 JSON

```python
# config.py line 246
with open(config_file, 'r', encoding='utf-8-sig') as f:
```

### Win7 闪退无日志

**原因：** 日志未及时初始化

**修复：** `runtime_hook.py` 在最早时机初始化日志

## PyInstaller 相关文件

| 文件 | 作用 |
|------|------|
| `SpecDetect_Atom.spec` | 打包配置 |
| `runtime_hook.py` | 运行时钩子 (DLL路径 + 日志初始化) |
| `version_info.txt` | exe 版本信息 |

## 打包命令速查

### 方式1: 使用 build.bat 脚本（推荐）

```batch
cd program\SpecDetect_Atom
build.bat 1.0.7
```

输出: `dist\SGAtom_1.0.7\SGAtom.exe`

### 方式2: 手动打包

```powershell
# 清理
rm -rf dist/* build/*

# 更新 version_info.txt 中的版本号

# 执行打包
& 'C:\Users\tuoyi5\AppData\Local\Programs\Python\Python37\Scripts\pyinstaller.exe' SpecDetect_Atom.spec --distpath 'dist\SGAtom_v1.0.7'

# 复制 runtime DLLs (从旧版部署)
xcopy /y /q runtime\*.dll dist\SGAtom_v1.0.7\
```
