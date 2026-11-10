# Delegates to launcher\start-ym-remote.ps1
$script = Join-Path $PSScriptRoot "launcher\start-ym-remote.ps1"
& powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $script @args
exit $LASTEXITCODE
