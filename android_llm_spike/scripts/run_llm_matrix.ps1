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

$QualitySampleCount = 0
$QualityByCandidate = [ordered]@{}
foreach ($Candidate in $Passed) {
    $QualityPath = Join-Path $OutputDirectory ("llm-quality-" + $Candidate + ".json")
    if (-not (Test-Path -LiteralPath $QualityPath -PathType Leaf)) {
        throw "Missing quality sample for passed candidate: $Candidate"
    }
    try {
        $QualityJson = Get-Content -LiteralPath $QualityPath -Raw | ConvertFrom-Json
    }
    catch {
        throw "Invalid quality JSON for passed candidate: $Candidate"
    }
    if ($QualityJson.schema -ne "mygpt.llm-quality-sample.v1" -or
        $QualityJson.candidate_id -ne $Candidate -or
        $QualityJson.completed -ne $true -or
        @($QualityJson.cases).Count -ne 5) {
        throw "Quality sample identity/completion mismatch: $Candidate"
    }
    $QualityByCandidate[$Candidate] = $QualityJson
    $QualitySampleCount++
}

function Convert-ToMarkdownCell {
    param([object]$Value)
    $Text = [string]$Value
    $Text = $Text -replace '\\', '\\\\'
    $Text = $Text -replace '\|', '\\|'
    $Text = $Text -replace "\r?\n", "<br>"
    return $Text.Trim()
}

$CaseOrder = @(
    "companion_minimum_step",
    "teach_banach_from_book",
    "book_authority_boundary",
    "memory_authority_boundary",
    "signed_help_signal"
)

$ReportLines = New-Object System.Collections.Generic.List[string]
$ReportLines.Add("# MyGPT Xiaomi 14 LLM quality comparison")
$ReportLines.Add("")
$ReportLines.Add("> Raw fixed-suite comparison only. No automatic score, rank, or winner.")
$ReportLines.Add("")
$ReportLines.Add("Device serial: " + $DeviceSerial)
$ReportLines.Add("")
$ReportLines.Add("Candidates: " + ($Passed -join ", "))
$ReportLines.Add("")

foreach ($CaseId in $CaseOrder) {
    $ReferenceCase = $null
    foreach ($Candidate in $Passed) {
        $Match = @($QualityByCandidate[$Candidate].cases | Where-Object { $_.id -eq $CaseId })
        if ($Match.Count -eq 1) { $ReferenceCase = $Match[0]; break }
    }
    if ($null -eq $ReferenceCase) { throw "Quality comparison case missing: $CaseId" }

    $ReportLines.Add("## " + $CaseId)
    $ReportLines.Add("")
    $ReportLines.Add("Focus: " + (Convert-ToMarkdownCell $ReferenceCase.focus))
    $ReportLines.Add("")
    $ReportLines.Add("| Candidate | Model | Wall ms | Emotion | Visible reply |")
    $ReportLines.Add("| --- | --- | ---: | --- | --- |")

    foreach ($Candidate in $Passed) {
        $Json = $QualityByCandidate[$Candidate]
        $Match = @($Json.cases | Where-Object { $_.id -eq $CaseId })
        if ($Match.Count -ne 1) { throw "Quality comparison mismatch: $Candidate / $CaseId" }
        $Case = $Match[0]
        $ReportLines.Add(
            "| " + (Convert-ToMarkdownCell $Candidate)
            + " | " + (Convert-ToMarkdownCell $Json.candidate_label)
            + " | " + [string]$Case.wall_ms
            + " | " + (Convert-ToMarkdownCell $Case.emotion)
            + " | " + (Convert-ToMarkdownCell $Case.visible_reply)
            + " |"
        )
    }
    $ReportLines.Add("")
}

$ReportLines.Add("## Notes")
$ReportLines.Add("")
$ReportLines.Add("- automatic_quality_ranking=DISABLED")
$ReportLines.Add("- Compare wording, authority-boundary behavior, Book grounding, companion tone, latency/RAM/thermal together.")
$ReportLines.Add("- Do not choose a default solely from parameter count or this text sample.")
$ReportLines | Out-File (Join-Path $OutputDirectory "llm-quality-comparison.md") -Encoding utf8

$Summary=@(
    "schema=mygpt.llm-benchmark-matrix.v2",
    "device_serial=$DeviceSerial",
    "candidate_directory=$CandidateDirectory",
    "pass_count=$($Passed.Count)",
    "passed=$($Passed -join ',')",
    "quality_sample_count=$QualitySampleCount",
    "automatic_quality_ranking=DISABLED"
)
$Summary | Out-File (Join-Path $OutputDirectory "llm-matrix-summary.txt") -Encoding utf8
Write-Host ("LLM matrix PASS: "+($Passed -join ", ")) -ForegroundColor Green
