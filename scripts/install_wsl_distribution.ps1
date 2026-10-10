# Continue the authorized project-only distribution installation after Windows restarts.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$work = Join-Path $taskRoot '.local-workbench/wsl'
$reportPath = Join-Path $taskRoot '.local-workbench/audits/wsl-distribution-install.json'
$clock = [Diagnostics.Stopwatch]::StartNew()
$report = [ordered]@{ started_at=(Get-Date -Format o); status='CHECKING'; automatic_reboot=$false; model_requests=0 }
function Save-Progress { $report.elapsed_seconds=$clock.Elapsed.TotalSeconds; $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8 }
function Read-ProjectDistro($name) {
    $registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
    if (Test-Path -LiteralPath $registry) {
        Get-ChildItem -LiteralPath $registry | Get-ItemProperty | Where-Object {$_.DistributionName -eq $name}
    }
}
try {
    $approval = Get-Content -LiteralPath (Join-Path $taskRoot '.local-workbench/approvals/wsl.json') -Raw | ConvertFrom-Json
    if ($approval.approved_by -ne 'human_user' -or -not $approval.system_components_allowed) { throw 'WSL installation is not authorized' }
    if ([IO.Path]::GetFullPath($approval.location) -ne $work) { throw 'Approved WSL location differs from this project' }
    $system = Get-Content -LiteralPath (Join-Path $taskRoot '.local-workbench/audits/wsl-system-install.json') -Raw | ConvertFrom-Json
    if ($system.status -notin @('RESTART_REQUIRED','SYSTEM_COMPONENTS_INSTALLED')) { throw 'System installation has not completed' }
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    $report.windows_boot_at=$boot.ToString('o')
    if ($system.status -eq 'RESTART_REQUIRED' -and ([datetimeoffset]$boot).UtcDateTime -le ([datetimeoffset]$system.started_at).UtcDateTime) {
        $report.status='BLOCKED_RESTART'
        Save-Progress
        Write-Output 'Windows must be restarted manually before installing the project distribution.'
        exit 75
    }
    $manifest = Get-Content -LiteralPath (Join-Path $taskRoot 'configs/wsl-assets.lock.json') -Raw | ConvertFrom-Json
    $target = [IO.Path]::GetFullPath((Join-Path $taskRoot $manifest.location))
    if (-not $target.StartsWith($work + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Distribution location escaped approved directory' }
    $name = $manifest.distribution_name
    if ($name -ne 'EnhancedHumanizer-P0') { throw 'Unexpected project distribution name' }
    $report.distribution_name=$name
    $report.location=$target
    $existing = @(Read-ProjectDistro $name)
    if ($existing.Count -gt 1) { throw 'Ambiguous existing distribution registration' }
    if ($existing.Count -eq 0) {
        if (Test-Path -LiteralPath $target) { throw 'Unregistered target already exists; inspect it without deleting or replacing it' }
        $asset = @($manifest.assets | Where-Object {$_.name -like '*.wsl'})
        if ($asset.Count -ne 1) { throw 'Expected one pinned Ubuntu image' }
        $image = [IO.Path]::GetFullPath((Join-Path $work ('downloads/' + $asset[0].name)))
        if (-not $image.StartsWith($work + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Image path escaped project' }
        if ((Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset[0].sha256) { throw 'Ubuntu image hash mismatch' }
        $report.status='INSTALLING'
        Save-Progress
        & "$env:SystemRoot/System32/wsl.exe" --install --from-file $image --location $target --name $name --version 2 --no-launch
        $report.wsl_exit_code=$LASTEXITCODE
        if ($LASTEXITCODE -ne 0) { throw "Distribution installation failed; exit code $LASTEXITCODE" }
        $existing = @(Read-ProjectDistro $name)
    } else {
        $report.reused_registration=$true
    }
    if ($existing.Count -ne 1) { throw 'Expected a registered project distribution' }
    $registeredPath = [IO.Path]::GetFullPath(($existing[0].BasePath -replace '^\\\\\?\\',''))
    if ($registeredPath.TrimEnd('\') -ne $target.TrimEnd('\') -or $existing[0].Version -ne 2) { throw 'Registered distribution path or WSL version differs from the approved target' }
    $report.registered_base_path=$registeredPath
    $report.wsl_version=2
    $report.status='DISTRIBUTION_REGISTERED_NOT_VALIDATED'
    Save-Progress
    Write-Output 'Project Ubuntu registered at the approved location. Linux tools, isolation and model demo still require validation.'
} catch {
    $report.status='INSTALL_FAILED'
    $report.error=$_.Exception.Message
    Save-Progress
    Write-Error $_
    exit 1
}
