[CmdletBinding()]
param(
    [string]$DeviceSerial = "",
    [switch]$SkipInstall,
    [switch]$SkipSubmoduleUpdate,
    [switch]$SkipSdkInstall,
    [switch]$AllowDirty
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

$SourceHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$SourceBranch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
$DirtyLines = @(& git -C $RepoRoot status --porcelain --untracked-files=no)

if ($DirtyLines.Count -gt 0 -and -not $AllowDirty) {
    throw "Tracked worktree changes detected. Commit/stash them or pass -AllowDirty for an intentionally non-reproducible build."
}

$JavaVersionOutput = (& java -version 2>&1 | Out-String)
$JavaMajor = $null
if ($JavaVersionOutput -match 'version\s+"(?<major>\d+)') {
    $JavaMajor = [int]$Matches["major"]
}
elseif ($JavaVersionOutput -match 'openjdk\s+(?<major>\d+)') {
    $JavaMajor = [int]$Matches["major"]
}
if ($null -eq $JavaMajor -or $JavaMajor -lt 17) {
    throw "JDK 17+ is required. Detected: $JavaVersionOutput"
}

Write-Host "Source:  $SourceBranch @ $SourceHead" -ForegroundColor Cyan
Write-Host "Java:    major $JavaMajor" -ForegroundColor Cyan

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
    Write-Host "Ensuring Android 36, build-tools 36.0.0, platform-tools, NDK and CMake..." -ForegroundColor Cyan
    Invoke-Checked $SdkManager @(
        "platform-tools",
        "platforms;android-36",
        "build-tools;36.0.0",
        "ndk;29.0.13113456",
        "cmake;3.31.6"
    )
}

$env:ANDROID_NDK_HOME = Join-Path $SdkRoot "ndk\29.0.13113456"

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
    ":book-client-sdk:assembleRelease",
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
$BookSdkAar = Join-Path $ProjectDir "book-client-sdk\build\outputs\aar\book-client-sdk-release.aar"

foreach ($Path in @($CompanionApk, $SenderApk, $LocalLlmApk, $BridgeAar, $BookSdkAar)) {
    if (-not (Test-Path $Path)) {
        throw "Expected build artifact missing: $Path"
    }
}

$PreferredBuildTools = Join-Path $SdkRoot "build-tools\36.0.0"
if (Test-Path $PreferredBuildTools) {
    $BuildTools = Get-Item $PreferredBuildTools
}
else {
    $BuildTools = Get-ChildItem (Join-Path $SdkRoot "build-tools") -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1
}
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

$SourceHead | Out-File (Join-Path $EvidenceDir "source-head.txt") -Encoding utf8
$SourceBranch | Out-File (Join-Path $EvidenceDir "source-branch.txt") -Encoding utf8
$DirtyLines | Out-File (Join-Path $EvidenceDir "source-dirty.txt") -Encoding utf8
$JavaVersionOutput | Out-File (Join-Path $EvidenceDir "java-version.txt") -Encoding utf8
$SdkRoot | Out-File (Join-Path $EvidenceDir "android-sdk-root.txt") -Encoding utf8
$LlamaHead | Out-File (Join-Path $EvidenceDir "llama-pin.txt") -Encoding utf8
$SherpaHead | Out-File (Join-Path $EvidenceDir "sherpa-pin.txt") -Encoding utf8

Get-FileHash $CompanionApk -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $EvidenceDir "companion-sha256.txt") -Encoding utf8
Get-FileHash $SenderApk -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $EvidenceDir "book-sender-sha256.txt") -Encoding utf8
Get-FileHash $BookSdkAar -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $EvidenceDir "book-client-sdk-sha256.txt") -Encoding utf8
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


$NowMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$ExpiresMs = $NowMs + 120000
$DummySha = ("a" * 64)

$NegativeArgs = @(
    "-s", $DeviceSerial,
    "shell", "am", "broadcast",
    "-n", "dev.mygpt.companionv2/.BookContextReceiver",
    "-a", "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1",
    "--es", "session_id", "shell-test",
    "--el", "sequence", "1",
    "--es", "course_id", "functional-analysis-test",
    "--es", "book_id", "synthetic-book",
    "--es", "book_version", "test@v1",
    "--es", "section_id", "ch1-s1",
    "--es", "source_id", "shell-source",
    "--es", "source_sha256", $DummySha,
    "--es", "mode", "learn",
    "--el", "captured_at_ms", "$NowMs",
    "--el", "expires_at_ms", "$ExpiresMs",
    "--es", "title", "Shell negative test",
    "--es", "text", "Valid-shaped synthetic context from adb shell; must not be accepted."
)
$NegativeBroadcast = & $Adb @NegativeArgs 2>&1
$NegativeText = ($NegativeBroadcast | Out-String)
$NegativeText | Out-File (Join-Path $EvidenceDir "negative-shell-book-broadcast.txt") -Encoding utf8

if ($NegativeText -match "result=-1") {
    throw "SECURITY FAILURE: adb shell Book context was accepted by Companion V2."
}
Write-Host "Book shell-origin negative gate did not return RESULT_OK." -ForegroundColor Green

$SenderActivityArgs = @(
    "-s", $DeviceSerial,
    "shell", "am", "start", "-W",
    "-n", "dev.mygpt.bookcontexttest/.BookContextTestActivity"
)
Invoke-Checked $Adb $SenderActivityArgs

& $Adb -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest rm -f files/adb-book-result.txt 2>$null

