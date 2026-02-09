# ops/promote_latest.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Resolve-Python {
  $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "python.exe not found (neither .venv nor PATH)."
}

function Is-MonthEnd([datetime]$d) {
  return $d.Date -eq (Get-Date $d.Year $d.Month 1).AddMonths(1).AddDays(-1).Date
}

$Py = Resolve-Python
$now = Get-Date
$startUtc = $now.ToUniversalTime()

# Collision gate: if today is Friday AND month-end -> skip promote (monthly job owns the heavy run)
if ($now.DayOfWeek -eq "Friday" -and (Is-MonthEnd $now)) {
  Write-Host "[promote] month-end Friday collision -> SKIP Friday promote (monthly job only)."
  exit 0
}

Write-Host "[promote] startUtc=$startUtc repo=$RepoRoot"

# Run acceptance promotion (this must refresh output/latest)
& $Py "scripts/run_acceptance_latest.py"
if ($LASTEXITCODE -ne 0) { throw "run_acceptance_latest.py failed with exit code $LASTEXITCODE" }

# Required verification gates
$latestDir = Join-Path $RepoRoot "output\latest"
$db = Join-Path $latestDir "radar.db"
$eval = Join-Path $latestDir "reports\eval_quality.json"
$accReportsDir = Join-Path $RepoRoot "output\reports"

if (!(Test-Path $db)) { throw "Gate failed: radar.db missing at $db" }
$dash = Get-ChildItem -Path $latestDir -Filter "dashboard*.html" -ErrorAction SilentlyContinue
if (!$dash -or $dash.Count -lt 1) { throw "Gate failed: dashboard*.html missing in $latestDir" }
if (!(Test-Path $eval)) { throw "Gate failed: eval_quality.json missing at $eval" }

# eval_quality.json contains boolean ok == true
$evalJson = Get-Content $eval -Raw | ConvertFrom-Json
if (($null -eq $evalJson.ok) -or ($evalJson.ok -isnot [bool]) -or ($evalJson.ok -ne $true)) {
  throw "Gate failed: eval_quality.json ok must be boolean true"
}

# Anti-fake-success gate: radar.db LastWriteTimeUtc >= startUtc
$dbItem = Get-Item $db
if ($dbItem.LastWriteTimeUtc -lt $startUtc) {
  throw "Anti-fake gate failed: radar.db not refreshed (LastWriteTimeUtc=$($dbItem.LastWriteTimeUtc), startUtc=$startUtc)"
}

# New acceptance summary exists after startUtc: newest acceptance_latest_*.json must be fresh
$acc = Get-ChildItem -Path $accReportsDir -Filter "acceptance_latest_*.json" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTimeUtc -Descending |
  Select-Object -First 1

if (!$acc) { throw "Anti-fake gate failed: no acceptance_latest_*.json under $accReportsDir" }
if ($acc.LastWriteTimeUtc -lt $startUtc) {
  throw "Anti-fake gate failed: acceptance_latest report not fresh (LastWriteTimeUtc=$($acc.LastWriteTimeUtc), startUtc=$startUtc)"
}

Write-Host "[promote] OK: latest refreshed + gates passed"
exit 0

Set-Location C:\dev\civilization-radar
.\.venv\Scripts\python.exe scripts/run_acceptance_latest.py
Start-Process "C:\dev\civilization-radar\output\latest\dashboard_v04.html"
