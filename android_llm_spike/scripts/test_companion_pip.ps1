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
        throw "adb command failed ($LASTEXITCODE): $($Arguments -join ' ')"
    }
}

function Get-ScreenSize {
    $Raw = (& $AdbPath -s $DeviceSerial shell wm size | Out-String)
    if ($Raw -notmatch '(?<w>\d+)x(?<h>\d+)') {
        throw "Unable to parse Android screen size: $Raw"
    }
    return @([int]$Matches["w"], [int]$Matches["h"])
}

function Dump-Ui {
    param([Parameter(Mandatory=$true)][string]$Name)
    $Remote = "/sdcard/mygpt-pip-" + $Name + ".xml"
    $Local = Join-Path $OutputDirectory ("pip-" + $Name + ".xml")
    Invoke-AdbChecked @("-s", $DeviceSerial, "shell", "uiautomator", "dump", $Remote)
    Invoke-AdbChecked @("-s", $DeviceSerial, "pull", $Remote, $Local)
    & $AdbPath -s $DeviceSerial shell rm -f $Remote | Out-Null
    return Get-Content $Local -Raw
}

function Find-PipButton {
    $Size = Get-ScreenSize
    $X = [int]($Size[0] / 2)
    $SwipeStart = [int]($Size[1] * 0.78)
    $SwipeEnd = [int]($Size[1] * 0.28)

    for ($i = 0; $i -lt 12; $i++) {
        $Xml = Dump-Ui ("find-" + $i)
        if ($Xml -match 'content-desc="ENTER_COMPANION_PIP"') {
            return $Xml
        }
        Invoke-AdbChecked @(
            "-s", $DeviceSerial,
            "shell", "input", "swipe",
            "$X", "$SwipeStart", "$X", "$SwipeEnd", "250"
        )
        Start-Sleep -Milliseconds 350
    }
    throw "PiP button not found."
}

function Assert-PipState {
    param([string]$Label)
    $Dump = (& $AdbPath -s $DeviceSerial shell dumpsys activity activities | Out-String)
    $Dump | Out-File (Join-Path $OutputDirectory ("pip-activity-" + $Label + ".txt")) -Encoding utf8

    if ($Dump -notmatch 'dev\.mygpt\.companionv2') {
        throw "Companion V2 is absent from activity state during $Label."
    }

    $Pinned = $Dump -match '(?i)(pictureInPictureMode=true|mPictureInPictureMode=true|mLastReportedPictureInPictureMode=true|WINDOWING_MODE_PINNED|windowingMode=2|mode=PINNED)'
    if (-not $Pinned) {
        throw "Companion V2 did not expose a pinned/PiP activity state during $Label."
    }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Invoke-AdbChecked @(
    "-s", $DeviceSerial,
    "shell", "am", "start", "-W",
    "-n", "dev.mygpt.companionv2/.CompanionV2Activity"
)
Start-Sleep -Seconds 1

$Xml = Find-PipButton
$NodePattern = 'content-desc="ENTER_COMPANION_PIP"[^>]*enabled="(?<enabled>true|false)"[^>]*bounds="\[(?<x1>\d+),(?<y1>\d+)\]\[(?<x2>\d+),(?<y2>\d+)\]"'
if ($Xml -notmatch $NodePattern) {
    # Some Android builds order attributes differently. Parse the full node instead.
    if ($Xml -notmatch '<node[^>]*content-desc="ENTER_COMPANION_PIP"[^>]*/>') {
        throw "PiP node could not be parsed."
    }
    $Node = $Matches[0]
    if ($Node -notmatch 'enabled="(?<enabled>true|false)"') {
        throw "PiP enabled state missing."
    }
    $Enabled = $Matches["enabled"]
    if ($Node -notmatch 'bounds="\[(?<x1>\d+),(?<y1>\d+)\]\[(?<x2>\d+),(?<y2>\d+)\]"') {
        throw "PiP bounds missing."
    }
} else {
    $Enabled = $Matches["enabled"]
}

if ($Enabled -ne "true") {
    throw "PiP button is disabled. Import/restore 3714430278 before running this gate."
}

$X1 = [int]$Matches["x1"]
$Y1 = [int]$Matches["y1"]
$X2 = [int]$Matches["x2"]
$Y2 = [int]$Matches["y2"]
$TapX = [int](($X1 + $X2) / 2)
$TapY = [int](($Y1 + $Y2) / 2)

Invoke-AdbChecked @("-s", $DeviceSerial, "shell", "input", "tap", "$TapX", "$TapY")
Start-Sleep -Seconds 2

Assert-PipState "after-enter"

# Open the synthetic Book app behind the PiP companion.
Invoke-AdbChecked @(
    "-s", $DeviceSerial,
    "shell", "am", "start", "-W",
    "-n", "dev.mygpt.bookcontexttest/.BookContextTestActivity"
)
Start-Sleep -Seconds 2

Assert-PipState "over-book"

$RemoteScreenshot = "/sdcard/mygpt-pip-over-book.png"
$LocalScreenshot = Join-Path $OutputDirectory "pip-over-book.png"
Invoke-AdbChecked @("-s", $DeviceSerial, "shell", "screencap", "-p", $RemoteScreenshot)
Invoke-AdbChecked @("-s", $DeviceSerial, "pull", $RemoteScreenshot, $LocalScreenshot)
& $AdbPath -s $DeviceSerial shell rm -f $RemoteScreenshot | Out-Null

# Return to full Companion UI.
Invoke-AdbChecked @(
    "-s", $DeviceSerial,
    "shell", "am", "start", "-W",
    "-n", "dev.mygpt.companionv2/.CompanionV2Activity"
)
Start-Sleep -Seconds 1

$PersistGateArgs = @(
    "-s", $DeviceSerial,
    "shell", "run-as", "dev.mygpt.companionv2",
    "sh", "-c", "echo PASS > files/adb-pip-gate.txt"
)
Invoke-AdbChecked $PersistGateArgs

"PASS" | Out-File (Join-Path $OutputDirectory "pip-gate.txt") -Encoding utf8
Write-Host "Companion V2 PiP-over-Book gate PASS." -ForegroundColor Green
