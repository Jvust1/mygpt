param(
    [ValidateRange(0,65535)][int]$Port = 8766,
    [string]$AllowLocalTestCallback = '',
    [string[]]$AllowHttpsCallbackHost = @(),
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
if ($AllowLocalTestCallback -and $AllowHttpsCallbackHost.Count) {
    throw 'Local test callbacks and HTTPS callbacks are mutually exclusive.'
}
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$python = Join-Path $root 'work\mygpt-progress-venv\Scripts\python.exe'
$brain = Join-Path $root 'work\mygpt-fusion-snapshot\mygpt-1e766c00d7ccb857d7d5a858e7af776f66b611df\brain'
if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath (Join-Path $brain 'mygpt_brain\core.py'))) {
    throw 'The verified workspace Python/mygpt source is missing. See MCP_README.md; no packages will be downloaded automatically.'
}
$runtime = Join-Path $root 'work\mcp-prototype\runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
# Restrict only our runtime directory, never global permissions or product files.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $runtime '/inheritance:r' '/grant:r' "${identity}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect the local credential directory.' }
$credentials = Join-Path $runtime 'credentials.local.json'
if (!(Test-Path -LiteralPath $credentials)) {
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $one = New-Object byte[] 32; $two = New-Object byte[] 32
        $rng.GetBytes($one); $rng.GetBytes($two)
        $keys = @{ mcp_token = [Convert]::ToBase64String($one); ingest_token = [Convert]::ToBase64String($two) }
        $json = $keys | ConvertTo-Json
        [IO.File]::WriteAllText($credentials, $json, (New-Object Text.UTF8Encoding($false)))
    } finally { $rng.Dispose() }
}
$keys = Get-Content -LiteralPath $credentials -Raw -Encoding UTF8 | ConvertFrom-Json
if ($keys.mcp_token.Length -lt 32 -or $keys.ingest_token.Length -lt 32 -or $keys.mcp_token -eq $keys.ingest_token) {
    throw 'Invalid local credentials. Tokens are not printed or silently replaced.'
}
if ($PrepareOnly) {
    @{ event='mcp_runtime_prepared'; credential_values_printed=$false; real_dot_connected=$false } | ConvertTo-Json -Compress
    exit 0
}
$saved = @{}
foreach ($name in @('MCP_BRIDGE_TOKEN','MYGPT_INGEST_TOKEN','MYGPT_SOURCE_ROOT','PYTHONUTF8','PYTHONDONTWRITEBYTECODE')) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    $env:MCP_BRIDGE_TOKEN = $keys.mcp_token
    $env:MYGPT_INGEST_TOKEN = $keys.ingest_token
    $env:MYGPT_SOURCE_ROOT = $brain
    $env:PYTHONUTF8 = '1'; $env:PYTHONDONTWRITEBYTECODE = '1'
    $arguments = @((Join-Path $PSScriptRoot 'run_mcp_bridge.py'), '--port', "$Port", '--state-dir', $runtime)
    if ($AllowLocalTestCallback) { $arguments += @('--allow-local-test-callback', $AllowLocalTestCallback) }
    foreach ($hostName in $AllowHttpsCallbackHost) { $arguments += @('--allow-https-callback-host', $hostName) }
    Write-Host 'Local MCP prototype only. Stop with Ctrl+C. Your dot/model/Live are NOT connected.'
    & $python @arguments
    $result = $LASTEXITCODE
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
}
exit $result

