param([int]$Port = 8765, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
$workbenchRoot = Split-Path -Parent $PSScriptRoot
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Use a local unprivileged port (1024-65535)' }
$workbenchState = Join-Path $workbenchRoot '.local-workbench\workbench'
New-Item -ItemType Directory -Path $workbenchState -Force | Out-Null
$workbenchLocalPython = Join-Path $workbenchRoot '.local-workbench\runtime\windows\Scripts\python.exe'
$workbenchPython = if ($PythonPath) { (Resolve-Path -LiteralPath $PythonPath).Path } elseif (Test-Path -LiteralPath $workbenchLocalPython) { $workbenchLocalPython } elseif (Test-Path -LiteralPath 'D:\Anaconda\python.exe') { 'D:\Anaconda\python.exe' } else { (Get-Command python -ErrorAction Stop).Source }
$workbenchHealth = $null
try {
    $workbenchHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
} catch { }
if ($workbenchHealth) {
    if ($workbenchHealth.phase -eq 'P5' -and $workbenchHealth.project_root -eq $workbenchRoot) { Write-Output "http://127.0.0.1:$Port"; exit 0 }
    throw 'Port belongs to another or older workspace. Choose another port; existing services are preserved.'
}
$workbenchSource = Join-Path $workbenchRoot 'scripts\workbench.py'
$workbenchProcess = Start-Process -FilePath $workbenchPython -ArgumentList '-B',('"' + $workbenchSource + '"'),'serve','--port',$Port -WorkingDirectory $workbenchRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $workbenchState 'server.stdout.log') -RedirectStandardError (Join-Path $workbenchState 'server.stderr.log') -PassThru
$workbenchProcess.Id | Set-Content -LiteralPath (Join-Path $workbenchState 'server.pid')
$workbenchDeadline = (Get-Date).AddSeconds(10)
do {
    try {
        $workbenchHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1
        if ($workbenchHealth.phase -eq 'P5' -and $workbenchHealth.project_root -eq $workbenchRoot) { Write-Output "http://127.0.0.1:$Port"; exit 0 }
    } catch { }
    Start-Sleep -Milliseconds 100
} while ((Get-Date) -lt $workbenchDeadline)
throw 'Workbench did not become ready; inspect the private server stderr log in .local-workbench/workbench'
