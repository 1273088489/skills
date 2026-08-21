[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

$runtimeHome = if ($env:VIDEO_INBOX_HOME) {
    $env:VIDEO_INBOX_HOME
} else {
    Join-Path $env:LOCALAPPDATA "video-inbox"
}

$python = $null
$venvPython = Join-Path $runtimeHome ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
} else {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $python = $command.Source }
}

if (-not $python) {
    Write-Error "Python not found. Run bootstrap.ps1 first to install the runtime."
    exit 1
}

$mainScript = Join-Path $PSScriptRoot "video_inbox_runtime\main.py"
& $python $mainScript @Arguments
exit $LASTEXITCODE
