# Registers a Windows Scheduled Task that pulls Agmarknet prices every morning.
# Run once from an elevated PowerShell (or normal user for a current-user task):
#
#   cd Backend\scripts
#   powershell -ExecutionPolicy Bypass -File .\install_daily_ingest_task.ps1
#
# Default schedule: daily at 06:30 local time.

param(
    [string]$TaskName = "MandiSyncDailyIngest",
    [string]$Time = "06:30"
)

$ErrorActionPreference = "Stop"

$ScriptPath = Join-Path $PSScriptRoot "run_daily_ingest.ps1"
if (-not (Test-Path $ScriptPath)) {
    throw "Missing $ScriptPath"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "MandiSync: pull Agmarknet crop prices into Postgres (ingest_prices.py --ingest)" `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' daily at $Time."
Write-Host "Script: $ScriptPath"
Write-Host "Test now:  schtasks /Run /TN `"$TaskName`""
Write-Host "Remove:     Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
