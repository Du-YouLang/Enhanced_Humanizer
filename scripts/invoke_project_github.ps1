<# Project-scoped GitHub transport; never modifies persistent proxy settings. #>
[CmdletBinding()]
param(
    [ValidateSet('gh', 'git')]
    [string]$Tool = 'gh',
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments,
    [string]$ProxyUrl = 'http://127.0.0.1:7897'
)
$ErrorActionPreference = 'Stop'
$proxyUri = [Uri]$ProxyUrl
if ($proxyUri.Scheme -notin @('http', 'https') -or
    $proxyUri.Host -notin @('127.0.0.1', 'localhost', '[::1]', '::1') -or
    $proxyUri.UserInfo -or $proxyUri.Port -lt 1) {
    throw 'Only an explicitly selected local loopback proxy without embedded credentials is permitted.'
}
$executable = (Get-Command -Name $Tool -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$projectRoot = Split-Path -Parent $PSScriptRoot
$names = @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'NO_PROXY', 'no_proxy')
$previous = @{}
foreach ($name in $names) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$oldLocation = Get-Location
$nativeExit = 1
try {
    foreach ($name in $names) {
        $value = if ($name -in @('NO_PROXY', 'no_proxy')) { 'localhost,127.0.0.1,::1' } else { $ProxyUrl }
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
    Set-Location -LiteralPath $projectRoot
    & $executable @Arguments
    $nativeExit = $LASTEXITCODE
}
finally {
    Set-Location -LiteralPath $oldLocation.Path
    foreach ($name in $names) {
        if ($null -eq $previous[$name]) {
            Remove-Item -LiteralPath ("Env:" + $name) -ErrorAction SilentlyContinue
        }
        else {
            [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
        }
    }
}
exit $nativeExit
