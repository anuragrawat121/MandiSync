<#
.SYNOPSIS
  Free public demo URLs via Cloudflare quick tunnels (no account required).

.NOTES
  1. Start Docker stack first:
       docker compose -f docker-compose.prod.yml --env-file .env.production up -d
  2. Run this script. It prints two trycloudflare.com URLs.
  3. Rebuild the web image with NEXT_PUBLIC_API_BASE_URL=<api tunnel>
     then restart the web container.
  Keep this window open — closing it kills the tunnels.
#>

$ErrorActionPreference = "Stop"
$cloudflared = Join-Path $env:LOCALAPPDATA "cloudflared\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    throw "cloudflared not found at $cloudflared. Download it first."
}

$logDir = Join-Path $PSScriptRoot "..\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$apiLog = Join-Path $logDir "cloudflared-api.log"
$webLog = Join-Path $logDir "cloudflared-web.log"

function Start-Tunnel([string]$url, [string]$logFile) {
    $outFile = "$logFile.out"
    if (Test-Path $logFile) { Remove-Item $logFile -Force }
    if (Test-Path $outFile) { Remove-Item $outFile -Force }
    Start-Process -FilePath $cloudflared -ArgumentList @(
        "tunnel", "--url", $url, "--no-autoupdate"
    ) -RedirectStandardError $logFile -RedirectStandardOutput $outFile -WindowStyle Hidden | Out-Null
}

function Wait-TunnelUrl([string]$logFile, [int]$seconds = 90) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $logFile) {
            $text = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
            if ($text -match "https://[a-z0-9-]+\.trycloudflare\.com") {
                return $Matches[0]
            }
        }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for tunnel URL in $logFile"
}

Write-Host "Starting Cloudflare quick tunnels..."
Start-Tunnel "http://127.0.0.1:8000" $apiLog
Start-Tunnel "http://127.0.0.1:3000" $webLog

$apiUrl = Wait-TunnelUrl $apiLog
$webUrl = Wait-TunnelUrl $webLog

Write-Host ""
Write-Host "=============================================="
Write-Host " MandiSync public demo (PC must stay awake)"
Write-Host "=============================================="
Write-Host " Farmer UI : $webUrl"
Write-Host " Admin     : $webUrl/admin"
Write-Host " API       : $apiUrl"
Write-Host ""
Write-Host "Next: rebuild the UI so the browser calls the public API:"
Write-Host "  `$env:NEXT_PUBLIC_API_BASE_URL='$apiUrl'"
Write-Host "  docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build web"
Write-Host "=============================================="
Write-Host ""
Write-Host "Leave this window open. Press Ctrl+C to stop tunnels."

# Keep script alive so the user has a clear "tunnels running" process.
try {
    while ($true) { Start-Sleep -Seconds 60 }
} finally {
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
}
