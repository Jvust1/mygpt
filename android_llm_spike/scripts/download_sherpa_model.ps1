[CmdletBinding()]
param(
    [ValidateSet("asr", "tts")]
    [string]$Kind = "asr",
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

$Assets = @{
    asr = @{
        Label = "sherpa streaming zh/en ASR"
        File = "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2"
        Bytes = [int64]511274346
        ReleaseTag = "asr-models"
        ReleaseId = [int64]130628817
        AssetId = [int64]170453803
        ApiUrl = "https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/assets/170453803"
        BrowserUrl = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2"
        ModelRevision = "98590b7ed6443e77b714204da2757d75e1a642f4"
        PostExtractGate = "ALL_FOUR_RUNTIME_CORE_FILES_HARD_LOCKED"
    }
    tts = @{
        Label = "sherpa Melo zh/en TTS"
        File = "vits-melo-tts-zh_en.tar.bz2"
        Bytes = [int64]167006755
        ReleaseTag = "tts-models"
        ReleaseId = [int64]130612623
        AssetId = [int64]203769960
        ApiUrl = "https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/assets/203769960"
        BrowserUrl = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-melo-tts-zh_en.tar.bz2"
        ModelRevision = "a0d5c6a264c0ef92d70d8661d8cc502d79627cd6"
        PostExtractGate = "MODEL_ONNX_HARD_LOCKED_PLUS_SUPPORT_FILE_MANIFEST"
    }
}

$Spec = $Assets[$Kind]

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
        $OutputDirectory = Join-Path $DriveVault "mygpt\voice_models"
    }
    else {
        $OutputDirectory = Join-Path $env:LOCALAPPDATA "MyGPT\voice-models"
    }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$Target = Join-Path $OutputDirectory $Spec.File

function Test-ExpectedBytes {
    param([string]$Path, [int64]$ExpectedBytes)
    return (Test-Path -LiteralPath $Path -PathType Leaf) -and
        ([int64](Get-Item -LiteralPath $Path).Length -eq $ExpectedBytes)
}

if (Test-ExpectedBytes $Target $Spec.Bytes) {
    Write-Host "Archive already has expected byte length: $Target" -ForegroundColor Green
}
else {
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Force
    }

    Write-Host ("Downloading " + $Spec.Label) -ForegroundColor Cyan
    Write-Host ("release=" + $Spec.ReleaseTag + " asset_id=" + $Spec.AssetId) -ForegroundColor DarkGray
    Write-Host ("expected_bytes=" + $Spec.Bytes) -ForegroundColor DarkGray

    # Prefer immutable GitHub release asset ID. Older assets do not expose a digest.
    $Args = @(
        "-L",
        "--fail",
        "--retry", "3",
        "--retry-delay", "2",
        "--connect-timeout", "30",
        "-H", "Accept: application/octet-stream",
        "-H", "X-GitHub-Api-Version: 2022-11-28",
        "-o", $Target,
        $Spec.ApiUrl
    )
    & curl.exe @Args

    if ($LASTEXITCODE -ne 0 -or -not (Test-ExpectedBytes $Target $Spec.Bytes)) {
        if (Test-Path -LiteralPath $Target) {
            Remove-Item -LiteralPath $Target -Force
        }

        Write-Host "Asset-ID endpoint did not return the expected archive; trying pinned release tag/name." -ForegroundColor Yellow
        $Fallback = @(
            "-L",
            "--fail",
            "--retry", "3",
            "--retry-delay", "2",
            "--connect-timeout", "30",
            "-o", $Target,
            $Spec.BrowserUrl
        )
        & curl.exe @Fallback
        if ($LASTEXITCODE -ne 0) {
            throw "Download failed: $($Spec.Label)"
        }
    }

    if (-not (Test-ExpectedBytes $Target $Spec.Bytes)) {
        $Actual = if (Test-Path -LiteralPath $Target) {
            [int64](Get-Item -LiteralPath $Target).Length
        } else {
            [int64]-1
        }
        throw "Archive byte length mismatch. expected=$($Spec.Bytes) actual=$Actual"
    }
}

$Item = Get-Item -LiteralPath $Target
@(
    "schema=mygpt.sherpa-archive-download.v1",
    "kind=$Kind",
    "label=$($Spec.Label)",
    "file=$($Spec.File)",
    "release_tag=$($Spec.ReleaseTag)",
    "release_id=$($Spec.ReleaseId)",
    "asset_id=$($Spec.AssetId)",
    "source_url=$($Spec.BrowserUrl)",
    "expected_bytes=$($Spec.Bytes)",
    "actual_bytes=$($Item.Length)",
    "github_digest=UNAVAILABLE_FOR_THIS_LEGACY_ASSET",
    "model_revision=$($Spec.ModelRevision)",
    "post_extract_gate=$($Spec.PostExtractGate)"
) | Out-File (Join-Path $OutputDirectory ($Spec.File + ".mygpt-manifest.txt")) -Encoding utf8

Write-Host "Sherpa archive ready:" -ForegroundColor Green
Write-Host ("  kind:      " + $Kind)
Write-Host ("  path:      " + $Target)
Write-Host ("  bytes:     " + $Item.Length)
Write-Host ("  asset id:  " + $Spec.AssetId)
Write-Host ("  IMPORTANT: archive digest is unavailable; Companion must pass post-extract core-file identity checks.")
