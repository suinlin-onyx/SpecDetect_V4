# 频谱探测系统 - 独立窗口启动脚本
# 每个服务在独立的终端窗口中运行

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 先清理可能占用端口的进程
Write-Host "检查端口占用..." -ForegroundColor Cyan
$Ports = @(9000, 9090, 8080)
foreach ($port in $Ports) {
    $connections = netstat -ano | Select-String ":$port\s+.*LISTENING"
    if ($connections) {
        foreach ($conn in $connections) {
            $pid = ($conn -split '\s+')[-1]
            if ($pid -match '^\d+$') {
                Write-Host "  发现残留进程 PID=$pid 占用端口 $port，正在终止..." -ForegroundColor Yellow
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  频谱探测系统 - 独立窗口启动" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

# 启动顺序：Mock -> Atom -> Proxy
# 每个服务在独立的 cmd 窗口中运行

Write-Host "1. 启动虚拟设备 (端口 9000)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k title Mock Device - Port 9000 && cd /d $ScriptDir && python main_mock.py"

Start-Sleep -Seconds 2

Write-Host "2. 启动原子服务 (端口 9090)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k title Atom Service - Port 9090 && cd /d $ScriptDir && python main_atom.py"

Start-Sleep -Seconds 2

Write-Host "3. 启动代理服务 (端口 8080)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k title Proxy Service - Port 8080 && cd /d $ScriptDir && python main_proxy.py"

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  所有服务已启动!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  虚拟设备: http://127.0.0.1:9000 (仅TCP)" -ForegroundColor White
Write-Host "  原子服务: http://127.0.0.1:9090" -ForegroundColor White
Write-Host "  代理服务: http://127.0.0.1:8080" -ForegroundColor White
Write-Host ""
Write-Host "  聚合页面: http://localhost:8080/dashboard" -ForegroundColor White
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
