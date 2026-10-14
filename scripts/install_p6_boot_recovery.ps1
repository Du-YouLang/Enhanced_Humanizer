param(
    [Parameter(Mandatory=$true)][string]$ConfigPath,
    [ValidateSet('Install','Status','Disable')][string]$Mode = 'Install'
)
$ErrorActionPreference = 'Stop'
$recoveryConfig = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$projectPath = [IO.Path]::GetFullPath($recoveryConfig.project)
$runtimePath = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($ConfigPath))
if (-not $runtimePath.StartsWith(($projectPath + '\.local-workbench\'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Recovery runtime must stay in the project' }
$taskName = 'Enhanced_Humanizer_P6_Boot_Recovery'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runValue = 'Enhanced_Humanizer_P6_Boot_Recovery'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$runProperties = Get-ItemProperty -LiteralPath $runKey -ErrorAction SilentlyContinue
$existingRun = if ($runProperties -and $runProperties.PSObject.Properties[$runValue]) { [string]$runProperties.$runValue } else { $null }
if ($Mode -eq 'Status') {
    [ordered]@{task_present=[bool]$task; task_state=if($task){[string]$task.State}else{'unavailable'}; user_logon_registration=[bool]$existingRun; runtime=$runtimePath} | ConvertTo-Json -Compress
    exit 0
}
if ($Mode -eq 'Disable') {
    # This marker is checked without terminating any current benchmark process.
    '{"enabled":false}' | Set-Content -LiteralPath (Join-Path $runtimePath 'enabled.private.json') -Encoding utf8
    if ($task) { Disable-ScheduledTask -TaskName $taskName | Out-Null }
    if ($existingRun) { Remove-ItemProperty -LiteralPath $runKey -Name $runValue }
    [ordered]@{status='DISABLED'; benchmark_processes_stopped=0} | ConvertTo-Json -Compress
    exit 0
}
foreach ($name in $recoveryConfig.supervisor_files.PSObject.Properties.Name) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $runtimePath $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $recoveryConfig.supervisor_files.$name) { throw 'Pinned supervisor hash differs' }
}
$scriptPath = Join-Path $runtimePath 'p6_boot_recovery.py'
$arguments = '"' + $scriptPath + '" supervise --config "' + [IO.Path]::GetFullPath($ConfigPath) + '" --execute'
$pythonPath = [string]$recoveryConfig.python
$pythonWindowless = Join-Path ([IO.Path]::GetDirectoryName($pythonPath)) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless)) { throw 'Windowless Python is required for local startup' }
$registration = 'TASK_SCHEDULER_USER_LOGON'
try {
    if ($task -or $existingRun) { throw 'Existing recovery registration must not be silently replaced' }
    $action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument $arguments -WorkingDirectory $projectPath
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
    $trigger.Delay = 'PT30S'
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Resume only this authorized local P6 batch after restart; never replay completed or ambiguous model calls.' -ErrorAction Stop | Out-Null
    $verifiedTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $verifiedTask -or $verifiedTask.Actions.Execute -ne $pythonWindowless -or $verifiedTask.Actions.Arguments -ne $arguments) { throw 'Startup scheduled task verification failed' }
} catch {
    if ($task -or $existingRun) { throw }
    # The current non-elevated Windows token may not register a scheduled task.
    # HKCU Run has identical after-login semantics and needs no password/elevation.
    $registration = 'HKCU_CURRENT_USER_LOGON'
    $command = '"' + $pythonWindowless + '" ' + $arguments
    New-ItemProperty -LiteralPath $runKey -Name $runValue -Value $command -PropertyType String -ErrorAction Stop | Out-Null
    if ((Get-ItemPropertyValue -LiteralPath $runKey -Name $runValue) -ne $command) { throw 'Startup registry verification failed' }
}
Start-Process -FilePath $pythonWindowless -ArgumentList $arguments -WorkingDirectory $projectPath -WindowStyle Hidden
[ordered]@{status='INSTALLED'; registration=$registration; starts_after_current_user_login=$true; current_benchmark_restart=$false; config=[IO.Path]::GetFullPath($ConfigPath)} | ConvertTo-Json -Compress
