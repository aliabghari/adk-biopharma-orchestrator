# PowerShell script to register the Biopharma Risk Horizon Radar task in Windows Task Scheduler
# Requires Administrator privileges to run.

# 1. Check for Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Error "CRITICAL: This script must be run as an Administrator to configure Windows Task Scheduler."
    Write-Host "Please close this shell, open a new PowerShell window as Administrator (Right click -> Run as Administrator), and try again." -ForegroundColor Red
    Exit 1
}

# 2. Define directory paths
$WorkingDir = $PSScriptRoot
$ScriptPath = Join-Path $WorkingDir "radar.py"
$TaskName = "BiopharmaRiskHorizonRadar"

Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Configuring Daily Windows Task Scheduler automation for Radar" -ForegroundColor Cyan
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan

# 3. Locate Python executable path
$PythonPath = Join-Path $WorkingDir ".venv\Scripts\python.exe"
if (Test-Path $PythonPath) {
    Write-Host "Found local virtual environment Python: $PythonPath" -ForegroundColor Green
} else {
    Write-Host "Local virtual environment python.exe not found. Searching system..." -ForegroundColor Yellow
    $PythonPath = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $PythonPath) {
        Write-Host "Warning: 'python.exe' was not found on your current PATH variable." -ForegroundColor Yellow
        Write-Host "Looking in typical Windows installation paths..." -ForegroundColor Yellow
        
        # Common path pattern for User-level Windows Python installs
        $commonPath = Join-Path $env:LOCALAPPDATA "Programs\Python"
        if (Test-Path $commonPath) {
            $pythonFolders = Get-ChildItem $commonPath -Filter "Python*" | Sort-Object Name -Descending
            if ($pythonFolders) {
                $PythonPath = Join-Path $pythonFolders[0].FullName "python.exe"
            }
        }
    }

    if (-not $PythonPath -or -not (Test-Path $PythonPath)) {
        # Final fallback: ask user or write warning
        $PythonPath = "python"
        Write-Warning "Could not pinpoint absolute path to python.exe. Defaulting to system command 'python'."
    } else {
        Write-Host "Pinpointed Python executable at: $PythonPath" -ForegroundColor Green
    }
}

# 4. Define Action, Trigger, and Settings
Write-Host "Setting up Scheduled Task actions & trigger (8:00 AM daily)..." -ForegroundColor Yellow

$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument """$ScriptPath"" --once" -WorkingDirectory $WorkingDir
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM

# Allow starting even on battery power
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 5. Register the scheduled task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Automated daily scrape and biopharma risk alert report dispatch." -Force -ErrorAction Stop
    Write-Host "`nSUCCESS: Scheduled task '$TaskName' has been registered." -ForegroundColor Green
    Write-Host "It will run daily at 8:00 AM starting tomorrow." -ForegroundColor Green
    Write-Host "You can inspect it in Windows Task Scheduler under task name '$TaskName'." -ForegroundColor Green
} catch {
    Write-Error "Failed to register scheduled task: $_"
    Exit 1
}
