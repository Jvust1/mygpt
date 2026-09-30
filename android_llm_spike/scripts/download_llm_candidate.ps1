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
        Sha256 = "57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf"
        Url = "https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q4_0.gguf"
    }
    balanced = @{
        Label = "Qwen3-1.7B-Q4_K_M"
        File = "Qwen3-1.7B-Q4_K_M.gguf"
        Sha256 = "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
        Url = "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf"
    }
    quality = @{
        Label = "Qwen3-4B-Q4_K_M"
        File = "Qwen3-4B-Q4_K_M.gguf"
        Sha256 = "ab27b9bfa375a178d6cba48f3ad892b94b7739659dcc7aae8058ce0ffed6b328"
        Url = "https://huggingface.co/ggml-org/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf"
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
    param([string]$Path, [string]$ExpectedSha)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $Hash -eq $ExpectedSha
}

if (Test-VerifiedFile $Target $Spec.Sha256) {
    Write-Host "Already verified: $Target" -ForegroundColor Green
}
else {
    Write-Host ("Downloading benchmark candidate: " + $Spec.Label) -ForegroundColor Cyan

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
        # A stale complete file can make resume return HTTP 416. Retry once fresh.
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

    if (-not (Test-VerifiedFile $Target $Spec.Sha256)) {
        $Actual = if (Test-Path -LiteralPath $Target) {
            (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            "missing"
        }
        throw "Downloaded GGUF SHA-256 mismatch. expected=$($Spec.Sha256) actual=$Actual"
    }
}

$Item = Get-Item -LiteralPath $Target
@(
    "schema=mygpt.llm-candidate-download.v1",
    "candidate=$Candidate",
    "label=$($Spec.Label)",
    "file=$($Spec.File)",
    "bytes=$($Item.Length)",
    "sha256=$($Spec.Sha256)"
) | Out-File (Join-Path $OutputDirectory ($Spec.File + ".mygpt-manifest.txt")) -Encoding utf8

Write-Host "Candidate ready:" -ForegroundColor Green
Write-Host ("  id:     " + $Candidate)
Write-Host ("  model:  " + $Spec.Label)
Write-Host ("  path:   " + $Target)
Write-Host ("  bytes:  " + $Item.Length)
Write-Host ("  sha256: " + $Spec.Sha256)
Write-Host ""
Write-Host "Next: select this GGUF in Companion V2, load it, then run the in-app benchmark."
