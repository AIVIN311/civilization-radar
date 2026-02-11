# ops/collect_snapshots_weekday.ps1
$ErrorActionPreference = "Stop"

# Resolve repo root from this script location: <repo>\ops\collect_*.ps1
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Resolve-Python {
  $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "python.exe not found (neither .venv nor PATH)."
}

$Py = Resolve-Python

# daysBack rule:
# Monday=3 (covers Fri-Sun), Tue/Wed/Thu=1
$dow = (Get-Date).DayOfWeek
$daysBack = if ($dow -eq "Monday") { 3 } else { 1 }

# Canonical snapshot command (single source of truth):
# Writes/appends to input\snapshots.jsonl using cf_pull_daily_v2.py
$outFile = Join-Path $RepoRoot "input\snapshots.jsonl"
New-Item -ItemType Directory -Force -Path (Split-Path $outFile) | Out-Null

Write-Host "[weekday collect] repo=$RepoRoot daysBack=$daysBack out=$outFile"

# cf_pull_daily_v2.py appends by default and supports --days / --out.
& $Py "cf_pull_daily_v2.py" "--days" "$daysBack" "--out" "$outFile"
if ($LASTEXITCODE -ne 0) { throw "cf_pull_daily_v2.py failed with exit code $LASTEXITCODE" }

Write-Host "[weekday collect] OK"
exit 0
