# Win7 兼容打包方案

## 问题描述

在 Windows 7 上启动 PyInstaller 打包的程序时报错：

```
系统错误
无法启动此程序，因为计算机中丢失 api-ms-win-core-sysinfo-l1-2-0.dll。
尝试重新安装该程序以解决此问题。
```

## 根本原因

PyInstaller 打包的程序依赖 Python 3.7，Python 3.7 依赖 Windows API Sets（`api-ms-win-core-*` 系列 DLL）。这些 DLL 是 Windows 8+ 才引入的，Windows 7 上不存在。

`api-ms-win-core-sysinfo-l1-2-0.dll` 导出的关键函数是 `GetSystemTimePreciseAsFileTime`，这是 Win8+ 的 API。

## 解决方案：自编译 Stub DLL + App-Local Deployment

### 核心思路

为每个缺失的 API Set DLL 创建 stub 实现，绝大部分函数转发到 kernel32，仅 `GetSystemTimePreciseAsFileTime` 做 Win7 兼容降级。

### 目录结构

```
SpecDetect_Atom/
├── stub/                                 # DLL stub 源码
│   ├── api-ms-win-core-sysinfo-l1-2-0.c
│   ├── api-ms-win-core-sysinfo-l1-2-0_exports.def
│   └── _c.bat                            # 编译脚本
├── runtime/                              # 收集所有 stub DLL
│   ├── api-ms-win-core-sysinfo-l1-2-0.dll
│   └── ... (其他 api-ms-win-* DLLs)
└── SpecDetect_Atom.spec                  # PyInstaller 配置
```

### Step 1 — 编写 Stub DLL 源码

`stub/api-ms-win-core-sysinfo-l1-2-0.c`：

```c
/*
 * api-ms-win-core-sysinfo-l1-2-0.dll stub
 *
 * Provides GetSystemTimePreciseAsFileTime (Win8+) on Win7 by delegating
 * to GetSystemTimeAsFileTime. Other functions forward to kernel32.
 */
#include <windows.h>

typedef void (WINAPI *GetSystemTimePreciseAsFileTime_t)(LPFILETIME);
typedef void (WINAPI *GetSystemTimeAsFileTime_t)(LPFILETIME);
// ... 其他函数指针类型

static HMODULE s_kernel32;

static HMODULE get_kernel32(void) {
    if (!s_kernel32)
        s_kernel32 = GetModuleHandleW(L"kernel32.dll");
    return s_kernel32;
}

#define RESOLVE_KERNEL32(func, type) do { \
    if (!func) { \
        HMODULE k32 = get_kernel32(); \
        if (k32) func = (type)GetProcAddress(k32, #func); \
    } \
} while (0)

/* 大部分函数直接转发到 kernel32 */
void WINAPI GetNativeSystemInfo(LPSYSTEM_INFO lpSystemInfo) {
    static GetNativeSystemInfo_t s_GetNativeSystemInfo;
    RESOLVE_KERNEL32(s_GetNativeSystemInfo, GetNativeSystemInfo_t);
    if (s_GetNativeSystemInfo) s_GetNativeSystemInfo(lpSystemInfo);
}

/* Win8+ API，Win7 回退到 GetSystemTimeAsFileTime */
void WINAPI GetSystemTimePreciseAsFileTime(LPFILETIME lpSystemTime) {
    static GetSystemTimeAsFileTime_t s_GetSystemTimeAsFileTime;
    if (!s_GetSystemTimeAsFileTime) {
        HMODULE k32 = get_kernel32();
        if (k32)
            s_GetSystemTimeAsFileTime = (GetSystemTimeAsFileTime_t)
                GetProcAddress(k32, "GetSystemTimeAsFileTime");
    }
    if (s_GetSystemTimeAsFileTime && lpSystemTime)
        s_GetSystemTimeAsFileTime(lpSystemTime);
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    return TRUE;
}
```

`stub/api-ms-win-core-sysinfo-l1-2-0_exports.def`：

