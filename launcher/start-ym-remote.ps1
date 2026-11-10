# Finds Yandex Music, starts CDP if needed, runs uvicorn inside a kill-on-close job,
# and shows a 360x580 QR window. Closing the window stops uvicorn only.
param(
    [switch]$MusicOnly
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Get-ProjectRoot {
    $entry = $PSCommandPath
    if (-not $entry) {
        $entry = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    }
    $dir = Split-Path -Parent $entry
    if (Test-Path (Join-Path $dir "src\ym_remote")) { return $dir }
    $parent = Split-Path -Parent $dir
    if (Test-Path (Join-Path $parent "src\ym_remote")) { return $parent }
    return $parent
}

function Read-DotEnv([string]$Path) {
    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $map }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $parts = $line.Split("=", 2)
        $map[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
    }
    return $map
}

function Test-TcpPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $wait.AsyncWaitHandle.WaitOne(500, $false)) { return $false }
        $client.EndConnect($wait)
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Find-YandexMusic {
    $dir = Join-Path $env:LOCALAPPDATA "Programs\YandexMusic"
    if (-not (Test-Path -LiteralPath $dir)) { return $null }
    foreach ($name in @("Яндекс Музыка.exe", "YandexMusic.exe")) {
        $path = Join-Path $dir $name
        if (Test-Path -LiteralPath $path) { return $path }
    }
    $fallback = Get-ChildItem -LiteralPath $dir -Filter *.exe -File | Where-Object {
        $_.Name -notmatch "Uninstall" -and $_.Name -notmatch "Update"
    } | Select-Object -First 1
    if ($fallback) { return $fallback.FullName }
    return $null
}

function Get-MusicProcesses([string]$Exe) {
    Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and ($_.ExecutablePath -ieq $Exe)
    }
}

function Test-CdpReady([string]$Exe, [int]$Port) {
    if (-not (Test-TcpPort $Port)) { return $false }
    foreach ($proc in @(Get-MusicProcesses $Exe)) {
        $cmd = [string]$proc.CommandLine
        if ($cmd -like "*remote-debugging-port*" -and $cmd -like "*remote-allow-origins*") {
            return $true
        }
    }
    return $false
}

