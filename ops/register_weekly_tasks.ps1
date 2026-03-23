# ops/register_weekly_tasks.ps1
param(
  [string]$RepoRoot = (Join-Path $PSScriptRoot ".."),
  [switch]$InteractiveOnly
)

$ErrorActionPreference = "Stop"

try {
  $RepoRoot = (Resolve-Path -Path $RepoRoot).Path
} catch {
  throw "repo root not found: $RepoRoot"
}

$me = "$env:USERDOMAIN\$env:USERNAME"
$schtasks = "$env:WINDIR\System32\schtasks.exe"

$collect = (Resolve-Path (Join-Path $RepoRoot "ops\collect_snapshots_weekday.ps1")).Path
$promote = (Resolve-Path (Join-Path $RepoRoot "ops\promote_latest.ps1")).Path
$monthly = (Resolve-Path (Join-Path $RepoRoot "ops\month_end_release.ps1")).Path

$taskSpecs = @(
  @{
    Name = "CivilizationRadar-WeekdaySnapshots"
    ScheduleArgs = @("/SC","WEEKLY","/D","MON,TUE,WED,THU","/ST","18:00")
    ScriptPath = $collect
  },
  @{
    Name = "CivilizationRadar-FridayPromote"
    ScheduleArgs = @("/SC","WEEKLY","/D","FRI","/ST","18:00")
    ScriptPath = $promote
  },
  @{
    Name = "CivilizationRadar-MonthEndPipelineTag"
    ScheduleArgs = @("/SC","DAILY","/ST","19:00")
    ScriptPath = $monthly
  }
)

