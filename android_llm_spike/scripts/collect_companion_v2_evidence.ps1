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

$SourceHead | Out-File (Join-Path $OutputDirectory "source-head.txt") -Encoding utf8
$SourceBranch | Out-File (Join-Path $OutputDirectory "source-branch.txt") -Encoding utf8
& git -C $RepoRoot status --porcelain --untracked-files=no |
    Out-File (Join-Path $OutputDirectory "source-dirty.txt") -Encoding utf8
& $Adb -s $DeviceSerial shell dumpsys package dev.mygpt.companionv2 |
    Out-File (Join-Path $OutputDirectory "dumpsys-companion-package.txt") -Encoding utf8

& $Adb -s $DeviceSerial shell dumpsys package dev.mygpt.bookcontexttest |
    Out-File (Join-Path $OutputDirectory "dumpsys-book-sender-package.txt") -Encoding utf8

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

$Benchmark = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/benchmark-last.txt 2>&1
if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($Benchmark | Out-String))) {
    $Benchmark | Out-File (Join-Path $OutputDirectory "benchmark-last.txt") -Encoding utf8
    Write-Host "Benchmark report captured." -ForegroundColor Green
}
else {
    $Benchmark | Out-File (Join-Path $OutputDirectory "benchmark-capture-error.txt") -Encoding utf8
    Write-Host "No benchmark report captured yet. Run the in-app benchmark first." -ForegroundColor Yellow
}

$BookResult = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest cat files/adb-book-result.txt 2>&1
$BookResult | Out-File (Join-Path $OutputDirectory "book-sender-last-result.txt") -Encoding utf8

$PrivateListing = & $Adb -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 sh -c "find files -type f -print" 2>&1
$PrivateListingText = ($PrivateListing | Out-String)
$PrivateListing | Out-File (Join-Path $OutputDirectory "app-private-files.txt") -Encoding utf8

$AudioLeakPattern = '\.(wav|pcm|raw|mp3|m4a|aac|ogg)$Packages = & $Adb -s $DeviceSerial shell pm list packages dev.mygpt
$Packages | Out-File (Join-Path $OutputDirectory "mygpt-packages.txt") -Encoding utf8

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RemoteScreenshot = "/sdcard/mygpt-companion-v2-" + $Timestamp + ".png"
$LocalScreenshot = Join-Path $OutputDirectory "companion-current.png"
& $Adb -s $DeviceSerial shell screencap -p $RemoteScreenshot | Out-Null
if ($LASTEXITCODE -eq 0) {
    & $Adb -s $DeviceSerial pull $RemoteScreenshot $LocalScreenshot | Out-Null
    & $Adb -s $DeviceSerial shell rm -f $RemoteScreenshot | Out-Null
}

Write-Host "Evidence collected: $OutputDirectory" -ForegroundColor Green
Write-Host "Add your PASS/FAIL notes before archiving the evidence directory."

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

Write-Host "Evidence collected: $OutputDirectory" -ForegroundColor Green
Write-Host "Add your PASS/FAIL notes before archiving the evidence directory."
