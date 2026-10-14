$ErrorActionPreference = 'Stop'
$project = 'D:\Desktop\Enhanced_Humanizer'
$folder = $project + '\.local-workbench\recovery\p6-observer-watchdog-v1'
$name = 'Enhanced_Humanizer_ReadOnly_Observer'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$administrator = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $administrator.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Task registration was denied by Windows. Run this saved script in an administrator PowerShell; task itself runs with limited privileges.' }
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw 'Existing task preserved. Do not overwrite without inspecting its definition.' }
& 'D:\Anaconda\python.exe' ($folder + '\watchdog.py') --config ($folder + '\config.private.json') --preflight
if ($LASTEXITCODE -ne 0) { throw 'Pinned read-only watchdog preflight failed' }
$sid = $identity.User.Value
$action = New-ScheduledTaskAction -Execute 'D:\Anaconda\pythonw.exe' -Argument ($folder + '\watchdog.py --config ' + $folder + '\config.private.json') -WorkingDirectory $project
$login = New-ScheduledTaskTrigger -AtLogOn -User $sid
$repeat = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$definition = New-ScheduledTask -Action $action -Trigger @($login,$repeat) -Principal $principal -Settings $settings -Description 'Pinned project read-only observer; no model or budget dispatch; existing singleton protects active observer.'
Register-ScheduledTask -TaskName $name -InputObject $definition -ErrorAction Stop | Out-Null
$task = Get-ScheduledTask -TaskName $name -ErrorAction Stop
if ($task.Actions.Execute -ne 'D:\Anaconda\pythonw.exe' -or $task.Actions.Arguments -ne $action.Arguments) { throw 'Scheduled action readback mismatch' }
if ($task.Principal.RunLevel -ne 'Limited' -or $task.Settings.MultipleInstances -ne 'IgnoreNew') { throw 'Scheduled privileges or singleton settings differ' }
if ($task.Triggers.Count -ne 2 -or $task.Settings.ExecutionTimeLimit -ne 'PT0S') { throw 'Scheduled trigger or duration readback mismatch' }
$xml = Export-ScheduledTask -TaskName $name -ErrorAction Stop
[IO.File]::WriteAllText(($folder + '\scheduled-task-v2.private.xml'),$xml,[Text.UTF8Encoding]::new($false))
$receipt = [ordered]@{ installed_at=(Get-Date).ToUniversalTime().ToString('o'); task_name=$name; action_readback_matches=$true; limited_interactive_user=$true; login_trigger=$true; periodic_trigger='PT1M'; start_when_available=$task.Settings.StartWhenAvailable; multiple_instances='IgnoreNew'; hidden=$task.Settings.Hidden; execution_limit=$task.Settings.ExecutionTimeLimit; task_xml_sha256=(Get-FileHash -LiteralPath ($folder+'\scheduled-task-v2.private.xml') -Algorithm SHA256).Hash.ToLowerInvariant(); watchdog_sha256=(Get-FileHash -LiteralPath ($folder+'\watchdog.py') -Algorithm SHA256).Hash.ToLowerInvariant(); models_started=0; ledger_mutations=0; reboot_performed=$false; old_hkcu_entry_preserved=$true }
[IO.File]::WriteAllText(($folder + '\installation-v2.private.json'),($receipt | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
Start-ScheduledTask -TaskName $name -ErrorAction Stop
[pscustomobject]@{ task_name=$name; state=(Get-ScheduledTask -TaskName $name -ErrorAction Stop).State.ToString(); configuration='HIDDEN_LIMITED_LOGIN_AND_ONE_MINUTE_RECOVERY'; models_started=0 } | ConvertTo-Json -Compress
