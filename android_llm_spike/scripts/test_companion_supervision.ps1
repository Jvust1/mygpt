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

    $Remote = "/sdcard/mygpt-supervision-" + $Name + ".xml"
    $Local = Join-Path $OutputDirectory ("supervision-" + $Name + ".xml")

    Invoke-AdbChecked @("-s", $DeviceSerial, "shell", "uiautomator", "dump", $Remote)
    Invoke-AdbChecked @("-s", $DeviceSerial, "pull", $Remote, $Local)
    & $AdbPath -s $DeviceSerial shell rm -f $Remote | Out-Null
    return Get-Content $Local -Raw
}

function Find-UiPattern {
    param(
        [Parameter(Mandatory=$true)][string]$Pattern,
        [Parameter(Mandatory=$true)][string]$Name,
        [int]$Attempts = 12
    )

    $Size = Get-ScreenSize
    $X = [int]($Size[0] / 2)
    $SwipeStart = [int]($Size[1] * 0.78)
    $SwipeEnd = [int]($Size[1] * 0.28)

    for ($i = 0; $i -lt $Attempts; $i++) {
        $Xml = Dump-Ui ($Name + "-" + $i)
        if ($Xml -match $Pattern) {
            return $Xml
        }

        Invoke-AdbChecked @(
            "-s", $DeviceSerial,
            "shell", "input", "swipe",
            "$X", "$SwipeStart", "$X", "$SwipeEnd", "250"
        )
        Start-Sleep -Milliseconds 350
    }

    throw "UI pattern not found: $Pattern"
}

function Read-StudyResult {
    $Value = & $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest cat files/adb-study-result.txt 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read adb-study-result.txt: $($Value | Out-String)"
    }
    return ($Value | Out-String)
}

function Send-StudyCommand {
    param(
        [Parameter(Mandatory=$true)][string]$Action,
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string]$ExpectedStatus,
        [Parameter(Mandatory=$true)][string]$ExpectedCue,
        [Parameter(Mandatory=$true)][string]$ExpectedOptIn
    )

    & $AdbPath -s $DeviceSerial exec-out run-as dev.mygpt.bookcontexttest rm -f files/adb-study-result.txt 2>$null

    $Args = @(
        "-s", $DeviceSerial,
        "shell", "am", "broadcast",
        "-n", "dev.mygpt.bookcontexttest/.BookContextTestCommandReceiver",
        "-a", $Action
    )
    $Command = & $AdbPath @Args 2>&1
    $Command | Out-File (Join-Path $OutputDirectory ("study-" + $Label + "-command.txt")) -Encoding utf8

    Start-Sleep -Seconds 1

    $Result = Read-StudyResult
    $Result | Out-File (Join-Path $OutputDirectory ("study-" + $Label + "-result.txt")) -Encoding utf8
    if ($Result -notmatch "accepted=true") {
        throw "Study event was rejected: $Label"
    }

    $FindArgs = @{
        Pattern = "SUPERVISION_STATUS=" + [regex]::Escape($ExpectedStatus)
        Name = $Label + "-status"
    }
    $Xml = Find-UiPattern @FindArgs

    if ($Xml -notmatch ("SUPERVISION_CUE=" + [regex]::Escape($ExpectedCue))) {
        throw "Unexpected supervision cue after $Label. Expected $ExpectedCue"
    }

    if ($Xml -notmatch ("SUPERVISION_OPT_IN=" + [regex]::Escape($ExpectedOptIn))) {
        throw "Unexpected supervision opt-in after $Label. Expected $ExpectedOptIn"
    }

    Write-Host ("Supervision " + $Label + " PASS: " + $ExpectedCue + " optIn=" + $ExpectedOptIn) -ForegroundColor Green
}

function Click-SupervisionOptIn {
    $FindArgs = @{
        Pattern = 'content-desc="TOGGLE_STUDY_SUPERVISION"'
        Name = "toggle-find"
    }
    $Xml = Find-UiPattern @FindArgs

    $Pattern = 'content-desc="TOGGLE_STUDY_SUPERVISION"[^>]*bounds="\[(?<x1>\d+),(?<y1>\d+)\]\[(?<x2>\d+),(?<y2>\d+)\]"'
    if ($Xml -notmatch $Pattern) {
        throw "Supervision button was found but bounds could not be parsed."
    }

    $X1 = [int]$Matches["x1"]
    $Y1 = [int]$Matches["y1"]
    $X2 = [int]$Matches["x2"]
    $Y2 = [int]$Matches["y2"]

    if ($X2 -le $X1 -or $Y2 -le $Y1) {
        throw "Supervision button has invalid bounds."
    }

    $TapX = [int](($X1 + $X2) / 2)
    $TapY = [int](($Y1 + $Y2) / 2)

    Invoke-AdbChecked @("-s", $DeviceSerial, "shell", "input", "tap", "$TapX", "$TapY")
    Start-Sleep -Seconds 1

    $ConfirmArgs = @{
        Pattern = 'SUPERVISION_OPT_IN=true'
        Name = "opt-in"
    }
    Find-UiPattern @ConfirmArgs | Out-Null
    Write-Host "Local MyGPT supervision opt-in tap PASS." -ForegroundColor Green
}

function Run-Step {
    param(
        [string]$Action,
        [string]$Label,
        [string]$Status,
        [string]$Cue,
        [string]$OptIn
    )

    $Args = @{
        Action = $Action
        Label = $Label
        ExpectedStatus = $Status
        ExpectedCue = $Cue
        ExpectedOptIn = $OptIn
    }
    Send-StudyCommand @Args
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Invoke-AdbChecked @(
    "-s", $DeviceSerial,
    "shell", "am", "start", "-W",
    "-n", "dev.mygpt.companionv2/.CompanionV2Activity"
)
Start-Sleep -Seconds 1

Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_START_V1" "start" "ACCEPTED_SESSION_STARTED" "QUIET" "false"
Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_REPEATED_ERROR_V1" "repeated-before-opt-in" "ACCEPTED_PRACTICE_REPEATED_ERROR" "QUIET" "false"

Click-SupervisionOptIn

Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_REPEATED_ERROR_V1" "repeated-after-opt-in" "ACCEPTED_PRACTICE_REPEATED_ERROR" "GENTLE_CHECK_IN" "true"
Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_HELP_V1" "help" "ACCEPTED_HELP_REQUESTED" "NEEDS_INPUT" "true"
Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_PAUSE_V1" "pause" "ACCEPTED_SESSION_PAUSED" "PAUSED" "true"
Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_RESUME_V1" "resume" "ACCEPTED_SESSION_RESUMED" "QUIET" "true"
Run-Step "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_END_V1" "end" "ACCEPTED_SESSION_ENDED" "QUIET" "false"

"PASS" | Out-File (Join-Path $OutputDirectory "supervision-gate.txt") -Encoding utf8
Write-Host "Signed Book quiet-first supervision gate PASS." -ForegroundColor Green
