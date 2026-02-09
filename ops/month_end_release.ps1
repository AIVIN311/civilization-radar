# ops/month_end_release.ps1
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

if (!(Is-MonthEnd $now)) {
  Write-Host "[month-end] not month-end -> no-op"
  exit 0
}

Write-Host "[month-end] RUN full pipeline once -> output/latest"

# ---- Full pipeline (assembled from your acceptance steps, but input=real snapshots) ----
$latestDir = Join-Path $RepoRoot "output\latest"
New-Item -ItemType Directory -Force -Path $latestDir | Out-Null

# 1) apply schema/views
& $Py "scripts/apply_sql_migrations.py" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "apply_sql_migrations failed" }

# 2) seed metrics from input\snapshots.jsonl (must exist)
$inputSnapshots = Join-Path $RepoRoot "input\snapshots.jsonl"
if (!(Test-Path $inputSnapshots)) { throw "input snapshots missing: $inputSnapshots" }

& $Py "seed_from_snapshots.py" "--input" $inputSnapshots "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "seed_from_snapshots failed" }

# 3) upgrade metrics views
& $Py "upgrade_to_v02.py" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "upgrade_to_v02 failed" }

# 4) derive events + load
& $Py "scripts/derive_events_from_daily.py" "--input" $inputSnapshots "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "derive_events_from_daily failed" }

& $Py "scripts/load_events_into_db.py" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "load_events_into_db failed" }

# 5) chain matrix + chain views + render dashboard
& $Py "build_chain_matrix_v10.py" "--half-life-days" "7" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "build_chain_matrix_v10 failed" }

& $Py "upgrade_to_v03_chain.py" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "upgrade_to_v03_chain failed" }

& $Py "render_dashboard_v02.py" "--half-life-days" "7" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "render_dashboard_v02 failed" }

# ---- Fixed monthly quality source ----
& $Py "scripts/eval_quality.py" "--output-dir" $latestDir
if ($LASTEXITCODE -ne 0) { throw "eval_quality failed" }

$eval = Join-Path $latestDir "reports\eval_quality.json"
if (!(Test-Path $eval)) { throw "eval_quality.json missing: $eval" }

$evalMonthly = Join-Path $latestDir "reports\eval_quality_monthly.json"
Copy-Item -Force $eval $evalMonthly

$evalJson = Get-Content $evalMonthly -Raw | ConvertFrom-Json
if (($null -eq $evalJson.ok) -or ($evalJson.ok -isnot [bool]) -or ($evalJson.ok -ne $true)) {
  throw "monthly gate failed: eval_quality_monthly.json ok must be boolean true"
}

# ---- Tag policy (idempotent) ----
$tag = "radar-release-{0:yyyyMM}" -f $now
$msg = "Monthly release {0:yyyy-MM}" -f $now

# If tag exists, skip create/push
$existing = & git tag -l $tag
if ($existing -and $existing.Trim() -eq $tag) {
  Write-Host "[month-end] tag exists -> skip create/push ($tag)"
  exit 0
}

& git tag -a $tag -m $msg
if ($LASTEXITCODE -ne 0) { throw "git tag failed" }

& git push origin $tag
if ($LASTEXITCODE -ne 0) { throw "git push tag failed" }

Write-Host "[month-end] OK: pipeline + monthly quality + tag pushed ($tag)"
exit 0
month_end_release.ps1