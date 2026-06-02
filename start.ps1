# AI Novel - Smart Launcher
param(
    [string]$BaseDir
)
$ErrorActionPreference = 'Stop'
if (-not $BaseDir) { $BaseDir = $args[0] }
if (-not $BaseDir) { $BaseDir = $PSScriptRoot }
$BACKEND_DIR = Join-Path $BaseDir 'backend'
$FRONTEND_DIR = Join-Path $BaseDir 'frontend'
$BACKEND_URL = 'http://127.0.0.1:8000'
$FRONTEND_URL = 'http://localhost:5173'

function Write-Status($msg) { Write-Host '[INFO]' $msg }
function Write-Err($msg) { Write-Host '[ERROR]' $msg -ForegroundColor Red }
function Write-OK($msg) { Write-Host '[OK]' $msg -ForegroundColor Green }

function Test-ProcessAlive([int]$ProcessId) {
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Sync-PidFile([string]$PidFilePath, [int[]]$ProcessIds) {
    $normalized = @($ProcessIds | Where-Object { $_ -and $_ -gt 0 } | Sort-Object -Unique)
    if ($normalized.Count -eq 0) {
        if (Test-Path -LiteralPath $PidFilePath) {
            Remove-Item -LiteralPath $PidFilePath -Force -ErrorAction SilentlyContinue
        }
        return
    }

    ($normalized | ForEach-Object { $_.ToString() }) |
        Out-File -FilePath $PidFilePath -Encoding ascii
}

function Get-RecordedProcessIds([string]$PidFilePath) {
    if (-not (Test-Path -LiteralPath $PidFilePath)) { return @() }
    return @(
        Get-Content -LiteralPath $PidFilePath -ErrorAction SilentlyContinue |
        ForEach-Object { ($_ | Out-String).Trim() } |
        Where-Object { $_ -match '^\d+$' } |
        ForEach-Object { [int]$_ }
    )
}

function Get-ListeningProcessIds([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) { return @() }
    return @(
        $connections |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -and $_ -gt 0 }
    )
}

function Get-BackendProcessIds() {
    $resolvedBackendDir = (Resolve-Path -LiteralPath $BACKEND_DIR).Path
    return @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $commandLine = [string]$_.CommandLine
            if (-not $commandLine) { return $false }

            $commandLine -like "*$resolvedBackendDir*" -or
            $commandLine -match 'python(?:\.exe)?["'']?\s+run\.py' -or
            $commandLine -match 'app\.main:app'
        } |
        Select-Object -ExpandProperty ProcessId -Unique |
        Where-Object { $_ -and $_ -gt 0 }
    )
}

function Stop-ProcessTrees([int[]]$ProcessIds, [string]$Label) {
    $taskkillPath = Join-Path $env:SystemRoot 'System32\taskkill.exe'

    foreach ($processId in ($ProcessIds | Sort-Object -Unique)) {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $taskkillOutput = & $taskkillPath /PID $processId /T /F 2>&1
        $ErrorActionPreference = $previousErrorActionPreference
        $taskkillExitCode = $LASTEXITCODE
        $taskkillText = $taskkillOutput | Out-String
        if ($taskkillExitCode -ne 0 -and -not ($taskkillText -match 'not found|没有运行的实例|process .* not found')) {
            Write-Err "Failed to terminate $Label PID $processId"
            Write-Err $taskkillText.Trim()
            Read-Host "Close manually and press Enter to exit"
            exit 1
        }
    }
}

