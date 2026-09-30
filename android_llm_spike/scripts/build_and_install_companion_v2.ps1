[CmdletBinding()]
param(
    [string]$DeviceSerial = "",
    [switch]$SkipInstall,
    [switch]$SkipSubmoduleUpdate,
    [switch]$SkipSdkInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $ProjectDir "..")).Path

Write-Host "Repo:    $RepoRoot" -ForegroundColor Cyan
Write-Host "Project: $ProjectDir" -ForegroundColor Cyan

Require-Command "git"
Require-Command "java"

if (-not $SkipSubmoduleUpdate) {
    Write-Host "Updating pinned submodules..." -ForegroundColor Cyan
    Invoke-Checked "git" @("-C", $RepoRoot, "submodule", "update", "--init", "--recursive")
}

$LlamaDir = Join-Path $RepoRoot "third_party\llama.cpp\upstream"
$SherpaDir = Join-Path $RepoRoot "third_party\sherpa-onnx\upstream"

if (-not (Test-Path (Join-Path $LlamaDir "CMakeLists.txt"))) {
    throw "llama.cpp submodule missing. Run git submodule update --init --recursive."
}
if (-not (Test-Path (Join-Path $SherpaDir "CMakeLists.txt"))) {
    throw "sherpa-onnx submodule missing. Run git submodule update --init --recursive."
}

$LlamaHead = (& git -C $LlamaDir rev-parse HEAD).Trim()
$SherpaHead = (& git -C $SherpaDir rev-parse HEAD).Trim()
if ($LlamaHead -ne "ba0ba54d93b25faf1e149f4ccedd3e9d84798563") {
    throw "Unexpected llama.cpp pin: $LlamaHead"
}
if ($SherpaHead -ne "040afe360a38e25daaa325ce8889abf93ea02609") {
    throw "Unexpected sherpa-onnx pin: $SherpaHead"
}

$SdkRoot = $env:ANDROID_HOME
if ([string]::IsNullOrWhiteSpace($SdkRoot)) {
    $SdkRoot = $env:ANDROID_SDK_ROOT
}
if ([string]::IsNullOrWhiteSpace($SdkRoot) -or -not (Test-Path $SdkRoot)) {
    throw "ANDROID_HOME or ANDROID_SDK_ROOT must point to an installed Android SDK."
}
$env:ANDROID_HOME = $SdkRoot
$env:ANDROID_SDK_ROOT = $SdkRoot

$SdkManagerCandidates = @(
    (Join-Path $SdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"),
    (Join-Path $SdkRoot "cmdline-tools\bin\sdkmanager.bat"),
    (Join-Path $SdkRoot "tools\bin\sdkmanager.bat")
)
$SdkManager = $SdkManagerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $SdkManager) {
    throw "sdkmanager.bat not found. Install Android SDK Command-line Tools."
}

if (-not $SkipSdkInstall) {
    Write-Host "Ensuring NDK 29.0.13113456 and CMake 3.31.6..." -ForegroundColor Cyan
    Invoke-Checked $SdkManager @("ndk;29.0.13113456", "cmake;3.31.6")
}

$Gradlew = Join-Path $ProjectDir "gradlew.bat"
if (-not (Test-Path $Gradlew)) {
    throw "gradlew.bat missing: $Gradlew"
}

Write-Host "Building Companion V2 local stack..." -ForegroundColor Cyan
$GradleArgs = @(
    ":llama-lib:assembleRelease",
    ":bridge:assembleRelease",
    ":app:assembleDebug",
    ":companion:assembleDebug",
    ":book-sender-test:assembleDebug",
    "--no-daemon",
    "--stacktrace"
)
Push-Location $ProjectDir
try {
    Invoke-Checked $Gradlew $GradleArgs
}
finally {
    Pop-Location
}

$CompanionApk = Join-Path $ProjectDir "companion\build\outputs\apk\debug\companion-debug.apk"
$SenderApk = Join-Path $ProjectDir "book-sender-test\build\outputs\apk\debug\book-sender-test-debug.apk"
$LocalLlmApk = Join-Path $ProjectDir "app\build\outputs\apk\debug\app-debug.apk"
$BridgeAar = Join-Path $ProjectDir "bridge\build\outputs\aar\bridge-release.aar"

foreach ($Path in @($CompanionApk, $SenderApk, $LocalLlmApk, $BridgeAar)) {
    if (-not (Test-Path $Path)) {
        throw "Expected build artifact missing: $Path"
    }
}

$BuildTools = Get-ChildItem (Join-Path $SdkRoot "build-tools") -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1
if (-not $BuildTools) {
    throw "Android build-tools not found."
}
$ApkSigner = Join-Path $BuildTools.FullName "apksigner.bat"
if (-not (Test-Path $ApkSigner)) {
    throw "apksigner.bat not found: $ApkSigner"
}

$CompanionCertLine = (& $ApkSigner verify --print-certs $CompanionApk |
    Select-String "Signer #1 certificate SHA-256 digest").Line
