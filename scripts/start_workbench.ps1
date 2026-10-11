param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$workbenchRoot = Split-Path -Parent $PSScriptRoot
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Use a local unprivileged port (1024-65535)' }
$workbenchState = Join-Path $workbenchRoot '.local-workbench\workbench'
New-Item -ItemType Directory -Path $workbenchState -Force | Out-Null
$workbenchPython = if (Test-Path -LiteralPath 'D:\Anaconda\python.exe') { 'D:\Anaconda\python.exe' } else { (Get-Command python -ErrorAction Stop).Source }
try {
    $workbenchHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
    if ($workbenchHealth.phase -eq 'P5') { Write-Output "http://127.0.0.1:$Port"; exit 0 }
} catch { }
$workbenchSource = Join-Path $workbenchRoot 'scripts\workbench.py'
Start-Process -FilePath $workbenchPython -ArgumentList '-B',('"' + $workbenchSource + '"'),'serve','--port',$Port -WorkingDirectory $workbenchRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $workbenchState 'server.stdout.log') -RedirectStandardError (Join-Path $workbenchState 'server.stderr.log')
$workbenchDeadline = (Get-Date).AddSeconds(10)
do {
    try {
        $workbenchHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1
        if ($workbenchHealth.phase -eq 'P5') { Write-Output "http://127.0.0.1:$Port"; exit 0 }
    } catch { }
    Start-Sleep -Milliseconds 100
} while ((Get-Date) -lt $workbenchDeadline)
throw 'Workbench did not become ready; inspect the private server stderr log in .local-workbench/workbench'
