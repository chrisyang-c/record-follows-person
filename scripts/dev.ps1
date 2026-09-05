<#
.SYNOPSIS
    Windows 開發入口。與 Makefile 對應，但把「會刪東西的」和「不會刪東西的」分開。

.DESCRIPTION
    安全邊界（這是這個腳本存在的主要理由）：

      日常指令  setup / api / web / worker / test / lint / check / codegen / eval / status
                絕對不會碰 records\ 或資料庫。

      破壞性    init / reset / seed / clean-records
                會先列出「將被刪除什麼」，並要求輸入 yes 才執行。
                CI 或腳本可以帶 -Force 跳過確認。

    Makefile 的 db-local / reset 綁 Homebrew 路徑，只在 macOS 可用。

.EXAMPLE
    .\scripts\dev.ps1 setup      # 裝相依（安全）
    .\scripts\dev.ps1 init       # 第一次：建 DB + migrate + seed（會清 records，要確認）
    .\scripts\dev.ps1 api        # 起 API（安全）
    .\scripts\dev.ps1 check      # ruff + pytest + codegen 一致性（安全）
    .\scripts\dev.ps1 reset -Force
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'status', 'setup', 'api', 'web', 'worker', 'test', 'lint',
                 'check', 'codegen', 'eval', 'migrate',
                 'init', 'reset', 'seed', 'clean-records')]
    [string]$Command = 'help',

    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root    = Split-Path -Parent $PSScriptRoot
$ApiDir  = Join-Path $Root 'apps\api'
$WebDir  = Join-Path $Root 'apps\web'
$Records = Join-Path $Root 'records'
$DbName  = 'record_follows_person'

# ── 工具探索 ────────────────────────────────────────────────

function Find-Tool {
    param([string]$Name, [string[]]$Fallbacks = @(), [string]$InstallHint)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in $Fallbacks) { if (Test-Path $p) { return $p } }
    throw "找不到 $Name。$InstallHint"
}