```def
LIBRARY "api-ms-win-core-sysinfo-l1-2-0"
EXPORTS
    EnumSystemFirmwareTables
    GetNativeSystemInfo
    GetOsSafeBootMode
    GetProductInfo
    GetSystemFirmwareTable
    GetSystemTimePreciseAsFileTime
    SetComputerNameExW
    SetSystemTime
    VerSetConditionMask
```

### Step 2 — 编译 Stub DLL

`stub/_c.bat`：

```bat
@echo off
cd /d "D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_UI_Atom\SpecDetect_Atom\stub"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cl.exe /nologo /LD /O2 /GS- /MT /Tc"api-ms-win-core-sysinfo-l1-2-0.c" ^
    /Fe"api-ms-win-core-sysinfo-l1-2-0.dll" ^
    /link kernel32.lib /DEF:api-ms-win-core-sysinfo-l1-2-0_exports.def
```

编译产物 `api-ms-win-core-sysinfo-l1-2-0.dll` 放入 `runtime/` 目录。

### Step 3 — PyInstaller 自动收集 runtime DLL

`SpecDetect_Atom.spec` 在打包时自动从 `runtime/` 收集所有 DLL：

```python
_runtime_dir = os.path.join(SPECPATH, '..', 'runtime')
_binaries = []
if os.path.isdir(_runtime_dir):
    for _dll in _glob.glob(os.path.join(_runtime_dir, '*.dll')):
        _binaries.append((_dll, '.'))   # 打包到 exe 同目录
```

执行 `pyinstaller SpecDetect_Atom.spec` 后，所有 `runtime/*.dll` 都会被打包到 exe 同一目录，程序运行时就在同目录下找到 stub DLL，不再依赖系统缺失的 API Sets。

### 已解决的 API Sets DLLs

当前 `runtime/` 中包含以下 stub DLLs：

| DLL | 状态 |
|-----|------|
| `api-ms-win-core-sysinfo-l1-2-0.dll` | 手动编译 stub |
| `api-ms-win-core-path-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-console-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-datetime-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-debug-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-errorhandling-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-file-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-handle-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-heap-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-interlocked-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-kernel32-legacy-l1-1-1.dll` | 手动编译 stub |
| `api-ms-win-core-libraryloader-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-localization-l1-2-0.dll` | 手动编译 stub |
| `api-ms-win-core-memory-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-namedpipe-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-processenvironment-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-processthreads-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-profile-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-rtlsupport-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-string-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-synch-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-timezone-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-core-util-l1-1-0.dll` | 手动编译 stub |
| `api-ms-win-crt-*.dll` | 手动编译 stub |

## 添加新的缺失 DLL

如果在新环境中发现新的缺失 DLL，按以下步骤添加：

1. **确认缺失的 DLL 名称**，从报错信息中获取（如 `api-ms-win-core-xxx-l1-x-0.dll`）
2. **创建源码文件** `stub/api-ms-win-core-xxx-l1-x-0.c`，参考现有 stub 格式
3. **创建导出定义** `stub/api-ms-win-core-xxx-l1-x-0_exports.def`，列出所有导出函数
4. **创建编译脚本** `stub/_compile_xxx.bat`，修改 `_c.bat` 中的文件名
5. **执行编译**，产物放入 `runtime/`
6. **验证** — 在 Win7 上运行 exe，确认不再报该 DLL 缺失

## 部署结构

最终 Win7 部署包结构：

```
SGAtom_vX.Y.Z/
├── SGAtom.exe                    # 主程序
├── python37.dll                  # Python 运行时
├── vcruntime140.dll              # VC++ 运行时
├── ucrtbase.dll                  # Universal C Runtime
├── api-ms-win-core-sysinfo-l1-2-0.dll
├── api-ms-win-core-path-l1-1-0.dll
├── api-ms-win-crt-*.dll
├── ... (所有 api-ms-win-* DLLs)
└── config/                      # 首次运行自动复制
```
