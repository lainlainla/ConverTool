param(
    [string]$Preset = "all",
    [string]$OutputRoot = ".\datasets",
    [string]$LeRobotSrc = "",
    [string]$DownloadBackend = "auto",
    [string]$HfEndpoint = "https://huggingface.co",
    [string]$MirrorEndpoint = "https://hf-mirror.com",
    [int]$Workers = 4,
    [switch]$Force,
    [switch]$AutoCloneLeRobot,
    [switch]$SkipDownload,
    [switch]$SkipConvert,
    [switch]$SkipValidate,
    [switch]$SkipOracleValidate,
    [switch]$SkipVideoValidate,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$argsList = @(
    ".\robocoin_hotel_convert.py",
    "--preset", $Preset,
    "--output-root", $OutputRoot,
    "--download-backend", $DownloadBackend,
    "--hf-endpoint", $HfEndpoint,
    "--mirror-endpoint", $MirrorEndpoint,
    "--workers", "$Workers"
)

if ($LeRobotSrc) {
    $argsList += @("--lerobot-src", $LeRobotSrc)
}
if ($Force) {
    $argsList += "--force"
}
if ($AutoCloneLeRobot) {
    $argsList += "--auto-clone-lerobot"
}
if ($SkipDownload) {
    $argsList += "--skip-download"
}
if ($SkipConvert) {
    $argsList += "--skip-convert"
}
if ($SkipValidate) {
    $argsList += "--skip-validate"
}
if ($SkipOracleValidate) {
    $argsList += "--skip-oracle-validate"
}
if ($SkipVideoValidate) {
    $argsList += "--skip-video-validate"
}
if ($DryRun) {
    $argsList += "--dry-run"
}

python @argsList
