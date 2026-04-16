@echo off
REM Restart services for SpecDetect_V4
REM Usage: restart_services.bat

echo ========================================
echo SpecDetect_V4 服务重启脚本
echo ========================================

REM 停止服务
echo [1/4] 停止 AtomSvcV3.exe ...
taskkill /F /IM AtomSvcV3.exe 2>nul
if %errorlevel%==0 (
    echo      停止成功
) else (
    echo      AtomSvcV3 未运行或已停止
)

echo [2/4] 停止 python.exe ...
taskkill /F /IM python.exe 2>nul
if %errorlevel%==0 (
    echo      停止成功
) else (
    echo      python 未运行或已停止
)

REM 等待服务完全停止
echo [3/4] 等待服务停止...
timeout /t 2 /nobreak >nul

REM 启动服务
echo [4/4] 启动服务...
REM 先启动 AtomSvcV3
start "" "C:\path\to\AtomSvcV3.exe"
echo      AtomSvcV3 启动命令已发送

REM 等待 AtomSvcV3 启动
timeout /t 3 /nobreak >nul

REM 启动 rmcp_proxy
echo      启动 rmcp_proxy.py ...
start "" python "D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\rmcp_proxy.py"

echo.
echo ========================================
echo 服务重启完成
echo ========================================
pause
