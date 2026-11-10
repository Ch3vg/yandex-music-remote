@echo off
cd /d "%~dp0.."
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%CD%\start-ym-remote.ps1"
