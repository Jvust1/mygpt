param(
    [string]$BookServerFile = '',
    [ValidateRange(1,65535)][int]$McpPort = 8766,
    [ValidateRange(1,65535)][int]$LivePort = 8767,
    [string[]]$AllowHttpsCallbackHost = @(),
    [switch]$WithoutLive,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$python = Join-Path $root 'work\mygpt-progress-venv\Scripts\python.exe'
$runtime = Join-Path $root 'work\mcp-prototype\runtime'
if (-not $BookServerFile) { $BookServerFile = Join-Path $env:LOCALAPPDATA 'BookSeven\server.json' }
if (-not $PrepareOnly -and -not (Test-Path -LiteralPath $BookServerFile)) {
    throw 'Start Book-1.3.1-StudyBridge-Windows-x64.exe first, or pass -BookServerFile for its server.json. No model will be called.'
}
$saved = @{}
foreach ($name in @('MCP_BRIDGE_TOKEN','MYGPT_INGEST_TOKEN','LIVE_STUDY_TOKEN','LIVE_STUDY_PORT','LIVE_STUDY_USER_DATA','PYTHONUTF8','PYTHONDONTWRITEBYTECODE')) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
$liveProcessId = $null
try {
    & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot 'Start-MCP.ps1') -PrepareOnly
    if ($LASTEXITCODE -ne 0) { throw 'MCP local credential preparation failed.' }
    $keys = Get-Content -LiteralPath (Join-Path $runtime 'credentials.local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $env:MCP_BRIDGE_TOKEN = $keys.mcp_token
    $env:MYGPT_INGEST_TOKEN = $keys.ingest_token
    $env:PYTHONUTF8 = '1'; $env:PYTHONDONTWRITEBYTECODE = '1'
    $liveLauncher = Join-Path $PSScriptRoot '..\live\Start-Live-Study.ps1'
    if (-not $WithoutLive) {
        & $liveLauncher -Port $LivePort -PrepareOnly | Out-Null
        # PrepareOnly leaves the narrow local Live token in this process only.
    }
    if ($PrepareOnly) {
        @{event='study_link_prepared';model_configured=$false;real_dot_connected=$false;credentials_printed=$false} | ConvertTo-Json -Compress
        return
    }
    if (-not $WithoutLive) {
        $live = (& $liveLauncher -Port $LivePort | ConvertFrom-Json)
        $liveProcessId = $live.pid
    }
    $arguments = @((Join-Path $PSScriptRoot 'run_study_link.py'),'--book-server-file',[IO.Path]::GetFullPath($BookServerFile),'--mcp-port',"$McpPort",'--state-dir',$runtime)
    if (-not $WithoutLive) { $arguments += @('--live-origin',('http://127.0.0.1:'+$LivePort)) }
    foreach ($hostName in $AllowHttpsCallbackHost) { $arguments += @('--allow-https-callback-host',$hostName) }
    Write-Host 'Book -> mygpt -> local MCP. Enable reading sharing in Book. Model and real dot are NOT connected. Ctrl+C stops this bridge.'
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw ('Study link stopped with exit status '+$LASTEXITCODE) }
} finally {
    # Never stop a pre-existing Book, Live or unrelated process.
    if ($liveProcessId) { Get-Process -Id $liveProcessId -ErrorAction SilentlyContinue | Stop-Process -ErrorAction SilentlyContinue }
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
}