$PositiveCommandArgs = @(
    "-s", $DeviceSerial,
    "shell", "am", "broadcast",
    "-n", "dev.mygpt.bookcontexttest/.BookContextTestCommandReceiver",
    "-a", "dev.mygpt.bookcontexttest.action.AUTOMATED_SEND_CONTEXT_V1"
)
$PositiveCommand = & $Adb @PositiveCommandArgs 2>&1
$PositiveCommand | Out-File (Join-Path $EvidenceDir "positive-book-command.txt") -Encoding utf8
Start-Sleep -Seconds 2

$PositiveBook = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest cat files/adb-book-result.txt 2>&1
$PositiveBookText = ($PositiveBook | Out-String)
$PositiveBookText | Out-File (Join-Path $EvidenceDir "positive-book-result.txt") -Encoding utf8
if ($PositiveBookText -notmatch "accepted=true") {
    throw "Same-signature Book context gate failed. See positive-book-result.txt."
}
Write-Host "Same-signature Book context delivery PASS." -ForegroundColor Green

$CompanionActivityArgs = @(
    "-s", $DeviceSerial,
    "shell", "am", "start", "-W",
    "-n", "dev.mygpt.companionv2/.CompanionV2Activity"
)
Invoke-Checked $Adb $CompanionActivityArgs
Start-Sleep -Seconds 1

$PositiveUiRemote = "/sdcard/mygpt-book-positive.xml"
$PositiveUiLocal = Join-Path $EvidenceDir "book-positive-ui.xml"
Invoke-Checked $Adb @("-s", $DeviceSerial, "shell", "uiautomator", "dump", $PositiveUiRemote)
Invoke-Checked $Adb @("-s", $DeviceSerial, "pull", $PositiveUiRemote, $PositiveUiLocal)
& $Adb -s $DeviceSerial shell rm -f $PositiveUiRemote | Out-Null

$PositiveUiText = Get-Content $PositiveUiLocal -Raw
if ($PositiveUiText -notmatch "synthetic-book") {
    throw "Companion UI did not expose the accepted synthetic Book context."
}
Write-Host "Companion Book status UI PASS." -ForegroundColor Green

Write-Host "Running signed Book quiet-first supervision gate..." -ForegroundColor Cyan
$SupervisionScript = Join-Path $ScriptDir "test_companion_supervision.ps1"
if (-not (Test-Path $SupervisionScript)) {
    throw "Supervision acceptance script missing: $SupervisionScript"
}
& $SupervisionScript -AdbPath $Adb -DeviceSerial $DeviceSerial -OutputDirectory $EvidenceDir
if ($LASTEXITCODE -ne 0) {
    throw "Supervision acceptance script failed."
}

Invoke-Checked $Adb $SenderActivityArgs

$ClearCommandArgs = @(
    "-s", $DeviceSerial,
    "shell", "am", "broadcast",
    "-n", "dev.mygpt.bookcontexttest/.BookContextTestCommandReceiver",
    "-a", "dev.mygpt.bookcontexttest.action.AUTOMATED_CLEAR_CONTEXT_V1"
)
$ClearCommand = & $Adb @ClearCommandArgs 2>&1
$ClearCommand | Out-File (Join-Path $EvidenceDir "clear-book-command.txt") -Encoding utf8
Start-Sleep -Seconds 2

$ClearBook = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest cat files/adb-book-result.txt 2>&1
$ClearBookText = ($ClearBook | Out-String)
$ClearBookText | Out-File (Join-Path $EvidenceDir "clear-book-result.txt") -Encoding utf8
if ($ClearBookText -notmatch "accepted=true") {
    throw "Same-signature Book clear gate failed. See clear-book-result.txt."
}

Invoke-Checked $Adb $CompanionActivityArgs
Start-Sleep -Seconds 1

$ClearUiRemote = "/sdcard/mygpt-book-clear.xml"
$ClearUiLocal = Join-Path $EvidenceDir "book-clear-ui.xml"
Invoke-Checked $Adb @("-s", $DeviceSerial, "shell", "uiautomator", "dump", $ClearUiRemote)
Invoke-Checked $Adb @("-s", $DeviceSerial, "pull", $ClearUiRemote, $ClearUiLocal)
& $Adb -s $DeviceSerial shell rm -f $ClearUiRemote | Out-Null

$ClearUiText = Get-Content $ClearUiLocal -Raw
if ($ClearUiText -notmatch "BOOK_CONTEXT_UNAVAILABLE") {
    throw "Companion UI did not show the cleared Book context state."
}
Write-Host "Same-signature Book clear + UI gate PASS." -ForegroundColor Green

Write-Host ""
Write-Host "Build/install/signature checks complete." -ForegroundColor Green
Write-Host "Evidence directory: $EvidenceDir" -ForegroundColor Green
Write-Host ""
Write-Host "Automated gates completed: signatures + Book context + quiet-first supervision + clear." -ForegroundColor Green
Write-Host "Remaining manual/device gates:" -ForegroundColor Yellow
Write-Host "1. Import decrypted 3714430278.zip."
Write-Host "   Then run: powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\test_companion_pip.ps1 -AdbPath \"$Adb\" -DeviceSerial \"$DeviceSerial\" -OutputDirectory \"$EvidenceDir\""
Write-Host "2. Import a compatible GGUF and load the local model."
Write-Host "3. Run the in-app llama benchmark."
Write-Host "4. Import ASR package sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2."
Write-Host "5. Optional TTS: import vits-melo-tts-zh_en.tar.bz2 and enable local speech replies."
Write-Host "6. Test typed chat, voice, emotion-driven Spine motion, memory commands and clear-chat."


Write-Host "After manual testing, run the final evidence collector:" -ForegroundColor Cyan
Write-Host "powershell -ExecutionPolicy Bypass -File .\\android_llm_spike\\scripts\\collect_companion_v2_evidence.ps1"
