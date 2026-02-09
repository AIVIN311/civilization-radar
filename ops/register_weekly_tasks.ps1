# ops/register_weekly_tasks.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$me = "$env:USERDOMAIN\$env:USERNAME"

$collect = (Resolve-Path (Join-Path $PSScriptRoot "collect_snapshots_weekday.ps1")).Path
$promote = (Resolve-Path (Join-Path $PSScriptRoot "promote_latest.ps1")).Path
$monthly = (Resolve-Path (Join-Path $PSScriptRoot "month_end_release.ps1")).Path

function Create-Task($name, $scheduleArgs, $scriptPath) {
  $ps = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
  $cmd = @(
    "schtasks", "/Create", "/F",
    "/TN", $name,
    "/TR", $ps,
    "/RU", $me, "/IT"
  ) + $scheduleArgs

  Write-Host "[register] $name -> $scriptPath"
  & $cmd
  if ($LASTEXITCODE -ne 0) { throw "schtasks create failed: $name" }
}

# Schedules (host local time; ensure Windows timezone = Asia/Taipei)
Create-Task "CivilizationRadar-WeekdaySnapshots" @("/SC","WEEKLY","/D","MON,TUE,WED,THU","/ST","18:00") $collect
Create-Task "CivilizationRadar-FridayPromote"     @("/SC","WEEKLY","/D","FRI","/ST","18:00")          $promote
Create-Task "CivilizationRadar-MonthEndPipelineTag" @("/SC","DAILY","/ST","19:00")                  $monthly

Write-Host "[register] OK: 3 tasks created/updated as $me (interactive)"
exit 0
