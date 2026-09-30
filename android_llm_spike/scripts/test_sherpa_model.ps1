[CmdletBinding()]
param(
    [ValidateSet("asr","tts")][string]$Kind,
    [Parameter(Mandatory=$true)][string]$ArchivePath,
    [Parameter(Mandatory=$true)][string]$AdbPath,
    [Parameter(Mandatory=$true)][string]$DeviceSerial,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-AdbChecked {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    & $AdbPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "adb command failed: $($Arguments -join ' ')" }
}

$Specs=@{
    asr=@{ Bytes=[int64]511274346; Inbox="files/acceptance-inbox/asr-model.tar.bz2"; Ready="ASR_MODEL_READY"; Wait=360 }
    tts=@{ Bytes=[int64]167006755; Inbox="files/acceptance-inbox/tts-model.tar.bz2"; Ready="TTS_MODEL_READY"; Wait=240 }
}
$Spec=$Specs[$Kind]

if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { throw "Archive not found: $ArchivePath" }
$Item=Get-Item -LiteralPath $ArchivePath
if ([int64]$Item.Length -ne [int64]$Spec.Bytes) { throw "Archive byte length mismatch." }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory=(Resolve-Path $OutputDirectory).Path

# Stop all runtime users of the model directory before replacement.
Invoke-AdbChecked @("-s",$DeviceSerial,"shell","am","force-stop","dev.mygpt.companionv2")

$DfText=(& $AdbPath -s $DeviceSerial shell df -k /data | Out-String)
$Lines=@($DfText -split "\r?\n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$DataLine=$Lines | Where-Object { $_ -match "/data\s*$" } | Select-Object -Last 1
if ($null -eq $DataLine -and $Lines.Count -ge 2) { $DataLine=$Lines[-1] }
if ($null -eq $DataLine) { throw "Unable to parse /data free space." }
$Cols=@($DataLine.Trim() -split "\s+")
if ($Cols.Count -lt 4) { throw "Unexpected df output: $DataLine" }
$Available=[int64]$Cols[3]*1024L
$Required=([int64]$Item.Length*2L)+(768L*1024L*1024L)
if ($Available -lt $Required) { throw "Insufficient /data space. available=$Available required=$Required" }

$Remote="/data/local/tmp/mygpt-"+$Kind+"-acceptance.tar.bz2"
try {
    Invoke-AdbChecked @("-s",$DeviceSerial,"push",$Item.FullName,$Remote)
    Invoke-AdbChecked @("-s",$DeviceSerial,"shell","run-as","dev.mygpt.companionv2","mkdir","-p","files/acceptance-inbox")
    $PipeCommand="cat "+$Remote+" | run-as dev.mygpt.companionv2 sh -c 'cat > "+$Spec.Inbox+"'"
    Invoke-AdbChecked @("-s",$DeviceSerial,"shell","sh","-c",$PipeCommand)
    $PrivateBytes=(& $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 stat -c %s $Spec.Inbox | Out-String).Trim()
    if ([int64]$PrivateBytes -ne [int64]$Spec.Bytes) { throw "Private archive byte length mismatch." }
} finally {
    & $AdbPath -s $DeviceSerial shell rm -f $Remote | Out-Null
}

& $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 rm -f files/adb-voice-model-import-result.txt 2>$null
$StartArgs=@("-s",$DeviceSerial,"shell","am","start","-W","-n","dev.mygpt.companionv2/.DebugVoiceModelImportActivity","--es","kind",$Kind)
$Start=& $AdbPath @StartArgs 2>&1
$Start | Out-File (Join-Path $OutputDirectory ("voice-import-start-"+$Kind+".txt")) -Encoding utf8

$ResultText=""
for($i=0;$i -lt $Spec.Wait;$i++){
    Start-Sleep -Seconds 1
    $Value=& $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/adb-voice-model-import-result.txt 2>&1
    if($LASTEXITCODE -eq 0){
        $ResultText=($Value | Out-String)
        if($ResultText -match "schema=mygpt.debug-voice-model-import.v1"){ break }
    }
}
$ResultText | Out-File (Join-Path $OutputDirectory ("voice-import-result-"+$Kind+".txt")) -Encoding utf8
if ($ResultText -notmatch "accepted=true" -or $ResultText -notmatch "hard_identity=PASS") { throw "Voice model import failed: $Kind" }

Invoke-AdbChecked @("-s",$DeviceSerial,"shell","am","force-stop","dev.mygpt.companionv2")
Invoke-AdbChecked @("-s",$DeviceSerial,"shell","am","start","-W","-n","dev.mygpt.companionv2/.CompanionV2Activity")
Start-Sleep -Seconds 1

$Ready=$false
for($i=0;$i -lt 180;$i++){
    $RemoteXml="/sdcard/mygpt-voice-"+$Kind+".xml"
    $LocalXml=Join-Path $OutputDirectory ("voice-"+$Kind+"-"+$i+".xml")
    & $AdbPath -s $DeviceSerial shell uiautomator dump $RemoteXml | Out-Null
    if($LASTEXITCODE -eq 0){
        & $AdbPath -s $DeviceSerial pull $RemoteXml $LocalXml | Out-Null
        & $AdbPath -s $DeviceSerial shell rm -f $RemoteXml | Out-Null
        if(Test-Path $LocalXml){
            $Xml=Get-Content $LocalXml -Raw
            if($Xml -match ('content-desc="'+[regex]::Escape($Spec.Ready)+'"')){ $Ready=$true; break }
        }
    }
    Start-Sleep -Seconds 1
}
if(-not $Ready){ throw "Companion did not restore verified $Kind model." }

$GateFile="adb-voice-model-gate-"+$Kind+".txt"
Invoke-AdbChecked @("-s",$DeviceSerial,"shell","run-as","dev.mygpt.companionv2","sh","-c",("echo PASS > files/"+$GateFile))
Write-Host ("Sherpa "+$Kind+" private import/restore gate PASS") -ForegroundColor Green