function Stop-BackendProcesses([int]$MaxPasses = 6) {
    $backendPidFile = Join-Path $BACKEND_DIR 'app.pid'

    for ($pass = 1; $pass -le $MaxPasses; $pass++) {
        $listeningIds = @(Get-ListeningProcessIds -Port 8000)
        $backendIds = @(Get-BackendProcessIds)
        $recordedIds = @(Get-RecordedProcessIds -PidFilePath $backendPidFile)

        # Only trust recorded PIDs when they are still alive and still look like our backend.
        $validRecordedIds = @(
            $recordedIds |
            Where-Object { Test-ProcessAlive $_ } |
            Where-Object { $_ -in $listeningIds -or $_ -in $backendIds }
        )
        if (@($validRecordedIds | Sort-Object -Unique).Count -ne @($recordedIds | Sort-Object -Unique).Count) {
            Sync-PidFile -PidFilePath $backendPidFile -ProcessIds $validRecordedIds
        }

        $processIds = @(
            $listeningIds
            $backendIds
            $validRecordedIds
        ) | Where-Object { $_ -and $_ -gt 0 } | Sort-Object -Unique

        if ($processIds.Count -eq 0) {
            Write-Status 'No stale backend process found'
            return
        }

        $pidList = ($processIds | ForEach-Object { $_.ToString() }) -join ', '
        Write-Host "[INFO] Stale backend PID(s): $pidList - terminating (pass $pass/$MaxPasses)..." -ForegroundColor Yellow

        Stop-ProcessTrees -ProcessIds $processIds -Label 'backend'
        Sync-PidFile -PidFilePath $backendPidFile -ProcessIds @()

        Start-Sleep -Milliseconds 1000
    }

    $remaining = Get-ListeningProcessIds -Port 8000
    if ($remaining.Count -gt 0) {
        $remainingList = ($remaining | ForEach-Object { $_.ToString() }) -join ', '
        Write-Err "Port 8000 is still occupied by PID(s): $remainingList"
        Read-Host "Close manually and press Enter to exit"
        exit 1
    }

    Sync-PidFile -PidFilePath $backendPidFile -ProcessIds @()
    Write-Status 'Port 8000 released'
}

Write-Host ''
Write-Host '  ========================================'
Write-Host '    AI Novel Platform - Smart Launcher'
Write-Host '  ========================================'
Write-Host ''

# 1. Check files
if (-not (Test-Path (Join-Path $BACKEND_DIR 'run.py'))) {
    Write-Err 'Cannot find backend\run.py'
    Read-Host 'Press Enter to exit'
    exit 1
}
if (-not (Test-Path (Join-Path $FRONTEND_DIR 'package.json'))) {
    Write-Err 'Cannot find frontend\package.json'
    Read-Host 'Press Enter to exit'
    exit 1
}
Write-Status 'Project files checked'

# 2. Check and handle backend port/processes
Stop-BackendProcesses

# 2a. Check frontend port
$frontendPort = (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue).Count
if ($frontendPort -gt 0) {
    Write-Err 'Port 5173 is in use - frontend may already be running'
    Read-Host 'Press Enter to exit'
    exit 1
}
Write-Status 'Port check passed'

# 3. Start backend
Write-Host ''
Write-Status 'Starting backend service...'

$backendProc = Start-Process python -WorkingDirectory $BACKEND_DIR -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000' -PassThru -WindowStyle Normal
$backendProc.Id | Out-File -FilePath (Join-Path $BACKEND_DIR 'app.pid') -Encoding ascii
Start-Sleep 1

Write-Status 'Waiting for backend (max 30s)...'
$backendOk = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "$BACKEND_URL/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) {
            $backendOk = $true
            break
        }
    } catch {}
    Start-Sleep 1
}

if (-not $backendOk) {
    Write-Err 'Backend startup timeout'
    Read-Host 'Press Enter to exit'
    exit 1
}
Write-OK 'Backend ready' $BACKEND_URL

# 4. Start frontend
Write-Host ''
Write-Status 'Starting frontend service...'

$frontendProc = Start-Process cmd -ArgumentList '/k', 'npm', 'run', 'dev' -WorkingDirectory $FRONTEND_DIR -PassThru -WindowStyle Normal
$frontendProc.Id | Out-File -FilePath (Join-Path $FRONTEND_DIR 'app.pid') -Encoding ascii
Start-Sleep 1

Write-Status 'Waiting for frontend (max 30s)...'
$frontendOk = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "$FRONTEND_URL/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) {
            $frontendOk = $true
            break
        }
    } catch {}
    Start-Sleep 1
}

if (-not $frontendOk) {
    Write-Err 'Frontend startup timeout'
    Read-Host 'Press Enter to exit'
    exit 1
}
Write-OK 'Frontend ready' $FRONTEND_URL

# 5. Done
Write-Host ''
Write-Host '  ========================================'
Write-OK 'All services started successfully!'
Write-Host '  ========================================'
Write-Host ''
Write-Host '    Backend:' $BACKEND_URL
Write-Host '    Frontend:' $FRONTEND_URL
Write-Host ''

Start-Process $FRONTEND_URL
Write-Status 'Browser opened'
Write-Host ''
Write-Host 'Tip: Run [stop.bat] to stop services'
Write-Host ''