function ConvertTo-PlainText([Security.SecureString]$SecureString) {
  if ($null -eq $SecureString) {
    throw "secure password is required"
  }

  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    if ($bstr -ne [IntPtr]::Zero) {
      [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
  }
}

function Get-RegistrationPassword([string]$UserName) {
  Write-Host "[register] mode: same-user non-interactive"
  Write-Host "[register] Password entry is a one-time registration cost."
  Write-Host "[register] Scheduled runs should execute non-interactively after registration."
  Write-Host "[register] Missed schedules should catch up once the host becomes available again."
  Write-Host "[register] WakeToRun remains disabled in this slice."
  Write-Host "[register] This preserves the existing user environment for month-end git push and credentials."

  $secure = Read-Host -AsSecureString "Enter the Windows password for $UserName"
  $plain = ConvertTo-PlainText $secure
  if ([string]::IsNullOrWhiteSpace($plain)) {
    throw "password cannot be blank"
  }
  return $plain
}

function Create-Task($TaskSpec, [string]$PlainPassword) {
  $ps = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$($TaskSpec.ScriptPath)`""
  $args = @(
    "/Create", "/F",
    "/TN", $TaskSpec.Name,
    "/TR", $ps,
    "/RU", $me
  )

  if ($InteractiveOnly) {
    $args += "/IT"
  } else {
    $args += @("/RP", $PlainPassword)
  }

  $args += $TaskSpec.ScheduleArgs

  Write-Host "[register] $($TaskSpec.Name) -> $($TaskSpec.ScriptPath)"
  & $schtasks @args
  if ($LASTEXITCODE -ne 0) {
    throw "schtasks create failed: $($TaskSpec.Name)"
  }
}

function Enable-TaskStartWhenAvailable($TaskSpec, [string]$PlainPassword) {
  $xmlText = & $schtasks "/Query" "/TN" $TaskSpec.Name "/XML"
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($xmlText)) {
    throw "schtasks query xml failed: $($TaskSpec.Name)"
  }

  [xml]$taskXml = $xmlText
  $nsUri = $taskXml.Task.NamespaceURI
  $ns = New-Object System.Xml.XmlNamespaceManager($taskXml.NameTable)
  $ns.AddNamespace("t", $nsUri)

  $settingsNode = $taskXml.SelectSingleNode("/t:Task/t:Settings", $ns)
  if ($null -eq $settingsNode) {
    throw "task xml missing Settings node: $($TaskSpec.Name)"
  }

  $startNode = $taskXml.SelectSingleNode("/t:Task/t:Settings/t:StartWhenAvailable", $ns)
  if ($null -eq $startNode) {
    $startNode = $taskXml.CreateElement("StartWhenAvailable", $nsUri)
    $startNode.InnerText = "true"

    $insertAfter = $taskXml.SelectSingleNode("/t:Task/t:Settings/t:StopIfGoingOnBatteries", $ns)
    if ($null -ne $insertAfter) {
      $null = $settingsNode.InsertAfter($startNode, $insertAfter)
    } else {
      $insertBefore = $taskXml.SelectSingleNode("/t:Task/t:Settings/t:IdleSettings", $ns)
      if ($null -ne $insertBefore) {
        $null = $settingsNode.InsertBefore($startNode, $insertBefore)
      } else {
        $null = $settingsNode.AppendChild($startNode)
      }
    }
  } else {
    $startNode.InnerText = "true"
  }

  $tempXml = Join-Path $env:TEMP ("{0}-{1}.xml" -f $TaskSpec.Name, [Guid]::NewGuid().ToString("N"))
  try {
    $taskXml.Save($tempXml)

    $args = @(
      "/Create", "/F",
      "/TN", $TaskSpec.Name,
      "/XML", $tempXml,
      "/RU", $me,
      "/RP", $PlainPassword
    )

    Write-Host "[register] enabling StartWhenAvailable for $($TaskSpec.Name)"
    & $schtasks @args
    if ($LASTEXITCODE -ne 0) {
      throw "schtasks xml import failed: $($TaskSpec.Name)"
    }
  } finally {
    if (Test-Path $tempXml) {
      Remove-Item -Path $tempXml -Force -ErrorAction SilentlyContinue
    }
  }
}

function Register-TaskSet([string]$PlainPassword) {
  foreach ($taskSpec in $taskSpecs) {
    Create-Task $taskSpec $PlainPassword
    if (-not $InteractiveOnly) {
      Enable-TaskStartWhenAvailable $taskSpec $PlainPassword
    }
  }
}

function Restore-InteractiveOnly {
  Write-Warning "[register] restoring previous interactive-only registration for all three tasks"
  foreach ($taskSpec in $taskSpecs) {
    $ps = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$($taskSpec.ScriptPath)`""
    $args = @(
      "/Create", "/F",
      "/TN", $taskSpec.Name,
      "/TR", $ps,
      "/RU", $me,
      "/IT"
    ) + $taskSpec.ScheduleArgs

    Write-Host "[register] rollback $($taskSpec.Name) -> $($taskSpec.ScriptPath)"
    & $schtasks @args
    if ($LASTEXITCODE -ne 0) {
      throw "rollback failed while restoring $($taskSpec.Name)"
    }
  }
}

Write-Host "[register] repo root: $RepoRoot"
Write-Host "[register] rollback command: powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\register_weekly_tasks.ps1 -InteractiveOnly"

$plainPassword = $null

try {
  if ($InteractiveOnly) {
    Write-Host "[register] mode: interactive-only rollback path"
    Register-TaskSet $null
    Write-Host "[register] OK: 3 tasks created/updated as $me (interactive only)"
    exit 0
  }

  $plainPassword = Get-RegistrationPassword $me

  try {
    Register-TaskSet $plainPassword
  } catch {
    $registrationError = $_
    try {
      Restore-InteractiveOnly
    } catch {
      throw "non-interactive registration failed and rollback also failed. Run '.\ops\register_weekly_tasks.ps1 -InteractiveOnly' to restore interactive-only mode. Original error: $registrationError. Rollback error: $_"
    }
    throw "non-interactive registration failed; interactive-only mode was restored to avoid mixed registration state. Original error: $registrationError"
  }

  Write-Host "[register] OK: 3 tasks created/updated as $me (non-interactive same-user mode)"
  exit 0
} finally {
  $plainPassword = $null
}
