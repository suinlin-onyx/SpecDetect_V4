@echo off
chcp 65001 >nul
echo Starting RMCP Proxy + RXAtomSvcV3 services...
echo.
echo [1/3] Starting RMCP Proxy on port 9996...
start "RMCP_Proxy" cmd /k "cd /d D:\arvin\claude_workspace\rmcp_proxy && python rmcp_proxy.py"
timeout /t 3 /nobreak >nul
echo.
echo [2/3] Starting Real Atom (AtomSvcV3.exe)...
start "" "D:\arvin\claude_workspace\RXAtomSvcV3\AtomSvcV3.exe"
timeout /t 3 /nobreak >nul
echo.
echo [3/3] Starting Test Tool (RXAtomTestTool3.exe)...
start "" "D:\arvin\claude_workspace\RXAtomSvcV3\RXAtomTestTool3.exe"
echo.
echo Done. All services started.
echo.
echo Architecture:
echo   AtomSvcV3 -^> rmcp_proxy:9996 -^> Real Device (100.89.170.72:9997)
echo.
pause
