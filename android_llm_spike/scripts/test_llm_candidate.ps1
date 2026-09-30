[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ModelPath,
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

$Candidates = @{
    speed = @{ Bytes=[int64]563036064; Sha256="57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf" }
    balanced = @{ Bytes=[int64]1282439264; Sha256="d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5" }
    quality = @{ Bytes=[int64]2497280640; Sha256="ab27b9bfa375a178d6cba48f3ad892b94b7739659dcc7aae8058ce0ffed6b328" }
}

if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) { throw "GGUF not found: $ModelPath" }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$Item = Get-Item -LiteralPath $ModelPath
$Sha = (Get-FileHash -LiteralPath $ModelPath -Algorithm SHA256).Hash.ToLowerInvariant()
$CandidateId = $null
$Spec = $null
foreach ($Entry in $Candidates.GetEnumerator()) {
    if ($Entry.Value.Sha256 -eq $Sha) { $CandidateId=$Entry.Key; $Spec=$Entry.Value; break }
}
if ($null -eq $Spec) { throw "Model is not a fixed benchmark candidate: $Sha" }
if ([int64]$Item.Length -ne [int64]$Spec.Bytes) { throw "Candidate byte length mismatch." }

$RemoteTemp = "/data/local/tmp/mygpt-acceptance-" + $Sha.Substring(0,16) + ".gguf"
try {
    Invoke-AdbChecked @("-s",$DeviceSerial,"push",$Item.FullName,$RemoteTemp)
    Invoke-AdbChecked @("-s",$DeviceSerial,"shell","run-as","dev.mygpt.companionv2","mkdir","-p","files/acceptance-inbox")
    Invoke-AdbChecked @("-s",$DeviceSerial,"shell","run-as","dev.mygpt.companionv2","cp",$RemoteTemp,"files/acceptance-inbox/model.gguf")
} finally {
    & $AdbPath -s $DeviceSerial shell rm -f $RemoteTemp | Out-Null
}

$BroadcastArgs=@("-s",$DeviceSerial,"shell","am","broadcast","-n","dev.mygpt.companionv2/.DebugModelImportReceiver","-a","dev.mygpt.companionv2.debug.IMPORT_ACCEPTANCE_MODEL_V1")
$Broadcast=& $AdbPath @BroadcastArgs 2>&1
$Broadcast | Out-File (Join-Path $OutputDirectory ("llm-import-broadcast-"+$CandidateId+".txt")) -Encoding utf8
Start-Sleep -Seconds 1
$Result=& $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat files/adb-model-import-result.txt 2>&1
$ResultText=($Result | Out-String)
$Result | Out-File (Join-Path $OutputDirectory ("llm-import-result-"+$CandidateId+".txt")) -Encoding utf8
if ($ResultText -notmatch "accepted=true" -or $ResultText -notmatch ("candidate="+$CandidateId)) { throw "Debug model import failed." }

Invoke-AdbChecked @("-s",$DeviceSerial,"shell","am","force-stop","dev.mygpt.companionv2")
Invoke-AdbChecked @("-s",$DeviceSerial,"shell","am","start","-W","-n","dev.mygpt.companionv2/.CompanionV2Activity")
Start-Sleep -Seconds 1

function Dump-Ui([string]$Name) {
    $Remote="/sdcard/mygpt-llm-"+$Name+".xml"
    $Local=Join-Path $OutputDirectory ("llm-"+$Name+".xml")
    Invoke-AdbChecked @("-s",$DeviceSerial,"shell","uiautomator","dump",$Remote)
    Invoke-AdbChecked @("-s",$DeviceSerial,"pull",$Remote,$Local)
    & $AdbPath -s $DeviceSerial shell rm -f $Remote | Out-Null
    return Get-Content $Local -Raw
}

function Find-Tap([string]$Desc,[int]$MaxSwipes=14) {
    $Size=(& $AdbPath -s $DeviceSerial shell wm size | Out-String)
    if ($Size -notmatch "(?<w>\d+)x(?<h>\d+)") { throw "Cannot parse screen size." }
    $X=[int]([int]$Matches["w"]/2); $H=[int]$Matches["h"]; $Y1=[int]($H*0.78); $Y2=[int]($H*0.28)
    for($i=0;$i -lt $MaxSwipes;$i++){
        $Xml=Dump-Ui ("find-"+$Desc+"-"+$i)
        if($Xml -match ('<node[^>]*content-desc="'+[regex]::Escape($Desc)+'"[^>]*/>')){
            $Node=$Matches[0]
            if($Node -notmatch 'enabled="true"'){ throw "$Desc is disabled." }
            if($Node -notmatch 'bounds="\[(?<x1>\d+),(?<y1>\d+)\]\[(?<x2>\d+),(?<y2>\d+)\]"'){ throw "Cannot parse bounds." }
            $TapX=[int](([int]$Matches["x1"]+[int]$Matches["x2"])/2); $TapY=[int](([int]$Matches["y1"]+[int]$Matches["y2"])/2)
            Invoke-AdbChecked @("-s",$DeviceSerial,"shell","input","tap","$TapX","$TapY"); return
        }
        Invoke-AdbChecked @("-s",$DeviceSerial,"shell","input","swipe","$X","$Y1","$X","$Y2","250")
        Start-Sleep -Milliseconds 300
    }
    throw "UI control not found: $Desc"
}

Find-Tap "LOAD_LOCAL_MODEL"
$Ready=$false
for($i=0;$i -lt 120;$i++){
    Start-Sleep -Seconds 1
    $Xml=Dump-Ui ("wait-load-"+$i)
    if($Xml -match '<node[^>]*content-desc="RUN_LOCAL_BENCHMARK"[^>]*enabled="true"[^>]*/>'){ $Ready=$true; break }
    if($Xml -match "模型加载失败"){ throw "Local model load failed." }
}
if(-not $Ready){ throw "Timed out waiting for model load." }

Find-Tap "RUN_LOCAL_BENCHMARK"
$Done=$false
for($i=0;$i -lt 300;$i++){
    Start-Sleep -Seconds 1
    $Xml=Dump-Ui ("wait-benchmark-"+$i)
    if($Xml -match "基准完成"){ $Done=$true; break }
    if($Xml -match "基准失败"){ throw "Local benchmark failed." }
}
if(-not $Done){ throw "Timed out waiting for benchmark." }

$ReportName="benchmark-"+$Sha.Substring(0,16)+".txt"
$Report=& $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.companionv2 cat ("files/"+$ReportName) 2>&1
$ReportText=($Report | Out-String)
$Report | Out-File (Join-Path $OutputDirectory $ReportName) -Encoding utf8
if($ReportText -notmatch ("candidate_id="+$CandidateId) -or $ReportText -notmatch ("model_sha256="+$Sha)){ throw "Benchmark report identity mismatch." }

$GateFile="adb-llm-gate-"+$CandidateId+".txt"
Invoke-AdbChecked @("-s",$DeviceSerial,"shell","run-as","dev.mygpt.companionv2","sh","-c",("echo PASS > files/"+$GateFile))
Write-Host "Local GGUF import/load/benchmark gate PASS: $CandidateId" -ForegroundColor Green
