# MandiSync — daily Agmarknet ingest runner
# Logs to Backend/logs/ingest_YYYY-MM-DD.log
# Exit code is forwarded so Task Scheduler can mark failures.

$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $BackendRoot "ingest_prices.py"))) {
    $BackendRoot = $PSScriptRoot
    if (-not (Test-Path (Join-Path $BackendRoot "ingest_prices.py"))) {
        throw "Cannot find Backend/ingest_prices.py (looked beside scripts/)."
    }
}

$LogDir = Join-Path $BackendRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("ingest_{0:yyyy-MM-dd}.log" -f (Get-Date))

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "`n===== MandiSync ingest start $stamp ====="

Set-Location $BackendRoot
$env:PYTHONUNBUFFERED = "1"

# Prefer `py -3` on Windows; fall back to `python`.
$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
    $pythonArgs = @("-3", "-u", "ingest_prices.py", "--ingest")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
    $pythonArgs = @("-u", "ingest_prices.py", "--ingest")
} else {
    Add-Content -Path $LogFile -Value "ERROR: python/py not found on PATH"
    exit 1
}

& $python @pythonArgs 2>&1 | Tee-Object -FilePath $LogFile -Append
$exitCode = $LASTEXITCODE

$stampEnd = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "===== MandiSync ingest end $stampEnd exit=$exitCode ====="
exit $exitCode
