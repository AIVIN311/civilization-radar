# ops/register_weekly_tasks.ps1
param(
  [string]$RepoRoot = (Join-Path $PSScriptRoot "..")
)

$ErrorActionPreference = "Stop"

try {
  $RepoRoot = (Resolve-Path -Path $RepoRoot).Path
} catch {
  throw "repo root not found: $RepoRoot"
}

$me = "$env:USERDOMAIN\$env:USERNAME"

$collect = (Resolve-Path (Join-Path $RepoRoot "ops\collect_snapshots_weekday.ps1")).Path
$promote = (Resolve-Path (Join-Path $RepoRoot "ops\promote_latest.ps1")).Path
$monthly = (Resolve-Path (Join-Path $RepoRoot "ops\month_end_release.ps1")).Path

function Create-Task($name, $scheduleArgs, $scriptPath) {
  $ps = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
  $args = @(
    "/Create", "/F",
    "/TN", $name,
    "/TR", $ps,
    "/RU", $me, "/IT"
  ) + $scheduleArgs

  $schtasks = "$env:WINDIR\System32\schtasks.exe"
  Write-Host "[register] $name -> $scriptPath"
  & $schtasks @args
  if ($LASTEXITCODE -ne 0) { throw "schtasks create failed: $name" }
}

Write-Host "[register] repo root: $RepoRoot"

# Schedules (host local time; ensure Windows timezone = Asia/Taipei)
Create-Task "CivilizationRadar-WeekdaySnapshots" @("/SC","WEEKLY","/D","MON,TUE,WED,THU","/ST","18:00") $collect
Create-Task "CivilizationRadar-FridayPromote" @("/SC","WEEKLY","/D","FRI","/ST","18:00") $promote
Create-Task "CivilizationRadar-MonthEndPipelineTag" @("/SC","DAILY","/ST","19:00") $monthly

Write-Host "[register] OK: 3 tasks created/updated as $me (interactive)"
exit 0
