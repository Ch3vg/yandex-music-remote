<#
.SYNOPSIS
Настраивает правила защиты веток (Repository Rulesets) на GitHub для Ch3vg/yandex-music-remote:
  1. Основная ветка — master, автоудаление веток при merge отключено (чтобы dev не удалялась при merge в master).
  2. Прямой push в master и dev запрещён (включая администратора репозитория: bypass_actors = []).
  3. Вливание в master и dev только через Pull Request при условии прохождения проверок:
     - autotests (Commit Status: pending -> passed / failed)
     - pytest-and-web-build (GitHub Actions CI job)
     - branch-flow (проверка направления PR: рабочие ветки -> dev -> master)

.EXAMPLE
$env:GITHUB_TOKEN = "github_pat_..."
.\scripts\setup-github-rules.ps1
#>
param(
    [string]$Owner = "Ch3vg",
    [string]$Repo = "yandex-music-remote",
    [string]$Token = $env:GITHUB_TOKEN
)

$ErrorActionPreference = "Stop"

if (-not $Token) {
    Write-Error "Не задан токен GitHub. Передайте -Token или задайте переменную окружения `$env:GITHUB_TOKEN (с правом Administration: Read and write)."
    exit 1
}

$headers = @{
    "Accept"               = "application/vnd.github+json"
    "Authorization"        = "Bearer $Token"
    "X-GitHub-Api-Version" = "2022-11-28"
    "User-Agent"           = "ym-remote-setup"
}

$baseUrl = "https://api.github.com/repos/$Owner/$Repo"

Write-Host "1/3 Обновление настроек репозитория $Owner/$Repo..."
$repoPatch = @{
    default_branch         = "master"
    delete_branch_on_merge = $false
    allow_squash_merge     = $true
    allow_merge_commit     = $true
    allow_rebase_merge     = $false
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Patch -Uri $baseUrl -Headers $headers -Body $repoPatch -ContentType "application/json" | Out-Null

function Set-BranchRuleset([string]$Name, [string]$BranchRef, [bool]$StrictUpToDate) {
    $payload = @{
        name          = $Name
        target        = "branch"
        enforcement   = "active"
        bypass_actors = @()
        conditions    = @{
            ref_name = @{
                include = @($BranchRef)
                exclude = @()
            }
        }
        rules         = @(
            @{ type = "deletion" },
            @{ type = "non_fast_forward" },
            @{
                type       = "pull_request"
                parameters = @{
                    dismiss_stale_reviews_on_push     = $true
                    require_code_owner_review         = $false
                    require_last_push_approval        = $false
                    required_approving_review_count   = 0
                    required_review_thread_resolution = $true
                }
            },
            @{
                type       = "required_status_checks"
                parameters = @{
                    strict_required_status_checks_policy = $StrictUpToDate
                    do_not_enforce_on_create             = $true
                    required_status_checks               = @(
                        @{ context = "autotests" },
                        @{ context = "pytest-and-web-build" },
                        @{ context = "branch-flow" }
                    )
                }
            }
        )
    }

    $existing = @(Invoke-RestMethod -Method Get -Uri "$baseUrl/rulesets" -Headers $headers)
    $found = $existing | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    $json = $payload | ConvertTo-Json -Depth 10

    if ($found) {
        Invoke-RestMethod -Method Put -Uri "$baseUrl/rulesets/$($found.id)" -Headers $headers -Body $json -ContentType "application/json" | Out-Null
        Write-Host "  Обновлён ruleset '$Name' (id=$($found.id)) для $BranchRef" -ForegroundColor Green
    } else {
        $created = Invoke-RestMethod -Method Post -Uri "$baseUrl/rulesets" -Headers $headers -Body $json -ContentType "application/json"
        Write-Host "  Создан ruleset '$Name' (id=$($created.id)) для $BranchRef" -ForegroundColor Green
    }
}

Write-Host "2/3 Настройка защиты ветки master..."
Set-BranchRuleset -Name "protect-master" -BranchRef "refs/heads/master" -StrictUpToDate $true

Write-Host "3/3 Настройка защиты ветки dev..."
Set-BranchRuleset -Name "protect-dev" -BranchRef "refs/heads/dev" -StrictUpToDate $false

Write-Host "Готово! Правила веток на GitHub активированы." -ForegroundColor Cyan
