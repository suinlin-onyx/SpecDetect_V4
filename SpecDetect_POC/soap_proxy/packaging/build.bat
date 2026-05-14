@echo off
REM Build script for SOAPProxy (single exe)
REM Usage: build.bat (run from soap_proxy root, NOT from packaging/)

setlocal enabledelayedexpansion

set "VERSION=1.0.1"
set "PYINSTALLER=C:\Users\tuoyi5\AppData\Local\Programs\Python\Python37\Scripts\pyinstaller.exe"

echo ========================================
echo   SOAPProxy Build v%VERSION% (single exe)
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

if not exist "%PYINSTALLER%" (
    echo [ERROR] PyInstaller not found
    exit /b 1
)

echo [1/3] Cleaning...
if exist "%PROJECT_DIR%\build" rmdir /s /q "%PROJECT_DIR%\build"
if exist "%PROJECT_DIR%\dist\SOAPProxy.exe" del /q "%PROJECT_DIR%\dist\SOAPProxy.exe"

echo [2/3] Building...
"%PYINSTALLER%" --onefile "%SCRIPT_DIR%SOAPProxy.spec" --distpath "%PROJECT_DIR%\dist"
if errorlevel 1 (
    echo [ERROR] Build failed
    exit /b 1
)

echo [3/3] Done.
echo.
echo Output: %PROJECT_DIR%\dist\SOAPProxy.exe
echo.
pause
