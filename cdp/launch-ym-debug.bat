@echo off
cd /d "%~dp0.."
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%CD%\launcher\start-ym-remote.ps1" -MusicOnly
