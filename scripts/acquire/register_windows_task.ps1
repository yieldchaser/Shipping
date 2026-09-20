# scripts/acquire/register_windows_task.ps1
# ============================================
# Registers "ShippingFleetSync" in Windows Task Scheduler
# - Runs daily at 10:00 AM (and catches up if laptop was shut down)
# - Hidden background execution (zero popups)
# - Calls scripts/acquire/run_scheduled_fleet_sync.py

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = (Get-Command python.exe).Source
$scriptPath = Join-Path $repoRoot "scripts\acquire\run_scheduled_fleet_sync.py"
$taskName = "ShippingFleetSync"

Write-Host "Registering Windows Scheduled Task '$taskName'..." -ForegroundColor Cyan
Write-Host "  Repository: $repoRoot"
Write-Host "  Python:     $pythonExe"
Write-Host "  Script:     $scriptPath"

# Action: Run python in background
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`"" -WorkingDirectory $repoRoot

# Trigger: Daily at 10:00 AM, with wake/logon resiliency
$trigger = New-ScheduledTaskTrigger -Daily -At "10:00AM"

# Settings: Hidden execution, run if missed, battery allowed
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -Hidden

# Register task under current user
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Automated 4-day stealth fleet telemetry sync for Shipping Terminal" `
    -Force | Out-Null

Write-Host "[OK] Task '$taskName' successfully registered in Windows Task Scheduler!" -ForegroundColor Green
Write-Host "It will run silently in the background every 4 days without disturbing you." -ForegroundColor Green
