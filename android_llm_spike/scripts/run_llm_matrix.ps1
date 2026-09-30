[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$AdbPath,
    [Parameter(Mandatory=$true)][string]$DeviceSerial,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$CandidateDirectory = "",
    [ValidateSet("speed","balanced","quality")][string[]]$Candidates = @("speed","balanced","quality")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DownloadScript = Join-Path $ScriptDir "download_llm_candidate.ps1"
$TestScript = Join-Path $ScriptDir "test_llm_candidate.ps1"
if (-not (Test-Path $DownloadScript)) { throw "Missing downloader: $DownloadScript" }
if (-not (Test-Path $TestScript)) { throw "Missing device test: $TestScript" }

if ([string]::IsNullOrWhiteSpace($CandidateDirectory)) {
    $DriveVault = $null
    foreach ($Drive in (Get-PSDrive -PSProvider FileSystem)) {
        $Probe = Join-Path $Drive.Root "My Drive\AI-Model-Vault"
        if (Test-Path $Probe -PathType Container) { $DriveVault=$Probe; break }
    }
    if ($null -ne $DriveVault) {
        $CandidateDirectory = Join-Path $DriveVault "mygpt\llm_candidates"
    } else {
        $CandidateDirectory = Join-Path $env:LOCALAPPDATA "MyGPT\model-candidates"
    }
}
New-Item -ItemType Directory -Path $CandidateDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$CandidateDirectory=(Resolve-Path $CandidateDirectory).Path
$OutputDirectory=(Resolve-Path $OutputDirectory).Path

$Files=@{
    speed="Qwen3.5-0.8B-Q4_0.gguf"
    balanced="Qwen3-1.7B-Q4_K_M.gguf"
    quality="Qwen3-4B-Q4_K_M.gguf"
}

$Passed=New-Object System.Collections.Generic.List[string]
foreach($Candidate in $Candidates){
    Write-Host ("=== MyGPT LLM matrix: "+$Candidate+" ===") -ForegroundColor Cyan
    & $DownloadScript -Candidate $Candidate -OutputDirectory $CandidateDirectory
    if($LASTEXITCODE -ne 0){ throw "Candidate download failed: $Candidate" }
    $Path=Join-Path $CandidateDirectory $Files[$Candidate]
    & $TestScript -ModelPath $Path -AdbPath $AdbPath -DeviceSerial $DeviceSerial -OutputDirectory $OutputDirectory
    if($LASTEXITCODE -ne 0){ throw "Candidate device gate failed: $Candidate" }
    $Passed.Add($Candidate)
}

$QualityFiles=@(Get-ChildItem -LiteralPath $OutputDirectory -Filter "llm-quality-*.json" -File -ErrorAction SilentlyContinue)

$Summary=@(
    "schema=mygpt.llm-benchmark-matrix.v2",
    "device_serial=$DeviceSerial",
    "candidate_directory=$CandidateDirectory",
    "pass_count=$($Passed.Count)",
    "passed=$($Passed -join ',')",
    "quality_sample_count=$($QualityFiles.Count)",
    "automatic_quality_ranking=DISABLED"
)
$Summary | Out-File (Join-Path $OutputDirectory "llm-matrix-summary.txt") -Encoding utf8
Write-Host ("LLM matrix PASS: "+($Passed -join ", ")) -ForegroundColor Green
