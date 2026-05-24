@echo off
REM Unified Build Script for SGAtom + SOAPProxy
REM Packages both apps with shared Python environment
REM
REM Target structure:
REM   dist\
REM   +--SGAtom.exe
REM   +--SOAPProxy.exe
REM   +--runtime\
REM   :   +--python37.dll
REM   :   +--vcruntime140.dll
REM   :   +--ucrtbase.dll
REM   :   +--api-ms-win-core-*.dll
REM   +--config\ (auto-created by app)
REM   +--logs\ (auto-created by app)

setlocal enabledelayedexpansion

REM ========================================
REM Versions (update manually)
REM ========================================
set "ATOM_VERSION=1.2.5"
set "PROXY_VERSION=1.1.8"

REM ========================================
REM Paths
REM ========================================
set "ROOT_DIR=D:\arvin\claude_workspace\SpecDetect_V4"
set "OUTPUT_DIR=%ROOT_DIR%\dist"
set "PYINSTALLER=C:\Users\tuoyi5\AppData\Local\Programs\Python\Python37\Scripts\pyinstaller.exe"

REM Project dirs
set "ATOM_PROJECT_DIR=%ROOT_DIR%\SpecDetect_UI_Atom\SpecDetect_Atom"
set "PROXY_PROJECT_DIR=%ROOT_DIR%\SpecDetect_POC\soap_proxy"

REM Temp build dirs
set "ATOM_BUILD_DIR=%ATOM_PROJECT_DIR%\build_onedir"
set "PROXY_BUILD_DIR=%PROXY_PROJECT_DIR%\build_onedir"

echo ========================================
echo   Unified Build: SGAtom + SOAPProxy
echo ========================================
echo   Atom:   v%ATOM_VERSION%
echo   Proxy:  v%PROXY_VERSION%
echo ========================================
echo.

REM Check PyInstaller
if not exist "%PYINSTALLER%" (
    echo [ERROR] PyInstaller not found at:
    echo   %PYINSTALLER%
    exit /b 1
)

REM ========================================
REM Step 1: Clean
REM ========================================
echo [1/7] Cleaning...
if exist "%ATOM_BUILD_DIR%" rmdir /s /q "%ATOM_BUILD_DIR%"
if exist "%PROXY_BUILD_DIR%" rmdir /s /q "%PROXY_BUILD_DIR%"
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"

REM ========================================
REM Step 2: Build SGAtom (--onedir)
REM ========================================
echo [2/7] Building SGAtom v%ATOM_VERSION% (onedir)...
pushd "%ATOM_PROJECT_DIR%"
    "%PYINSTALLER%" --onedir packaging\SpecDetect_Atom.spec --distpath "%ATOM_BUILD_DIR%"
    if errorlevel 1 (
        echo [ERROR] SGAtom build failed
        popd
        exit /b 1
    )
popd

REM ========================================
REM Step 3: Build SOAPProxy (--onedir)
REM ========================================
echo [3/7] Building SOAPProxy v%PROXY_VERSION% (onedir)...
pushd "%PROXY_PROJECT_DIR%"
    "%PYINSTALLER%" --onedir packaging\SOAPProxy.spec --distpath "%PROXY_BUILD_DIR%"
    if errorlevel 1 (
        echo [ERROR] SOAPProxy build failed
        popd
        exit /b 1
    )
popd

REM ========================================
REM Step 4: Create output structure
REM ========================================
echo [4/7] Creating output structure...
mkdir "%OUTPUT_DIR%" 2>nul
mkdir "%OUTPUT_DIR%\runtime" 2>nul

REM ========================================
REM Step 5: Copy executables
REM ========================================
echo [5/7] Copying executables...
if exist "%ATOM_BUILD_DIR%\SGAtom.exe" (
    copy /y "%ATOM_BUILD_DIR%\SGAtom.exe" "%OUTPUT_DIR%\SGAtom_v%ATOM_VERSION%.exe"
) else (
    echo [ERROR] SGAtom.exe not found
    exit /b 1
)
if exist "%PROXY_BUILD_DIR%\SOAPProxy_v%PROXY_VERSION%.exe" (
    copy /y "%PROXY_BUILD_DIR%\SOAPProxy_v%PROXY_VERSION%.exe" "%OUTPUT_DIR%\SOAPProxy_v%PROXY_VERSION%.exe"
) else (
    echo [ERROR] SOAPProxy_v%PROXY_VERSION%.exe not found
    exit /b 1
)

REM ========================================
REM Step 6: Copy shared runtime DLLs
REM ========================================
echo [6/7] Copying runtime DLLs...
set "RUNTIME_DIR=%ATOM_PROJECT_DIR%\runtime"
if exist "%RUNTIME_DIR%\python37.dll" copy /y "%RUNTIME_DIR%\python37.dll" "%OUTPUT_DIR%\runtime\"
if exist "%RUNTIME_DIR%\vcruntime140.dll" copy /y "%RUNTIME_DIR%\vcruntime140.dll" "%OUTPUT_DIR%\runtime\"
if exist "%RUNTIME_DIR%\ucrtbase.dll" copy /y "%RUNTIME_DIR%\ucrtbase.dll" "%OUTPUT_DIR%\runtime\"
if exist "%RUNTIME_DIR%\api-ms-win-core-*.dll" (
    for %%f in ("%RUNTIME_DIR%\api-ms-win-core-*.dll") do (
        copy /y "%%f" "%OUTPUT_DIR%\runtime\"
    )
)

REM ========================================
REM Step 7: Copy config files
REM ========================================
echo [7/7] Copying config files...
mkdir "%OUTPUT_DIR%\config" 2>nul
if exist "%ATOM_PROJECT_DIR%\config\settings.json" copy /y "%ATOM_PROJECT_DIR%\config\settings.json" "%OUTPUT_DIR%\config\"
if exist "%PROXY_PROJECT_DIR%\config\proxy_settings.json" copy /y "%PROXY_PROJECT_DIR%\config\proxy_settings.json" "%OUTPUT_DIR%\config\"

REM ========================================
REM Done
REM ========================================
echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Output structure:
echo   %OUTPUT_DIR%\
echo   +--SGAtom_v%ATOM_VERSION%.exe
echo   +--SOAPProxy_v%PROXY_VERSION%.exe
echo   +--runtime\
echo   :   +--python37.dll
echo   :   +--vcruntime140.dll
echo   :   +--ucrtbase.dll
echo   :   +--api-ms-win-core-*.dll
echo   +--config\ (auto-created by app on first run)
echo   +--logs\ (auto-created by app on first run)
echo.
echo NOTE: Run SGAtom.exe and SOAPProxy.exe from this directory.
echo       Config and logs directories are created automatically.
echo.
pause
