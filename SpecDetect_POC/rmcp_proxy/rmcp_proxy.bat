@echo off
REM RMCP Proxy launcher
REM Win7 DLL 兼容：将 runtime/ 加入 PATH
set "PATH=%~dp0runtime;%PATH%"

REM 自动查找 exe
for %%f in ("%~dp0rmcp_proxy_v*.exe") do (
    "%%f" %*
    goto :eof
)
echo [ERROR] rmcp_proxy_v*.exe not found
pause
