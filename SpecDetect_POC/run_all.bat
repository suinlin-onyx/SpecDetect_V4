@echo off
chcp 65001 >nul 2>&1
title claude_sas
cd /d "%~dp0"
python run_all.py
pause