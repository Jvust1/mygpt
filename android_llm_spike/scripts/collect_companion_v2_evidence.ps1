[CmdletBinding()]
param(
    [string]$DeviceSerial = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $ProjectDir "..")).Path

$SourceHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$SourceBranch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()

$SdkRoot = $env:ANDROID_HOME
if ([string]::IsNullOrWhiteSpace($SdkRoot)) {
    $SdkRoot = $env:ANDROID_SDK_ROOT
}
if ([string]::IsNullOrWhiteSpace($SdkRoot) -or -not (Test-Path $SdkRoot)) {
    throw "ANDROID_HOME or ANDROID_SDK_ROOT must point to an installed Android SDK."
}

$Adb = Join-Path $SdkRoot "platform-tools\adb.exe"
if (-not (Test-Path $Adb)) {
    throw "adb.exe not found: $Adb"
}

$DeviceLines = @(
    & $Adb devices |
        Select-Object -Skip 1 |
        Where-Object { $_ -match "\s+device$" }
)

if ([string]::IsNullOrWhiteSpace($DeviceSerial)) {
    if ($DeviceLines.Count -ne 1) {
        throw "Expected exactly one authorized Android device. Use -DeviceSerial if needed."
    }
    $DeviceSerial = ($DeviceLines[0] -split "\s+")[0]
}
else {
    $KnownSerials = @($DeviceLines | ForEach-Object { ($_ -split "\s+")[0] })
    if ($KnownSerials -notcontains $DeviceSerial) {
        throw "Requested device is not connected/authorized: $DeviceSerial"
    }
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDirectory = Join-Path $ProjectDir ("device_evidence\manual-" + $Timestamp)
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path

Write-Host "Collecting Companion V2 evidence from $DeviceSerial" -ForegroundColor Cyan

$BundledSkinEvidencePath = Join-Path $OutputDirectory "bundled-skin-evidence.txt"
if (Test-Path $BundledSkinEvidencePath) {
    $BundledSkinEvidenceText = Get-Content $BundledSkinEvidencePath -Raw
    if ($BundledSkinEvidenceText -match "bundled=True" -and
        $BundledSkinEvidenceText -match "apk_entry_status=PASS" -and
        $BundledSkinEvidenceText -match "sha256=eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f") {
        $BundledSkinStatus = "PASS"
    }
    elseif ($BundledSkinEvidenceText -match "bundled=False" -and
            $BundledSkinEvidenceText -match "apk_entry_status=NOT_BUNDLED") {
        $BundledSkinStatus = "NOT_BUNDLED"
    }
    else {
        $BundledSkinStatus = "INVALID_EVIDENCE"
        throw "Bundled skin evidence exists but is internally inconsistent."
    }
}
else {
    $BundledSkinStatus = "UNKNOWN"
}

$SourceHead | Out-File (Join-Path $OutputDirectory "source-head.txt") -Encoding utf8
$SourceBranch | Out-File (Join-Path $OutputDirectory "source-branch.txt") -Encoding utf8
& git -C $RepoRoot status --porcelain --untracked-files=no |
    Out-File (Join-Path $OutputDirectory "source-dirty.txt") -Encoding utf8

$DeviceInfo = @(
    "serial=$DeviceSerial",
    "model=" + ((& $Adb -s $DeviceSerial shell getprop ro.product.model).Trim()),
    "device=" + ((& $Adb -s $DeviceSerial shell getprop ro.product.device).Trim()),
    "android_release=" + ((& $Adb -s $DeviceSerial shell getprop ro.build.version.release).Trim()),
    "sdk=" + ((& $Adb -s $DeviceSerial shell getprop ro.build.version.sdk).Trim()),
    "abi=" + ((& $Adb -s $DeviceSerial shell getprop ro.product.cpu.abi).Trim())
)
$DeviceInfo | Out-File (Join-Path $OutputDirectory "device-info.txt") -Encoding utf8

$CompanionDump = & $Adb -s $DeviceSerial shell dumpsys package dev.mygpt.companionv2
$CompanionDumpText = ($CompanionDump | Out-String)
$CompanionDump |
    Out-File (Join-Path $OutputDirectory "dumpsys-companion-package.txt") -Encoding utf8

$SenderDump = & $Adb -s $DeviceSerial shell dumpsys package dev.mygpt.bookcontexttest
$SenderDump |
    Out-File (Join-Path $OutputDirectory "dumpsys-book-sender-package.txt") -Encoding utf8

$PermissionFailures = @()
foreach ($BadPermission in @(
    "android.permission.INTERNET",
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE"
)) {
    if ($CompanionDumpText -match [regex]::Escape($BadPermission)) {
        $PermissionFailures += $BadPermission
    }
}

if ($PermissionFailures.Count -gt 0) {
    ("FAIL unexpected permissions: " + ($PermissionFailures -join ", ")) |
        Out-File (Join-Path $OutputDirectory "permission-boundary-check.txt") -Encoding utf8
    throw "Unexpected Companion V2 permission(s): $($PermissionFailures -join ', ')"
}

"PASS: no INTERNET / SYSTEM_ALERT_WINDOW / broad storage permission detected" |
    Out-File (Join-Path $OutputDirectory "permission-boundary-check.txt") -Encoding utf8

& $Adb -s $DeviceSerial shell dumpsys meminfo dev.mygpt.companionv2 |
    Out-File (Join-Path $OutputDirectory "meminfo-current.txt") -Encoding utf8

& $Adb -s $DeviceSerial shell dumpsys thermalservice |
    Out-File (Join-Path $OutputDirectory "thermal-current.txt") -Encoding utf8

& $Adb -s $DeviceSerial shell dumpsys activity activities |
    Out-File (Join-Path $OutputDirectory "activity-current.txt") -Encoding utf8

$Pid = (& $Adb -s $DeviceSerial shell pidof dev.mygpt.companionv2).Trim()
if (-not [string]::IsNullOrWhiteSpace($Pid)) {
    & $Adb -s $DeviceSerial logcat -d --pid=$Pid -v threadtime |
        Out-File (Join-Path $OutputDirectory "logcat-companion-current.txt") -Encoding utf8
}

$PromptBudget = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/prompt-budget-last.txt 2>&1
if ($LASTEXITCODE -eq 0 -and (($PromptBudget | Out-String) -match "schema=mygpt.prompt-budget.v1")) {
    $PromptBudgetStatus = "present"
    $PromptBudget | Out-File (Join-Path $OutputDirectory "prompt-budget-last.txt") -Encoding utf8
}
else {
    $PromptBudgetStatus = "missing"
    $PromptBudget | Out-File (Join-Path $OutputDirectory "prompt-budget-error.txt") -Encoding utf8
}

$BenchmarkCandidates = @(
    @{ Id = "speed"; Prefix = "57d1997790d1744f"; Output = "benchmark-speed.txt" },
    @{ Id = "balanced"; Prefix = "d2387ca2dbfee2ff"; Output = "benchmark-balanced.txt" },
    @{ Id = "quality"; Prefix = "ab27b9bfa375a178"; Output = "benchmark-quality.txt" }
)
$BenchmarkMatrixCount = 0
foreach ($Entry in $BenchmarkCandidates) {
    $RemoteName = "files/benchmark-" + $Entry.Prefix + ".txt"
    $Value = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat $RemoteName 2>&1
    if ($LASTEXITCODE -eq 0 -and (($Value | Out-String) -match "schema=mygpt.android-llm-benchmark.v1")) {
        $Value | Out-File (Join-Path $OutputDirectory $Entry.Output) -Encoding utf8
        $BenchmarkMatrixCount++
    }
}

$Benchmark = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/benchmark-last.txt 2>&1
$BenchmarkExit = $LASTEXITCODE
if ($BenchmarkExit -eq 0 -and -not [string]::IsNullOrWhiteSpace(($Benchmark | Out-String))) {
    $Benchmark | Out-File (Join-Path $OutputDirectory "benchmark-last.txt") -Encoding utf8
    $BenchmarkStatus = "present"
    Write-Host "Benchmark report captured." -ForegroundColor Green
}
else {
    $Benchmark | Out-File (Join-Path $OutputDirectory "benchmark-capture-error.txt") -Encoding utf8
    $BenchmarkStatus = "missing"
    Write-Host "No benchmark report captured yet. Run the in-app benchmark first." -ForegroundColor Yellow
}

$SupervisionGate = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest cat files/adb-supervision-gate.txt 2>&1
$SupervisionGateExit = $LASTEXITCODE
$SupervisionGateText = ($SupervisionGate | Out-String).Trim()
if ($SupervisionGateExit -eq 0) {
    $SupervisionGate | Out-File (Join-Path $OutputDirectory "supervision-gate.txt") -Encoding utf8
}
else {
    $SupervisionGate | Out-File (Join-Path $OutputDirectory "supervision-gate-error.txt") -Encoding utf8
}
$SupervisionStatus = if ($SupervisionGateText -eq "PASS") { "PASS" } else { "UNKNOWN_OR_NOT_RUN" }

$PipGate = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/adb-pip-gate.txt 2>&1
if ($LASTEXITCODE -eq 0 -and (($PipGate | Out-String) -match "PASS")) {
    $PipGateStatus = "PASS"
    $PipGate | Out-File (Join-Path $OutputDirectory "pip-gate.txt") -Encoding utf8
}
else {
    $PipGateStatus = "UNKNOWN_OR_NOT_RUN"
    $PipGate | Out-File (Join-Path $OutputDirectory "pip-gate-error.txt") -Encoding utf8
}

$BookResult = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest cat files/adb-book-result.txt 2>&1
$BookResultExit = $LASTEXITCODE
$BookResultText = ($BookResult | Out-String)
if ($BookResultExit -eq 0) {
    $BookResult | Out-File (Join-Path $OutputDirectory "book-sender-last-result.txt") -Encoding utf8
}
else {
    $BookResult | Out-File (Join-Path $OutputDirectory "book-sender-result-error.txt") -Encoding utf8
}

if ($BookResultText -match "accepted=true" -and
    $BookResultText -match "sdk=true" -and
    $BookResultText -match "preflight=READY" -and
    $BookResultText -match "status=ACCEPTED") {
    $BookGateStatus = "PASS"
}
else {
    $BookGateStatus = "UNKNOWN_OR_NOT_RUN"
}

$AsrManifest = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/asr-models/sherpa-zh-en-streaming/mygpt-model-manifest.txt 2>&1
if ($LASTEXITCODE -eq 0 -and (($AsrManifest | Out-String) -match "schema=mygpt.model-fingerprint.v1")) {
    $AsrManifestStatus = "present"
    $AsrManifest | Out-File (Join-Path $OutputDirectory "asr-model-manifest.txt") -Encoding utf8
}
else {
    $AsrManifestStatus = "missing"
    $AsrManifest | Out-File (Join-Path $OutputDirectory "asr-model-manifest-error.txt") -Encoding utf8
}

$TtsManifest = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/tts-models/sherpa-melo-zh-en-tts/mygpt-model-manifest.txt 2>&1
if ($LASTEXITCODE -eq 0 -and (($TtsManifest | Out-String) -match "schema=mygpt.model-fingerprint.v1")) {
    $TtsManifestStatus = "present"
    $TtsManifest | Out-File (Join-Path $OutputDirectory "tts-model-manifest.txt") -Encoding utf8
}
else {
    $TtsManifestStatus = "missing"
    $TtsManifest | Out-File (Join-Path $OutputDirectory "tts-model-manifest-error.txt") -Encoding utf8
}

$PrivateListing = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 sh -c "find files -type f -print" 2>&1
if ($LASTEXITCODE -ne 0) {
    $PrivateListing |
        Out-File (Join-Path $OutputDirectory "app-private-files-error.txt") -Encoding utf8
    throw "Unable to inspect Companion V2 app-private files."
}

$PrivateListingText = ($PrivateListing | Out-String)
$PrivateListing | Out-File (Join-Path $OutputDirectory "app-private-files.txt") -Encoding utf8

$AudioLeakPattern = '\.(wav|pcm|raw|mp3|m4a|aac|ogg)$'
if ($PrivateListingText -match $AudioLeakPattern) {
    ("FAIL: persisted audio-like file detected" + [Environment]::NewLine + $PrivateListingText) |
        Out-File (Join-Path $OutputDirectory "audio-persistence-check.txt") -Encoding utf8
    throw "Unexpected persisted audio-like file found in Companion V2 private files."
}

"PASS: no persisted wav/pcm/raw/mp3/m4a/aac/ogg file found" |
    Out-File (Join-Path $OutputDirectory "audio-persistence-check.txt") -Encoding utf8

$Packages = & $Adb -s $DeviceSerial shell pm list packages dev.mygpt
$Packages | Out-File (Join-Path $OutputDirectory "mygpt-packages.txt") -Encoding utf8

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RemoteScreenshot = "/sdcard/mygpt-companion-v2-" + $Timestamp + ".png"
$LocalScreenshot = Join-Path $OutputDirectory "companion-current.png"
& $Adb -s $DeviceSerial shell screencap -p $RemoteScreenshot | Out-Null
if ($LASTEXITCODE -eq 0) {
    & $Adb -s $DeviceSerial pull $RemoteScreenshot $LocalScreenshot | Out-Null
    & $Adb -s $DeviceSerial shell rm -f $RemoteScreenshot | Out-Null
}

$Summary = @(
    "schema=mygpt.companion-v2-evidence.v1",
    "source_head=$SourceHead",
    "source_branch=$SourceBranch",
    "device_serial=$DeviceSerial",
    "bundled_skin=$BundledSkinStatus",
    "book_gate=$BookGateStatus",
    "supervision=$SupervisionStatus",
    "pip_gate=$PipGateStatus",
    "benchmark=$BenchmarkStatus",
    "benchmark_matrix_count=$BenchmarkMatrixCount",
    "prompt_budget=$PromptBudgetStatus",
    "asr_model_manifest=$AsrManifestStatus",
    "tts_model_manifest=$TtsManifestStatus",
    "permission_boundary=PASS",
    "audio_persistence=PASS"
)
$Summary | Out-File (Join-Path $OutputDirectory "evidence-summary.txt") -Encoding utf8

Write-Host "Evidence collected: $OutputDirectory" -ForegroundColor Green
Write-Host "permission_boundary=PASS" -ForegroundColor Green
Write-Host "audio_persistence=PASS" -ForegroundColor Green
Write-Host "bundled_skin=$BundledSkinStatus"
Write-Host "book_gate=$BookGateStatus"
Write-Host "supervision=$SupervisionStatus"
Write-Host "pip_gate=$PipGateStatus"
Write-Host "benchmark=$BenchmarkStatus"
Write-Host "benchmark_matrix_count=$BenchmarkMatrixCount"
Write-Host "prompt_budget=$PromptBudgetStatus"
Write-Host "asr_model_manifest=$AsrManifestStatus"
Write-Host "tts_model_manifest=$TtsManifestStatus"
Write-Host "Add your remaining visual/voice/model PASS/FAIL notes before archiving the evidence directory."
