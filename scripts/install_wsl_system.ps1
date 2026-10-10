# Run once elevated, after the user's recorded WSL approval. Never restarts Windows.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$approvalPath = Join-Path $taskRoot '.local-workbench/approvals/wsl.json'
$approval = Get-Content -LiteralPath $approvalPath -Raw | ConvertFrom-Json
if ($approval.approved_by -ne 'human_user' -or -not $approval.system_components_allowed) {
    throw 'WSL system installation is not authorized'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'This installer requires the user to accept Windows elevation'
}
$work = Join-Path $taskRoot '.local-workbench/wsl'
$logs = Join-Path $work 'logs'
$scratch = Join-Path $work 'tmp'
New-Item -ItemType Directory -Path $logs,$scratch -Force | Out-Null
$env:TEMP = $scratch
$env:TMP = $scratch
$reportPath = Join-Path $taskRoot '.local-workbench/audits/wsl-system-install.json'
$clock = [Diagnostics.Stopwatch]::StartNew()
$report = [ordered]@{ started_at=(Get-Date -Format o); status='RUNNING'; automatic_reboot=$false; elevated=$true }
function Save-Progress { $report.elapsed_seconds=$clock.Elapsed.TotalSeconds; $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8 }
try {
    $manifest = Get-Content -LiteralPath (Join-Path $taskRoot 'configs/wsl-assets.lock.json') -Raw | ConvertFrom-Json
    $asset = $manifest.assets | Where-Object {$_.name -like '*.msi'}
    if (@($asset).Count -ne 1) { throw 'Expected one pinned MSI' }
    $msiPath = [IO.Path]::GetFullPath((Join-Path $work ('downloads/' + $asset.name)))
    if (-not $msiPath.StartsWith($work + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Installer path escaped project' }
    if ((Get-FileHash -LiteralPath $msiPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.sha256) { throw 'MSI hash mismatch' }
    $signature = Get-AuthenticodeSignature -LiteralPath $msiPath
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Microsoft publisher signature is not valid' }
    $report.publisher_signature='Valid Microsoft Corporation'
    Save-Progress
    $feature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
    $report.virtual_machine_platform_before=$feature.State.ToString()
    if ($feature.State -eq 'Disabled') {
        $enabled = Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart -LogPath (Join-Path $logs 'virtual-machine-platform.log')
        $report.feature_restart_needed=[bool]$enabled.RestartNeeded
    }
    $report.virtual_machine_platform_after=(Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State.ToString()
    Save-Progress
    $msiLog = Join-Path $logs 'wsl-msi.log'
    $process = Start-Process -FilePath "$env:SystemRoot/System32/msiexec.exe" -ArgumentList @('/i',('"'+$msiPath+'"'),'/qn','/norestart','REBOOT=ReallySuppress','/l*v',('"'+$msiLog+'"')) -WindowStyle Hidden -Wait -PassThru
    $report.msi_exit_code=$process.ExitCode
    if ($process.ExitCode -notin @(0,3010)) { throw "WSL MSI failed; exit code $($process.ExitCode)" }
    $report.status=if ($report.feature_restart_needed -or $process.ExitCode -eq 3010 -or $report.virtual_machine_platform_after -eq 'EnablePending') {'RESTART_REQUIRED'} else {'SYSTEM_COMPONENTS_INSTALLED'}
    Save-Progress
} catch {
    $report.status='INSTALL_FAILED'
    $report.error=$_.Exception.Message
    Save-Progress
    exit 1
}
