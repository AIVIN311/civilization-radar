[CmdletBinding()]
param(
  [switch]$ForceMonthEnd,
  [switch]$SkipTagPush
)

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

function Test-MonthEnd([datetime]$d) {
  $firstDay = Get-Date -Year $d.Year -Month $d.Month -Day 1
  return $d.Date -eq $firstDay.AddMonths(1).AddDays(-1).Date
}

function Ensure-Dir([string]$Path) {
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Remove-Tree([string]$Path) {
  if (Test-Path $Path) {
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
}

function Write-Receipt([string]$Path, [hashtable]$Receipt) {
  $Receipt["updated_utc"] = (Get-Date).ToUniversalTime().ToString("o")
  $json = $Receipt | ConvertTo-Json -Depth 8
  Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Invoke-Step([string]$Py, [string[]]$CommandArgs, [string]$Name) {
  & $Py @CommandArgs
  if ($LASTEXITCODE -ne 0) { throw "$Name failed" }
}

function Promote-ToLatest([string]$SourceDir, [string]$LatestDir, [string]$TmpRoot, [string]$Stamp) {
  $backup = Join-Path $TmpRoot "latest_bak_$Stamp"
  Remove-Tree $backup

  $movedOld = $false
  if (Test-Path $LatestDir) {
    try {
      Move-Item -LiteralPath $LatestDir -Destination $backup
      $movedOld = $true
    } catch {
      Remove-Tree $LatestDir
    }
  }

  try {
    Move-Item -LiteralPath $SourceDir -Destination $LatestDir
  } catch {
    if ($movedOld -and (Test-Path $backup) -and !(Test-Path $LatestDir)) {
      Move-Item -LiteralPath $backup -Destination $LatestDir
    }
    throw
  }

  if ($movedOld -and (Test-Path $backup)) {
    Remove-Tree $backup
  }
}

function Canonicalize-EvalQuality([string]$EvalPath, [string]$DbPath) {
  if (!(Test-Path $EvalPath)) { return }
  $payload = Get-Content -LiteralPath $EvalPath -Raw | ConvertFrom-Json
  if ($null -eq $payload.db_path) {
    $payload | Add-Member -NotePropertyName "db_path" -NotePropertyValue $DbPath
  } else {
    $payload.db_path = $DbPath
  }
  $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvalPath -Encoding UTF8
}

$Py = Resolve-Python
$now = Get-Date
$isMonthEnd = Test-MonthEnd $now

if ((!$isMonthEnd) -and (-not $ForceMonthEnd)) {
  Write-Host "[month-end] not month-end -> no-op"
  exit 0
}

$outputRoot = Join-Path $RepoRoot "output"
$reportsDir = Join-Path $outputRoot "reports"
$tmpRoot = Join-Path $outputRoot "tmp"
$latestDir = Join-Path $outputRoot "latest"
$inputSnapshots = Join-Path $RepoRoot "input\snapshots.jsonl"
$stamp = $now.ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$runDir = Join-Path $tmpRoot "month_end_run_$stamp"
$receiptPath = Join-Path $reportsDir "month_end_$stamp.json"
$tag = "radar-release-{0:yyyyMM}" -f $now
$msg = "Monthly release {0:yyyy-MM}" -f $now

Ensure-Dir $outputRoot
Ensure-Dir $reportsDir
Ensure-Dir $tmpRoot
Remove-Tree $runDir
Ensure-Dir $runDir

$receipt = [ordered]@{
  generated_utc = $now.ToUniversalTime().ToString("o")
  repo_root = $RepoRoot
  output_root = $outputRoot
  staging_dir = $runDir
  latest_dir = $latestDir
  receipt_path = $receiptPath
  forced = [bool]$ForceMonthEnd
  skip_tag_push = [bool]$SkipTagPush
  month_end_eligible = [bool]$isMonthEnd
  status = "starting"
  input_path = $inputSnapshots
  input_exists = [bool](Test-Path $inputSnapshots)
  input_mtime_utc = $null
  input_sha256 = $null
  eval_path = $null
  eval_monthly_path = $null
  eval_ok = $false
  critical_failed = @()
  promoted_latest = $false
  tag_name = $tag
  tag_created = $false
  tag_pushed = $false
  tag_action = "pending"
  error = $null
}

if (Test-Path $inputSnapshots) {
  $inputItem = Get-Item -LiteralPath $inputSnapshots
  $receipt["input_mtime_utc"] = $inputItem.LastWriteTimeUtc.ToString("o")
  $receipt["input_sha256"] = (Get-FileHash -Path $inputSnapshots -Algorithm SHA256).Hash.ToLower()
}

Write-Receipt $receiptPath $receipt

try {
  if (!(Test-Path $inputSnapshots)) {
    throw "input snapshots missing: $inputSnapshots"
  }

  Write-Host "[month-end] RUN full pipeline once -> staging ($runDir)"

  Invoke-Step -Py $Py -CommandArgs @("scripts/apply_sql_migrations.py", "--output-dir", $runDir) -Name "apply_sql_migrations"
  Invoke-Step -Py $Py -CommandArgs @("seed_from_snapshots.py", "--input", $inputSnapshots, "--output-dir", $runDir) -Name "seed_from_snapshots"
  Invoke-Step -Py $Py -CommandArgs @("upgrade_to_v02.py", "--output-dir", $runDir) -Name "upgrade_to_v02"
  Invoke-Step -Py $Py -CommandArgs @("scripts/derive_events_from_daily.py", "--input", $inputSnapshots, "--output-dir", $runDir) -Name "derive_events_from_daily"
  Invoke-Step -Py $Py -CommandArgs @("scripts/load_events_into_db.py", "--output-dir", $runDir) -Name "load_events_into_db"
  Invoke-Step -Py $Py -CommandArgs @("build_chain_matrix_v10.py", "--half-life-days", "7", "--output-dir", $runDir) -Name "build_chain_matrix_v10"
  Invoke-Step -Py $Py -CommandArgs @("upgrade_to_v03_chain.py", "--output-dir", $runDir) -Name "upgrade_to_v03_chain"
  Invoke-Step -Py $Py -CommandArgs @("render_dashboard_v02.py", "--half-life-days", "7", "--output-dir", $runDir) -Name "render_dashboard_v02"
  Invoke-Step -Py $Py -CommandArgs @("scripts/eval_quality.py", "--output-dir", $runDir) -Name "eval_quality"

  $eval = Join-Path $runDir "reports\eval_quality.json"
  if (!(Test-Path $eval)) { throw "eval_quality.json missing: $eval" }

  $evalMonthly = Join-Path $runDir "reports\eval_quality_monthly.json"
  Copy-Item -Force -LiteralPath $eval -Destination $evalMonthly

  $evalJson = Get-Content -LiteralPath $evalMonthly -Raw | ConvertFrom-Json
  $receipt["eval_path"] = $eval
  $receipt["eval_monthly_path"] = $evalMonthly
  $receipt["eval_ok"] = [bool]$evalJson.ok
  $receipt["critical_failed"] = @($evalJson.critical_failed)
  $receipt["status"] = "gated"
  Write-Receipt $receiptPath $receipt

  if (($null -eq $evalJson.ok) -or ($evalJson.ok -isnot [bool]) -or ($evalJson.ok -ne $true)) {
    throw "monthly gate failed: eval_quality_monthly.json ok must be boolean true"
  }

  Promote-ToLatest $runDir $latestDir $tmpRoot $stamp
  $latestDb = Join-Path $latestDir "radar.db"
  Canonicalize-EvalQuality -EvalPath (Join-Path $latestDir "reports\eval_quality.json") -DbPath $latestDb
  Canonicalize-EvalQuality -EvalPath (Join-Path $latestDir "reports\eval_quality_monthly.json") -DbPath $latestDb
  $receipt["promoted_latest"] = $true
  $receipt["eval_path"] = Join-Path $latestDir "reports\eval_quality.json"
  $receipt["eval_monthly_path"] = Join-Path $latestDir "reports\eval_quality_monthly.json"
  $receipt["status"] = "promoted"
  Write-Receipt $receiptPath $receipt

  if ($SkipTagPush) {
    $receipt["tag_action"] = "skipped_by_flag"
    $receipt["status"] = "success_no_push"
    Write-Receipt $receiptPath $receipt
    Write-Host "[month-end] OK: gated + promoted latest (tag push skipped by flag)"
    exit 0
  }

  $existing = & git tag -l $tag
  if ($LASTEXITCODE -ne 0) { throw "git tag lookup failed" }
  if ($existing -and $existing.Trim() -eq $tag) {
    $receipt["tag_action"] = "already_exists"
    $receipt["status"] = "success_tag_exists"
    Write-Receipt $receiptPath $receipt
    Write-Host "[month-end] tag exists -> skip create/push ($tag)"
    exit 0
  }

  & git tag -a $tag -m $msg
  if ($LASTEXITCODE -ne 0) { throw "git tag failed" }
  $receipt["tag_created"] = $true
  $receipt["tag_action"] = "created"
  $receipt["status"] = "tag_created"
  Write-Receipt $receiptPath $receipt

  & git push origin $tag
  if ($LASTEXITCODE -ne 0) { throw "git push tag failed" }
  $receipt["tag_pushed"] = $true
  $receipt["tag_action"] = "pushed"
  $receipt["status"] = "success"
  Write-Receipt $receiptPath $receipt

  Write-Host "[month-end] OK: pipeline + monthly quality + tag pushed ($tag)"
  exit 0
} catch {
  $receipt["error"] = $_.Exception.Message
  if ($receipt["status"] -eq "starting") {
    $receipt["status"] = "failed"
  } elseif ($receipt["status"] -eq "gated") {
    $receipt["status"] = "failed_after_gate"
  } elseif ($receipt["status"] -eq "promoted") {
    $receipt["status"] = "failed_after_promote"
  } elseif ($receipt["status"] -eq "tag_created") {
    $receipt["status"] = "failed_tag_push"
  }
  Write-Receipt $receiptPath $receipt
  throw
}
