param(
  [switch]$CleanNestedVenv,
  [switch]$Reinstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run from script directory
Set-Location -Path $PSScriptRoot

Write-Host "[QA_FAST] 1) Starting Postgres (docker compose up -d) ..."
docker compose up -d

Write-Host "[QA_FAST] 2) Ensuring Python venv and dependencies ..."

if ($Reinstall -and (Test-Path ".\.venv")) {
  Write-Host "[QA_FAST] Reinstall flag set. Removing existing .venv ..."
  Remove-Item -Recurse -Force ".\.venv"
}

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
  py -3 -m venv .venv
}

# Warn or cleanup nested venvs that can cause confusion
$nested = @()
if (Test-Path ".\pub\.venv") { $nested += "pub\\.venv" }
if (Test-Path ".\sub\.venv") { $nested += "sub\\.venv" }
if ($nested.Count -gt 0) {
  Write-Warning "Nested venvs detected: $($nested -join ', '). This script uses the root .venv."
  if ($CleanNestedVenv) {
    foreach ($n in $nested) { Remove-Item -Recurse -Force (Join-Path $PSScriptRoot $n) }
    Write-Host "[QA_FAST] Removed nested venvs."
  }
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $PSScriptRoot "pub\requirements.txt")
& $py -m pip install -r (Join-Path $PSScriptRoot "sub\requirements.txt")

# Base environment
$dbUrl = "postgresql+psycopg://postgres:postgres@localhost:5433/qa_fast"
$env:DATABASE_URL = $dbUrl
$env:SUB_BASE_URL = "http://127.0.0.1:8001"

Write-Host "[QA_FAST] 3) Launching SUB(8001) and PUB(8000) in new PowerShell windows ..."

$subCmd = @"
`$env:DATABASE_URL = '$dbUrl'
& '$py' -m uvicorn app.main:app --app-dir sub --host 0.0.0.0 --port 8001 --reload
"@
Start-Process -FilePath "powershell" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$subCmd | Out-Null

$pubCmd = @"
`$env:DATABASE_URL = '$dbUrl'
`$env:SUB_BASE_URL = 'http://127.0.0.1:8001'
& '$py' -m uvicorn app.main:app --app-dir pub --host 0.0.0.0 --port 8000 --reload
"@
Start-Process -FilePath "powershell" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$pubCmd | Out-Null

Write-Host "[QA_FAST] Done."
Write-Host " - SUB health:  http://127.0.0.1:8001/healthz"
Write-Host " - PUB docs:    http://127.0.0.1:8000/swagger"