$SenderCertLine = (& $ApkSigner verify --print-certs $SenderApk |
    Select-String "Signer #1 certificate SHA-256 digest").Line

if ([string]::IsNullOrWhiteSpace($CompanionCertLine) -or
    [string]::IsNullOrWhiteSpace($SenderCertLine)) {
    throw "Unable to read APK signer SHA-256 digest."
}
if ($CompanionCertLine.Trim() -ne $SenderCertLine.Trim()) {
    throw "Companion V2 and Book sender APKs are not signed by the same certificate."
}

Write-Host "Same-signature check PASS" -ForegroundColor Green
Write-Host $CompanionCertLine.Trim()

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceDir = Join-Path $ProjectDir ("device_evidence\" + $Timestamp)
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null

Get-FileHash $CompanionApk -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $EvidenceDir "companion-sha256.txt") -Encoding utf8
Get-FileHash $SenderApk -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $EvidenceDir "book-sender-sha256.txt") -Encoding utf8
$CompanionCertLine | Out-File (Join-Path $EvidenceDir "companion-cert.txt") -Encoding utf8
$SenderCertLine | Out-File (Join-Path $EvidenceDir "book-sender-cert.txt") -Encoding utf8

if ($SkipInstall) {
    Write-Host "Build complete. Device install skipped." -ForegroundColor Yellow
    Write-Host "Evidence: $EvidenceDir"
    exit 0
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

Write-Host "Device: $DeviceSerial" -ForegroundColor Cyan

Write-Host "Installing Companion V2 first..." -ForegroundColor Cyan
Invoke-Checked $Adb @("-s", $DeviceSerial, "install", "-r", $CompanionApk)

Write-Host "Installing same-signature Book test sender..." -ForegroundColor Cyan
Invoke-Checked $Adb @("-s", $DeviceSerial, "install", "-r", $SenderApk)

& $Adb -s $DeviceSerial shell dumpsys package dev.mygpt.companionv2 |
    Out-File (Join-Path $EvidenceDir "dumpsys-companion-package.txt") -Encoding utf8
& $Adb -s $DeviceSerial shell dumpsys package dev.mygpt.bookcontexttest |
    Out-File (Join-Path $EvidenceDir "dumpsys-book-sender-package.txt") -Encoding utf8

Write-Host "Launching Companion V2..." -ForegroundColor Cyan
& $Adb -s $DeviceSerial shell monkey -p dev.mygpt.companionv2 -c android.intent.category.LAUNCHER 1 | Out-Null
Start-Sleep -Seconds 2

$Pid = (& $Adb -s $DeviceSerial shell pidof dev.mygpt.companionv2).Trim()
if (-not [string]::IsNullOrWhiteSpace($Pid)) {
    & $Adb -s $DeviceSerial shell dumpsys meminfo dev.mygpt.companionv2 |
        Out-File (Join-Path $EvidenceDir "meminfo-before-models.txt") -Encoding utf8
    & $Adb -s $DeviceSerial logcat -d --pid=$Pid -v threadtime |
        Out-File (Join-Path $EvidenceDir "logcat-companion.txt") -Encoding utf8
}

& $Adb -s $DeviceSerial shell dumpsys thermalservice |
    Out-File (Join-Path $EvidenceDir "thermal-before-models.txt") -Encoding utf8

$NegativeArgs = @(
    "-s", $DeviceSerial,
    "shell", "am", "broadcast",
    "-a", "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1",
    "-p", "dev.mygpt.companionv2",
    "--es", "session_id", "shell-test",
    "--el", "sequence", "1"
)
$NegativeBroadcast = & $Adb @NegativeArgs 2>&1
$NegativeBroadcast |
    Out-File (Join-Path $EvidenceDir "negative-shell-book-broadcast.txt") -Encoding utf8

Write-Host ""
Write-Host "Build/install/signature checks complete." -ForegroundColor Green
Write-Host "Evidence directory: $EvidenceDir" -ForegroundColor Green
Write-Host ""
Write-Host "Manual device gates:" -ForegroundColor Yellow
Write-Host "1. Open Book Context Test Sender -> new session -> send fresh Book context."
Write-Host "2. Return to Companion V2; Book status should show synthetic-book + section."
Write-Host "3. Import decrypted 3714430278.zip."
Write-Host "4. Import a compatible GGUF and load the local model."
Write-Host "5. Import ASR package sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2."
Write-Host "6. Optional TTS: import vits-melo-tts-zh_en.tar.bz2 and enable local speech replies."
Write-Host "7. Test typed chat, voice, emotion-driven Spine motion, memory commands and clear-chat."


Write-Host "After manual testing, run the final evidence collector:" -ForegroundColor Cyan
Write-Host "powershell -ExecutionPolicy Bypass -File .\\android_llm_spike\\scripts\\collect_companion_v2_evidence.ps1"