function Stop-Music([string]$Exe) {
    foreach ($proc in @(Get-MusicProcesses $Exe)) {
        & taskkill.exe /T /F /PID $proc.ProcessId | Out-Null
    }
    $deadline = (Get-Date).AddSeconds(6)
    do {
        $left = @(Get-MusicProcesses $Exe)
        if ($left.Count -eq 0) { return }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
}

function Wait-Tcp([int]$Port, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        if (Test-TcpPort $Port) { return $true }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Show-Error([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show($Text, "Yandex Music Remote") | Out-Null
}

if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne "STA") {
    $arg = "-NoProfile -STA -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($MusicOnly) { $arg += " -MusicOnly" }
    Start-Process -FilePath "powershell.exe" -ArgumentList $arg | Out-Null
    exit 0
}

$root = Get-ProjectRoot
$envFile = Read-DotEnv (Join-Path $root ".env")
$port = 8001
$cdpPort = 9222
if ($envFile.ContainsKey("PORT") -and $envFile["PORT"]) { $port = [int]$envFile["PORT"] }
if ($envFile.ContainsKey("CDP_PORT") -and $envFile["CDP_PORT"]) { $cdpPort = [int]$envFile["CDP_PORT"] }

$exe = Find-YandexMusic
if (-not $exe) {
    Show-Error "Яндекс Музыка не найдена в $env:LOCALAPPDATA\Programs\YandexMusic."
    exit 1
}

$restarted = $false
if (-not (Test-CdpReady $exe $cdpPort)) {
    Stop-Music $exe
    Start-Process -FilePath $exe -ArgumentList @(
        "--remote-debugging-port=$cdpPort",
        "--remote-allow-origins=*"
    ) | Out-Null
    if (-not (Wait-Tcp $cdpPort 20)) {
        Show-Error "Не удалось запустить Яндекс Музыку с отладкой CDP (порт $cdpPort)."
        exit 1
    }
    $restarted = $true
}

if ($MusicOnly) { exit 0 }

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Show-Error "Не найден интерпретатор: $python"
    exit 1
}
if (-not $envFile.ContainsKey("YANDEX_MUSIC_TOKEN") -or -not $envFile["YANDEX_MUSIC_TOKEN"]) {
    Show-Error "YANDEX_MUSIC_TOKEN не найден в .env"
    exit 1
}

$logDir = Join-Path $root "cdp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "server-cdp.log"
$stderr = Join-Path $logDir "server-cdp.err.log"
Set-Content -LiteralPath $stdout -Value "" -Encoding UTF8
Set-Content -LiteralPath $stderr -Value "" -Encoding UTF8

$env:PYTHONPATH = Join-Path $root "src"
$env:PYTHONUTF8 = "1"
$env:PORT = "$port"
$env:CDP_PORT = "$cdpPort"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class YmRemoteJob {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateJobObject(IntPtr a, string name);
    [DllImport("kernel32.dll")]
    public static extern bool SetInformationJobObject(IntPtr hJob, int infoClass, IntPtr info, uint length);
    [DllImport("kernel32.dll")]
    public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
[StructLayout(LayoutKind.Sequential)]
public struct YmBasicLimits {
    public long PerProcessUserTimeLimit;
    public long PerJobUserTimeLimit;
    public uint LimitFlags;
    public UIntPtr MinimumWorkingSetSize;
    public UIntPtr MaximumWorkingSetSize;
    public uint ActiveProcessLimit;
    public UIntPtr Affinity;
    public uint PriorityClass;
    public uint SchedulingClass;
}
[StructLayout(LayoutKind.Sequential)]
public struct YmIoCounters {
    public ulong ReadOperationCount;
    public ulong WriteOperationCount;
    public ulong OtherOperationCount;
    public ulong ReadTransferCount;
    public ulong WriteTransferCount;
    public ulong OtherTransferCount;
}
[StructLayout(LayoutKind.Sequential)]
public struct YmExtendedLimits {
    public YmBasicLimits BasicLimitInformation;
    public YmIoCounters IoInfo;
    public UIntPtr ProcessMemoryLimit;
    public UIntPtr JobMemoryLimit;
    public UIntPtr PeakProcessMemoryUsed;
    public UIntPtr PeakJobMemoryUsed;
}
"@

$job = [YmRemoteJob]::CreateJobObject([IntPtr]::Zero, $null)
$limits = New-Object YmExtendedLimits
$limits.BasicLimitInformation.LimitFlags = 0x2000
$size = [Runtime.InteropServices.Marshal]::SizeOf($limits)
$ptr = [Runtime.InteropServices.Marshal]::AllocHGlobal($size)
[Runtime.InteropServices.Marshal]::StructureToPtr($limits, $ptr, $false)
[void][YmRemoteJob]::SetInformationJobObject($job, 9, $ptr, [uint32]$size)
[Runtime.InteropServices.Marshal]::FreeHGlobal($ptr)

$server = Start-Process -FilePath $python -PassThru -WindowStyle Hidden -WorkingDirectory $root `
    -ArgumentList @("-u", "-m", "uvicorn", "ym_remote.interfaces.asgi:app", "--host", "0.0.0.0", "--port", "$port") `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr
[void][YmRemoteJob]::AssignProcessToJobObject($job, $server.Handle)

function Stop-Remote {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
    if ($job -ne [IntPtr]::Zero) {
        [void][YmRemoteJob]::CloseHandle($job)
        $script:job = [IntPtr]::Zero
    }
}

$ready = $false
$deadline = (Get-Date).AddSeconds(20)
do {
    try {
        $info = Invoke-RestMethod -Uri "http://127.0.0.1:$port/network-info" -TimeoutSec 2
        if ($info.url) { $ready = $true; break }
    } catch {
        Start-Sleep -Milliseconds 300
    }
} while ((Get-Date) -lt $deadline)

if (-not $ready) {
    Stop-Remote
    Show-Error "Пульт не ответил на /network-info за 20 секунд. Лог: $stderr"
    exit 1
}

$publicUrl = [string]$info.url
$caption = "Яндекс Музыка и пульт запущены."
if ($restarted) { $caption = "Яндекс Музыка перезапущена с отладкой CDP." }

$form = New-Object System.Windows.Forms.Form
$form.Text = "Yandex Music Remote"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(360, 580)
$form.MinimumSize = $form.Size
$form.MaximumSize = $form.Size
$form.BackColor = [System.Drawing.Color]::FromArgb(18, 18, 18)
$form.ForeColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Text = "Yandex Music Remote"
$title.ForeColor = [System.Drawing.Color]::FromArgb(240, 192, 0)
$title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $false
$title.TextAlign = "MiddleCenter"
$title.SetBounds(12, 8, 328, 28)

$status = New-Object System.Windows.Forms.Label
$status.Text = $caption
$status.ForeColor = [System.Drawing.Color]::White
$status.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$status.AutoSize = $false
$status.TextAlign = "MiddleCenter"
$status.SetBounds(12, 40, 328, 36)

$picture = New-Object System.Windows.Forms.PictureBox
$picture.SetBounds(62, 82, 220, 220)
$picture.SizeMode = "Zoom"
$picture.BackColor = [System.Drawing.Color]::White
try {
    $web = New-Object System.Net.WebClient
    $bytes = $web.DownloadData("http://127.0.0.1:$port/qr")
    $stream = New-Object System.IO.MemoryStream(,$bytes)
    $image = [System.Drawing.Image]::FromStream($stream)
    $copy = New-Object System.Drawing.Bitmap($image)
    $picture.Image = $copy
    $image.Dispose()
    $stream.Dispose()
} catch {
    $status.Text = "Не удалось загрузить QR."
}

$urlLabel = New-Object System.Windows.Forms.Label
$urlLabel.Text = $publicUrl
$urlLabel.Font = New-Object System.Drawing.Font("Consolas", 9)
$urlLabel.ForeColor = [System.Drawing.Color]::White
$urlLabel.AutoSize = $false
$urlLabel.TextAlign = "MiddleCenter"
$urlLabel.SetBounds(8, 310, 336, 32)

function New-Button([string]$Text, [int]$Top) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $Text
    $button.SetBounds(40, $Top, 280, 32)
    $button.FlatStyle = "Flat"
    $button.BackColor = [System.Drawing.Color]::FromArgb(28, 28, 30)
    $button.ForeColor = [System.Drawing.Color]::White
    return $button
}

$copyButton = New-Button "Скопировать ссылку" 352
$logButton = New-Button "Открыть лог" 392
$openButton = New-Button "Открыть в браузере" 432
$stopButton = New-Button "Остановить пульт" 480

$copyButton.Add_Click({ [System.Windows.Forms.Clipboard]::SetText($publicUrl) })
$logButton.Add_Click({ Start-Process -FilePath "notepad.exe" -ArgumentList $stdout })
$openButton.Add_Click({ Start-Process $publicUrl })
$stopButton.Add_Click({ $form.Close() })

$form.Controls.AddRange(@($title, $status, $picture, $urlLabel, $copyButton, $logButton, $openButton, $stopButton))

try {
    [void]$form.ShowDialog()
} finally {
    Stop-Remote
    if ($picture.Image) { $picture.Image.Dispose() }
    $form.Dispose()
}
