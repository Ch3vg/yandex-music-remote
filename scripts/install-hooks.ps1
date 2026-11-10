# Подключает локальные Git-хуки из папки .githooks (pre-commit и pre-push).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    git config core.hooksPath .githooks
    $configured = git config --get core.hooksPath
    Write-Host "Git-хуки подключены: core.hooksPath = $configured" -ForegroundColor Green
    Write-Host "Активны проверки:"
    Write-Host "  - pre-commit: запрет прямых коммитов в master/dev, сканер секретов, проверка web/dist, pytest"
    Write-Host "  - pre-push:   запрет прямого push в master/dev, pytest"
} finally {
    Pop-Location
}
