# Ticketradar – Installer für Windows (PowerShell)
# Lädt das Radar herunter, installiert Python (falls nötig) und Abhängigkeiten,
# schickt einen Test-Push und richtet den automatischen Lauf per Aufgabenplanung ein.
# Aufruf (PowerShell): irm https://raw.githubusercontent.com/mikeschneider666/Claude-code/refs/heads/claude/electric-call-boy-ticket-radar-hze1ul/ticketradar/install-windows.ps1 | iex
$ErrorActionPreference = "Stop"
$Branch = "claude/electric-call-boy-ticket-radar-hze1ul"
$Zip = "https://github.com/mikeschneider666/Claude-code/archive/refs/heads/$Branch.zip"
$Dir = Join-Path $env:USERPROFILE "Ticketradar"
$IntervalMinutes = 15   # Suchintervall in Minuten

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
}

Write-Host "`n[1/5] Python prüfen ..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py -or (& python --version 2>&1) -notmatch "Python 3") {
  Write-Host "Python fehlt – Installation über winget ..."
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
  Refresh-Path
}
$python = (Get-Command python).Source
Write-Host "Python: $python ($(& python --version))"

Write-Host "`n[2/5] Radar herunterladen ..." -ForegroundColor Cyan
$tmpZip = Join-Path $env:TEMP "ticketradar.zip"
$tmpDir = Join-Path $env:TEMP "ticketradar-src"
Invoke-WebRequest -Uri $Zip -OutFile $tmpZip -UseBasicParsing
if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force
$src = Get-ChildItem $tmpDir -Directory | Select-Object -First 1
$srcRadar = Join-Path $src.FullName "ticketradar"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
Get-ChildItem $srcRadar | Where-Object { $_.Name -ne "state" } | Copy-Item -Destination $Dir -Recurse -Force
if (-not (Test-Path (Join-Path $Dir "state\seen.json"))) {
  Copy-Item (Join-Path $srcRadar "state") (Join-Path $Dir "state") -Recurse -Force
}
Write-Host "Installiert nach $Dir"

Write-Host "`n[3/5] Abhängigkeiten installieren ..." -ForegroundColor Cyan
& $python -m pip install -q --upgrade pip
& $python -m pip install -q -r (Join-Path $Dir "requirements.txt")

Write-Host "`n[4/5] Test: Push aufs Handy und erster Suchlauf ..." -ForegroundColor Cyan
& $python (Join-Path $Dir "ticketradar.py") --test-push
& $python (Join-Path $Dir "ticketradar.py") --dry-run --print | Select-Object -Last 25

Write-Host "`n[5/5] Automatischen Lauf alle $IntervalMinutes Minuten einrichten ..." -ForegroundColor Cyan
$action  = New-ScheduledTaskAction -Execute $python -Argument "`"$(Join-Path $Dir 'ticketradar.py')`"" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "Ticketradar" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "`nFertig. Das Radar läuft jetzt alle $IntervalMinutes Minuten, solange der Rechner an ist." -ForegroundColor Green
Write-Host "Protokoll: $Dir\state\radar.log"
Write-Host "Stoppen:   Unregister-ScheduledTask -TaskName Ticketradar -Confirm:`$false"
