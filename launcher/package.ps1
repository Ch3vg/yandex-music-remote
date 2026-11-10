# Packages launcher\start-ym-remote.ps1 into YandexMusicRemote.exe when ps2exe is installed.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$sourceFile = Join-Path $here "start-ym-remote.ps1"
$icon = Join-Path $here "app.ico"
$output = Join-Path $root "YandexMusicRemote.exe"

if (-not (Get-Command Invoke-ps2exe -ErrorAction SilentlyContinue)) {
    if (Get-Module -ListAvailable -Name ps2exe) {
        Import-Module ps2exe
    }
}
if (-not (Get-Command Invoke-ps2exe -ErrorAction SilentlyContinue)) {
    Write-Host "ps2exe не установлен. Exe не собран."
    exit 0
}
Invoke-ps2exe -inputFile $sourceFile -outputFile $output -noConsole -sta -iconFile $icon -title "Yandex Music Remote"
Write-Host $output
