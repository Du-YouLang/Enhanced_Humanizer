param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$ExpectedSHA256,
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][string]$PythonPath
)
$ErrorActionPreference = 'Stop'
$workbenchPython = (Resolve-Path -LiteralPath $PythonPath).Path
$workbenchArchive = (Resolve-Path -LiteralPath $Archive).Path
$workbenchInstaller = Join-Path $PSScriptRoot 'package_workbench.py'
& $workbenchPython -B $workbenchInstaller install --archive $workbenchArchive --sha256 $ExpectedSHA256 --destination $Destination
if ($LASTEXITCODE -ne 0) { throw 'Source installation failed; existing and failed directories are preserved' }
$workbenchDestination = (Resolve-Path -LiteralPath $Destination).Path
$workbenchRuntime = Join-Path $workbenchDestination '.local-workbench\runtime\windows'
$workbenchCache = Join-Path $workbenchDestination '.local-workbench\cache\pip'
$workbenchTemp = Join-Path $workbenchDestination '.local-workbench\tmp'
New-Item -ItemType Directory -Path $workbenchCache,$workbenchTemp -Force | Out-Null
$workbenchOldTemp = $env:TEMP; $workbenchOldTmp = $env:TMP
try {
    $env:TEMP = $workbenchTemp; $env:TMP = $workbenchTemp
    & $workbenchPython -B -m venv $workbenchRuntime
    if ($LASTEXITCODE -ne 0) { throw 'Local Python environment creation failed' }
    $workbenchLocalPython = Join-Path $workbenchRuntime 'Scripts\python.exe'
    $workbenchLock = Join-Path $workbenchDestination 'configs\requirements-workbench-windows.lock'
    & $workbenchLocalPython -B -m pip --isolated --disable-pip-version-check install --index-url https://pypi.org/simple --no-compile --require-hashes --only-binary=:all: --cache-dir $workbenchCache -r $workbenchLock
    if ($LASTEXITCODE -ne 0) { throw 'Pinned local dependencies could not be installed' }
    & $workbenchLocalPython -B (Join-Path $workbenchDestination 'scripts\doctor_workbench.py')
    if ($LASTEXITCODE -ne 0) { throw 'Installed source/UI diagnostics failed' }
    $workbenchReceiptPath = Join-Path $workbenchDestination '.local-workbench\delivery\install-receipt.json'
    $workbenchReceipt = Get-Content -LiteralPath $workbenchReceiptPath -Raw | ConvertFrom-Json
    $workbenchReceipt | Add-Member -NotePropertyName runtime_status -NotePropertyValue 'LOCAL_UI_READY_LIVE_DISABLED'
    $workbenchReceipt | Add-Member -NotePropertyName runtime_path -NotePropertyValue $workbenchRuntime
    $workbenchReceiptJSON = $workbenchReceipt | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($workbenchReceiptPath, $workbenchReceiptJSON, (New-Object System.Text.UTF8Encoding($false)))
} finally {
    $env:TEMP = $workbenchOldTemp; $env:TMP = $workbenchOldTmp
}
Write-Output ('Local preview installed. Start with: & "' + (Join-Path $workbenchDestination 'scripts\start_workbench.ps1') + '" -Port 8767')
