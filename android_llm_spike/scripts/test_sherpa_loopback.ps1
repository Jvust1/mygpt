[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$AdbPath,
    [Parameter(Mandatory=$true)][string]$DeviceSerial,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-AdbChecked {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    & $AdbPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "adb command failed: $($Arguments -join ' ')"
    }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path

Invoke-AdbChecked @("-s",$DeviceSerial,"shell","am","force-stop","dev.mygpt.companionv2")
& $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 rm -f files/voice-loopback-result.json files/adb-voice-loopback-gate.txt 2>$null

$Start = & $AdbPath -s $DeviceSerial shell am start -W -n dev.mygpt.companionv2/.DebugVoiceLoopbackActivity 2>&1
$Start | Out-File (Join-Path $OutputDirectory "voice-loopback-start.txt") -Encoding utf8

$ResultText = ""
for ($i = 0; $i -lt 300; $i++) {
    Start-Sleep -Seconds 1
    $Value = & $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/voice-loopback-result.json 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ResultText = ($Value | Out-String)
        if ($ResultText -match '"completed"\s*:\s*(true|false)') {
            break
        }
    }
}

$ResultPath = Join-Path $OutputDirectory "voice-loopback-result.json"
$ResultText | Out-File $ResultPath -Encoding utf8

try {
    $Result = $ResultText | ConvertFrom-Json
}
catch {
    throw "Sherpa voice loopback did not produce valid JSON."
}

if ($Result.schema -ne "mygpt.voice-loopback.v1") {
    throw "Sherpa voice loopback schema mismatch."
}
if ($Result.completed -ne $true) {
    throw ("Sherpa voice loopback failed: " + [string]$Result.error)
}
if ([int64]$Result.tts_samples -le 0 -or
    [int64]$Result.asr_input_samples -le 0 -or
    [int]$Result.tts_sample_rate -le 0 -or
    [string]::IsNullOrWhiteSpace([string]$Result.transcript)) {
    throw "Sherpa voice loopback evidence is incomplete."
}
if ($Result.audio_persisted -ne $false) {
    throw "Sherpa voice loopback violated audio non-persistence evidence."
}

Invoke-AdbChecked @(
    "-s",$DeviceSerial,
    "shell","run-as","dev.mygpt.companionv2",
    "sh","-c","echo PASS > files/adb-voice-loopback-gate.txt"
)

Write-Host ("Sherpa TTS->ASR native loopback PASS · transcript=" + [string]$Result.transcript) -ForegroundColor Green
