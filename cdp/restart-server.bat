@echo off
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Не найден интерпретатор: %PYTHON%
  exit /b 1
)
if not exist "%ROOT%\cdp" mkdir "%ROOT%\cdp"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -like '*ym_remote.interfaces.asgi:app*' -or $_.CommandLine -like '*server_cdp:app*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
break > "%ROOT%\cdp\server-cdp.log"
break > "%ROOT%\cdp\server-cdp.err.log"
for /f %%P in ('powershell -NoProfile -Command "$p = 8001; if (Test-Path -LiteralPath ''%ROOT%\.env'') { foreach ($l in Get-Content -LiteralPath ''%ROOT%\.env'' -Encoding UTF8) { if ($l -match ''^\s*PORT\s*=\s*(\d+)\s*$'' -and [int]$Matches[1] -gt 0) { $p = [int]$Matches[1] } } }; Write-Output $p"') do set "PORT=%%P"
if not defined PORT set "PORT=8001"
powershell -NoProfile -Command "$env:PYTHONPATH='%ROOT%\src'; $env:PYTHONUTF8='1'; $env:PORT='%PORT%'; Start-Process -FilePath '%PYTHON%' -ArgumentList '-u','-m','uvicorn','ym_remote.interfaces.asgi:app','--host','0.0.0.0','--port','%PORT%' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%\cdp\server-cdp.log' -RedirectStandardError '%ROOT%\cdp\server-cdp.err.log'"
set /a n=0
:wait
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%PORT%/network-info -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL%==0 exit /b 0
set /a n+=1
if %n% GEQ 15 exit /b 1
timeout /t 1 /nobreak >nul
goto wait
