param(
    [string]$Python = "python",
    [string]$Venv = ".\.venv",
    [switch]$CloneLeRobot,
    [string]$LeRobotDir = ".\_deps\lerobot",
    [string]$LeRobotRepo = "https://github.com/huggingface/lerobot.git",
    [string]$LeRobotRef = "",
    [switch]$InstallViz
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

function Assert-Command {
    param(
        [string]$Name,
        [string]$Hint
    )
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing command '$Name'. $Hint"
    }
}

Assert-Command $Python "Install Python 3.12 or 3.13, then reopen PowerShell."
Assert-Command "curl" "Install curl or use a PowerShell version that includes curl."

& $Python --version
if ($CloneLeRobot) {
    Assert-Command "git" "Install Git from https://git-scm.com/downloads, then reopen PowerShell."
    & git --version
}

if (-not (Test-Path -LiteralPath $Venv)) {
    & $Python -m venv $Venv
}

$venvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment Python not found: $venvPython"
}

& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r requirements.txt

if ($CloneLeRobot) {
    if (-not (Test-Path -LiteralPath $LeRobotDir)) {
        $parent = Split-Path -Parent $LeRobotDir
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent | Out-Null
        }
        git clone $LeRobotRepo $LeRobotDir
    }

    if ($LeRobotRef) {
        git -C $LeRobotDir fetch --all --tags
        git -C $LeRobotDir checkout $LeRobotRef
    }

    $lerobotDatasetSpec = "$LeRobotDir[dataset]"
    & $venvPython -m pip install -e $lerobotDatasetSpec

    if ($InstallViz) {
        $lerobotVizSpec = "$LeRobotDir[dataset_viz]"
        & $venvPython -m pip install -e $lerobotVizSpec
    }
}
elseif ($InstallViz) {
    & $venvPython -m pip install -r requirements-viz.txt
}

$lerobotSrc = Join-Path $LeRobotDir "src"
Write-Host ""
Write-Host "[OK] Environment is ready."
Write-Host "Activate it with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $lerobotSrc) {
    Write-Host "LeRobot src:"
    Write-Host "  $lerobotSrc"
}
Write-Host "Next dry-run:"
Write-Host "  .\run_all.ps1 -Preset all -OutputRoot .\datasets -DryRun"
