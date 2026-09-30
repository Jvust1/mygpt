[CmdletBinding()]
param(
    [ValidateSet("speed", "balanced", "quality")]
    [string]$Candidate = "balanced",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command "curl.exe"

$Candidates = @{
    speed = @{
        Label = "Qwen3.5-0.8B-Q4_0"
        File = "Qwen3.5-0.8B-Q4_0.gguf"
        Bytes = [int64]563036064
        Sha256 = "57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf"
        UpstreamCommit = "9447f74101aeb4e93621884dfa36ee8effb8831b"
        Url = "https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/9447f74101aeb4e93621884dfa36ee8effb8831b/Qwen3.5-0.8B-Q4_0.gguf"
    }
    balanced = @{
        Label = "Qwen3-1.7B-Q4_K_M"
        File = "Qwen3-1.7B-Q4_K_M.gguf"
        Bytes = [int64]1282439264
        Sha256 = "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
        UpstreamCommit = "daeb8e2d528a760970442092f6bf1e55c3b659eb"
        Url = "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf"
    }
    quality = @{
        Label = "Qwen3-4B-Q4_K_M"
        File = "Qwen3-4B-Q4_K_M.gguf"
        Bytes = [int64]2497280640
        Sha256 = "ab27b9bfa375a178d6cba48f3ad892b94b7739659dcc7aae8058ce0ffed6b328"
        UpstreamCommit = "2f3b082b1356a6123f7ed71e65aea340da25d53c"
        Url = "https://huggingface.co/ggml-org/Qwen3-4B-GGUF/resolve/2f3b082b1356a6123f7ed71e65aea340da25d53c/Qwen3-4B-Q4_K_M.gguf"
    }
}

$Spec = $Candidates[$Candidate]

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $DriveVault = $null
    foreach ($Drive in (Get-PSDrive -PSProvider FileSystem)) {
        $Probe = Join-Path $Drive.Root "My Drive\AI-Model-Vault"
        if (Test-Path $Probe -PathType Container) {
            $DriveVault = $Probe
            break
        }
    }

    if ($null -ne $DriveVault) {
        $OutputDirectory = Join-Path $DriveVault "mygpt\llm_candidates"
    }
    else {
        $OutputDirectory = Join-Path $env:LOCALAPPDATA "MyGPT\model-candidates"
    }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$Target = Join-Path $OutputDirectory $Spec.File

function Test-VerifiedFile {
    param(
        [string]$Path,
        [int64]$ExpectedBytes,
        [string]$ExpectedSha
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }

    $Item = Get-Item -LiteralPath $Path
    if ([int64]$Item.Length -ne $ExpectedBytes) { return $false }

    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $Hash -eq $ExpectedSha
}

if (Test-VerifiedFile $Target $Spec.Bytes $Spec.Sha256) {
    Write-Host "Already verified: $Target" -ForegroundColor Green
}
else {
    Write-Host ("Downloading benchmark candidate: " + $Spec.Label) -ForegroundColor Cyan
    Write-Host ("Pinned upstream commit: " + $Spec.UpstreamCommit) -ForegroundColor DarkGray
    Write-Host ("Expected bytes: " + $Spec.Bytes) -ForegroundColor DarkGray

    $CurlArgs = @(
        "-L",
        "--fail",
        "--retry", "3",
        "--retry-delay", "2",
        "--connect-timeout", "30",
        "-C", "-",
        "-o", $Target,
        $Spec.Url
    )

    & curl.exe @CurlArgs
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path -LiteralPath $Target) {
            Remove-Item -LiteralPath $Target -Force
        }
        $FreshArgs = @(
            "-L",
            "--fail",
            "--retry", "3",
            "--retry-delay", "2",
            "--connect-timeout", "30",
            "-o", $Target,
            $Spec.Url
        )
        & curl.exe @FreshArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Download failed: $($Spec.Label)"
        }
    }

    if (-not (Test-VerifiedFile $Target $Spec.Bytes $Spec.Sha256)) {
        $ActualBytes = if (Test-Path -LiteralPath $Target) {
            [int64](Get-Item -LiteralPath $Target).Length
        } else {
            [int64]-1
        }
        $ActualSha = if (Test-Path -LiteralPath $Target) {
            (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            "missing"
        }
        throw ("Downloaded GGUF identity mismatch. expected_bytes=" + $Spec.Bytes
            + " actual_bytes=" + $ActualBytes
            + " expected_sha256=" + $Spec.Sha256
            + " actual_sha256=" + $ActualSha)
    }
}

$Item = Get-Item -LiteralPath $Target
@(
    "schema=mygpt.llm-candidate-download.v2",
    "candidate=$Candidate",
    "label=$($Spec.Label)",
    "file=$($Spec.File)",
    "upstream_commit=$($Spec.UpstreamCommit)",
    "source_url=$($Spec.Url)",
    "expected_bytes=$($Spec.Bytes)",
    "actual_bytes=$($Item.Length)",
    "sha256=$($Spec.Sha256)"
) | Out-File (Join-Path $OutputDirectory ($Spec.File + ".mygpt-manifest.txt")) -Encoding utf8

Write-Host "Candidate ready:" -ForegroundColor Green
Write-Host ("  id:       " + $Candidate)
Write-Host ("  model:    " + $Spec.Label)
Write-Host ("  path:     " + $Target)
Write-Host ("  commit:   " + $Spec.UpstreamCommit)
Write-Host ("  bytes:    " + $Item.Length)
Write-Host ("  sha256:   " + $Spec.Sha256)
Write-Host ""
Write-Host "Next: select this GGUF in Companion V2, load it, then run the in-app benchmark."