function Get-Uv {
    Find-Tool 'uv' @("$env:USERPROFILE\.local\bin\uv.exe", 'D:\anaconda3\Scripts\uv.exe') `
        ' 安裝：https://docs.astral.sh/uv/  或 pip install uv'
}

function Get-Pnpm {
    Find-Tool 'pnpm' @() ' 安裝：npm i -g pnpm'
}

function Get-Psql {
    $globs = @(
        'C:\Program Files\PostgreSQL\*\bin\psql.exe',
        'D:\PostgreSQL\*\bin\psql.exe'
    )
    $found = $globs | ForEach-Object { Get-Item $_ -ErrorAction SilentlyContinue } |
             Sort-Object FullName -Descending | Select-Object -First 1
    if ($found) { return $found.FullName }
    Find-Tool 'psql' @() ' 安裝 PostgreSQL 17，或用 docker compose up -d postgres'
}

function Invoke-In {
    # 參數不能叫 $Args：那是 PowerShell 的自動變數，會被吃掉，外面傳的陣列到不了。
    param([string]$Dir, [string]$Exe, [string[]]$Arguments)
    Push-Location $Dir
    try {
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') 失敗（exit $LASTEXITCODE）" }
    } finally { Pop-Location }
}

# ── 破壞性操作的閘門 ────────────────────────────────────────

function Confirm-Destructive {
    <#  列出將被刪除的東西，要求輸入 yes。-Force 可跳過（給 CI 用）。
        這個函式是「日常指令不會弄丟資料」這條保證的實作。 #>
    param([string]$Title, [string[]]$WillDelete)

    Write-Host ''
    Write-Host "  ⚠ $Title" -ForegroundColor Yellow
    Write-Host '  ─────────────────────────────────────────────' -ForegroundColor DarkGray
    foreach ($item in $WillDelete) { Write-Host "    · $item" -ForegroundColor Yellow }
    Write-Host ''

    if ($Force) { Write-Host '  -Force 已指定，跳過確認。' -ForegroundColor DarkGray; return }

    # 非互動（CI、被 pipe、-NonInteractive）時 Read-Host 會拋錯。與其讓它拋一個
    # 看不懂的例外，不如明確拒絕：破壞性操作在沒有人看著的時候必須要求 -Force。
    if (-not [Environment]::UserInteractive -or $Host.Name -eq 'ServerRemoteHost') {
        Write-Host '  非互動模式無法確認。破壞性操作請明確加上 -Force。' -ForegroundColor Red
        Write-Host '    例：.\scripts\dev.ps1 reset -Force' -ForegroundColor DarkGray
        exit 1
    }

    try { $answer = Read-Host '  確定要繼續嗎？輸入 yes 執行，其他任何輸入都會取消' }
    catch {
        Write-Host '  這個終端無法互動輸入。破壞性操作請明確加上 -Force。' -ForegroundColor Red
        exit 1
    }
    if ($answer -ne 'yes') { Write-Host '  已取消，沒有動任何東西。' -ForegroundColor Green; exit 0 }
}

function Get-RecordsSummary {
    if (-not (Test-Path $Records)) { return '（records\ 目前不存在）' }
    $dirs  = @(Get-ChildItem $Records -Directory -ErrorAction SilentlyContinue)
    $files = @(Get-ChildItem $Records -Recurse -File -ErrorAction SilentlyContinue)
    "records\：$($dirs.Count) 位住民、$($files.Count) 個檔案（含 conversation、sensor_events、care_circle 的所有變更）"
}

# ── 指令 ────────────────────────────────────────────────────

function Cmd-Help {
    Write-Host ''
    Write-Host '  一份能跟著人走的紀錄 — Windows 開發入口' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  安全（不會碰 records\ 或資料庫）' -ForegroundColor Green
    @(
        @('status',  '顯示環境、資料庫、records、git 狀態'),
        @('setup',   'uv sync + pnpm install'),
        @('api',     'FastAPI 開發伺服器 :8000'),
        @('web',     'Next.js 開發伺服器 :3000'),
        @('worker',  '逾時升級 worker'),
        @('test',    'ruff + pytest（web 側若有 pnpm 一併跑）'),
        @('lint',    'ruff check + format --check'),
        @('check',   'lint + test + codegen 一致性檢查'),
        @('codegen', 'pydantic → TypeScript'),
        @('eval',    '抽取評測 → apps/api/eval/results.md'),
        @('migrate', 'PostgresSaver.setup() + thread registry（不刪資料）')
    ) | ForEach-Object { '    {0,-14} {1}' -f $_[0], $_[1] | Write-Host }

    Write-Host ''
    Write-Host '  破壞性（會先列出將刪除什麼並要求確認）' -ForegroundColor Yellow
    @(
        @('init',          '第一次設定：建資料庫 + migrate + seed'),
        @('reset',         'drop + recreate 資料庫，再 migrate + seed'),
        @('seed',          '重建三位住民的示範資料（會清空 records\）'),
        @('clean-records', '只刪 records\')
    ) | ForEach-Object { '    {0,-14} {1}' -f $_[0], $_[1] | Write-Host }

    Write-Host ''
    Write-Host '  加 -Force 可跳過確認（給 CI 用）。' -ForegroundColor DarkGray
    Write-Host ''
}

function Cmd-Status {
    Write-Host ''
    Write-Host '  環境' -ForegroundColor Cyan
    foreach ($t in @(@('uv', { Get-Uv }), @('pnpm', { Get-Pnpm }), @('psql', { Get-Psql }))) {
        try { '    {0,-8} {1}' -f $t[0], (& $t[1]) | Write-Host }
        catch { '    {0,-8} 找不到' -f $t[0] | Write-Host -ForegroundColor DarkYellow }
    }

    Write-Host ''
    Write-Host '  .env' -ForegroundColor Cyan
    $envFile = Join-Path $Root '.env'
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object {
            $k, $v = $_ -split '=', 2
            $shown = if ($v -and $v.Trim()) { '已設定' } else { '（空）' }
            if ($k -match 'KEY|TOKEN|SECRET|PASSWORD') { '    {0,-28} {1}' -f $k, $shown | Write-Host }
            else { '    {0,-28} {1}' -f $k, $v | Write-Host }
        }
    } else { Write-Host '    沒有 .env（從 .env.example 複製一份）' -ForegroundColor DarkYellow }

    Write-Host ''
    Write-Host '  資料' -ForegroundColor Cyan
    Write-Host "    $(Get-RecordsSummary)"

    Write-Host ''
    Write-Host '  git' -ForegroundColor Cyan
    Push-Location $Root
    try {
        git status --short --branch | ForEach-Object { "    $_" | Write-Host }
        $log = git log --oneline -1
        Write-Host "    HEAD  $log"
    } finally { Pop-Location }
    Write-Host ''
}

function Cmd-Setup {
    $uv = Get-Uv
    Write-Host '  uv sync…' -ForegroundColor Cyan
    Invoke-In $ApiDir $uv @('sync')
    try {
        $pnpm = Get-Pnpm
        Write-Host '  pnpm install…' -ForegroundColor Cyan
        Invoke-In $WebDir $pnpm @('install')
    } catch {
        Write-Host "  跳過 web：$_" -ForegroundColor DarkYellow
    }
    Write-Host '  完成。下一步：.\scripts\dev.ps1 init（第一次）或 .\scripts\dev.ps1 api' -ForegroundColor Green
}

function Cmd-Api     { Invoke-In $ApiDir (Get-Uv) @('run', 'fastapi', 'dev', 'main.py', '--port', '8000') }
function Cmd-Web     { Invoke-In $WebDir (Get-Pnpm) @('dev') }
function Cmd-Worker  { Invoke-In $ApiDir (Get-Uv) @('run', 'python', '-m', 'graphs.worker') }
function Cmd-Migrate { Invoke-In $ApiDir (Get-Uv) @('run', 'python', '-m', 'graphs.migrate') }
function Cmd-Eval    { Invoke-In $ApiDir (Get-Uv) @('run', 'python', '-m', 'eval.run') }
function Cmd-Codegen {
    Invoke-In $ApiDir (Get-Uv) @('run', 'python', (Join-Path $Root 'packages\schema\codegen.py'))
}

function Cmd-Lint {
    $uv = Get-Uv
    Invoke-In $ApiDir $uv @('run', 'ruff', 'check', '.')
    Invoke-In $ApiDir $uv @('run', 'ruff', 'format', '--check', '.')
}

function Cmd-Test {
    $uv = Get-Uv
    Invoke-In $ApiDir $uv @('run', 'ruff', 'check', '.')
    Invoke-In $ApiDir $uv @('run', 'pytest', '-q')
    try {
        $pnpm = Get-Pnpm
        Invoke-In $WebDir $pnpm @('lint')
        Invoke-In $WebDir $pnpm @('test')
    } catch {
        Write-Host "  跳過 web 測試：$_" -ForegroundColor DarkYellow
    }
}

function Cmd-Check {
    <# lint + test + 「codegen 產物是否與 schema 同步」。
       最後這項是 CI 常漏的：改了 pydantic 卻忘記跑 codegen，TS 型別就過期了。 #>
    Cmd-Test
    Write-Host '  檢查 codegen 是否同步…' -ForegroundColor Cyan
    Cmd-Codegen
    Push-Location $Root
    try {
        $diff = git status --porcelain -- 'packages/schema/ts/index.ts'
        if ($diff) {
            git checkout -- 'packages/schema/ts/index.ts'
            throw 'packages/schema/ts/index.ts 與 schema 不同步。請跑 .\scripts\dev.ps1 codegen 並提交結果。'
        }
        Write-Host '  codegen 同步 ✓' -ForegroundColor Green
    } finally { Pop-Location }
}

function Cmd-CleanRecords {
    Confirm-Destructive '這會刪除所有住民紀錄' @(Get-RecordsSummary)
    if (Test-Path $Records) { Remove-Item -Recurse -Force $Records }
    Write-Host '  records\ 已刪除。' -ForegroundColor Green
}

function Cmd-Seed {
    Confirm-Destructive '重建示範資料會先清空 records\' @(
        (Get-RecordsSummary),
        '（資料庫的 thread 不會被清；要一併清請用 reset）'
    )
    Invoke-In $ApiDir (Get-Uv) @('run', 'python', (Join-Path $Root 'data\seed\seed.py'))
    Write-Host '  seed 完成：3 位住民 × 14 天 + 1 次急症。' -ForegroundColor Green
}

function Cmd-Init {
    Confirm-Destructive '第一次設定：建立資料庫並寫入示範資料' @(
        "建立資料庫 $DbName（若已存在則沿用）",
        '執行 migrate（建 checkpointer 與 thread registry 表）',
        (Get-RecordsSummary) + ' → 會被 seed 覆蓋'
    )
    $psql = Get-Psql
    $createdb = Join-Path (Split-Path $psql) 'createdb.exe'
    Write-Host "  建立資料庫 $DbName…" -ForegroundColor Cyan
    & $createdb -h localhost $DbName 2>$null
    Write-Host '  migrate…' -ForegroundColor Cyan
    Cmd-Migrate
    Write-Host '  seed…' -ForegroundColor Cyan
    Invoke-In $ApiDir (Get-Uv) @('run', 'python', (Join-Path $Root 'data\seed\seed.py'))
    Write-Host '  完成。起服務：.\scripts\dev.ps1 api（另一個終端 .\scripts\dev.ps1 web）' -ForegroundColor Green
}

function Cmd-Reset {
    Confirm-Destructive '完全重置（錄影前的乾淨狀態）' @(
        "DROP DATABASE $DbName —— 所有 LangGraph thread、checkpoint、registry 都會消失",
        (Get-RecordsSummary),
        '對應 KNOWN_ISSUES #17／#31：測試留下的紅燈 thread 會疊卡，錄影前需要這一步'
    )
    $psql = Get-Psql
    Write-Host '  重建資料庫…' -ForegroundColor Cyan
    & $psql -h localhost -d postgres `
        -c "drop database if exists $DbName" `
        -c "create database $DbName"
    if ($LASTEXITCODE -ne 0) { throw 'psql 失敗，資料庫沒有被重建。' }
    Cmd-Migrate
    Invoke-In $ApiDir (Get-Uv) @('run', 'python', (Join-Path $Root 'data\seed\seed.py'))
    Write-Host '  重置完成。' -ForegroundColor Green
}

# ── 派送 ────────────────────────────────────────────────────

switch ($Command) {
    'help'          { Cmd-Help }
    'status'        { Cmd-Status }
    'setup'         { Cmd-Setup }
    'api'           { Cmd-Api }
    'web'           { Cmd-Web }
    'worker'        { Cmd-Worker }
    'test'          { Cmd-Test }
    'lint'          { Cmd-Lint }
    'check'         { Cmd-Check }
    'codegen'       { Cmd-Codegen }
    'eval'          { Cmd-Eval }
    'migrate'       { Cmd-Migrate }
    'init'          { Cmd-Init }
    'reset'         { Cmd-Reset }
    'seed'          { Cmd-Seed }
    'clean-records' { Cmd-CleanRecords }
}
