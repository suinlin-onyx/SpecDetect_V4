@echo off
chcp 65001 >nul 2>&1
title SpecDetect - Mock Device
cd /d "%~dp0"
echo ================================================
echo 启动虚拟设备 (Mock Device) - 端口 9000
echo ================================================
python main_mock.py
