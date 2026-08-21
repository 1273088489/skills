[CmdletBinding()]
param(
    [switch]$SkipModels,
    [switch]$SkipFfmpeg,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$runtimeHome = if ($env:VIDEO_INBOX_HOME) {
    $env:VIDEO_INBOX_HOME
} else {
    Join-Path $env:LOCALAPPDATA "video-inbox"
}
$bin = Join-Path $runtimeHome "bin"
$venvPython = Join-Path $runtimeHome ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $bin | Out-Null

function Find-Uv {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidate = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

Write-Host "==> 1/7 install uv"
$uv = Find-Uv
if (-not $uv -or $Force) {
    Invoke-Expression (Invoke-RestMethod "https://astral.sh/uv/install.ps1")
    $uv = Find-Uv
    if (-not $uv) { throw "uv installation failed" }
}
Write-Host "uv: $uv"

Write-Host "==> 2/7 install Python 3.12"
& $uv python install 3.12
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 installation failed" }

Write-Host "==> 3/7 create virtual environment"
if (-not (Test-Path -LiteralPath $venvPython) -or $Force) {
    & $uv venv $runtimeHome\.venv --python 3.12
    if ($LASTEXITCODE -ne 0) { throw "virtual environment creation failed" }
}

Write-Host "==> 4/7 install faster-whisper"
& $uv pip install --python $venvPython faster-whisper
if ($LASTEXITCODE -ne 0) { throw "faster-whisper installation failed" }

Write-Host "==> 5/7 install yt-dlp"
& $uv tool install --force yt-dlp
if ($LASTEXITCODE -ne 0) { throw "yt-dlp installation failed" }
$ytDlpSource = Join-Path $env:USERPROFILE ".local\bin\yt-dlp.exe"
if (-not (Test-Path -LiteralPath $ytDlpSource)) {
    $ytCommand = Get-Command yt-dlp -ErrorAction SilentlyContinue
    if ($ytCommand) { $ytDlpSource = $ytCommand.Source }
}
if (Test-Path -LiteralPath $ytDlpSource) {
    Copy-Item -LiteralPath $ytDlpSource -Destination (Join-Path $bin "yt-dlp.exe") -Force
    Write-Host "yt-dlp: $(Join-Path $bin 'yt-dlp.exe')"
} else {
    Write-Warning "yt-dlp installed but its exe was not found; add it to PATH manually"
}

Write-Host "==> 6/7 install ffmpeg"
$ffmpegExe = Join-Path $bin "ffmpeg.exe"
if (-not $SkipFfmpeg -and (-not (Test-Path -LiteralPath $ffmpegExe) -or $Force)) {
    $zipPath = Join-Path $env:TEMP "video-inbox-ffmpeg.zip"
    Write-Host "Downloading ffmpeg (~170 MB, may take a few minutes)..."
    curl.exe -L --retry 3 --retry-delay 2 -o $zipPath "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg download failed" }
    $extractRoot = Join-Path $runtimeHome "temp"
    $extractDest = Join-Path $extractRoot "ffmpeg"
    New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
    if (Test-Path -LiteralPath $extractDest) {
        Remove-Item -LiteralPath $extractDest -Recurse -Force
    }
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDest
    $binDir = Get-ChildItem -Path $extractDest -Recurse -Directory -Filter "bin" | Select-Object -First 1
    if (-not $binDir) { throw "no bin directory found in ffmpeg archive" }
    Copy-Item -LiteralPath (Join-Path $binDir.FullName "ffmpeg.exe") -Destination (Join-Path $bin "ffmpeg.exe") -Force
    Copy-Item -LiteralPath (Join-Path $binDir.FullName "ffprobe.exe") -Destination (Join-Path $bin "ffprobe.exe") -Force
} elseif (Test-Path -LiteralPath $ffmpegExe) {
    Write-Host "ffmpeg already present"
}

Write-Host "==> 7/7 ASR model"
if (-not $SkipModels) {
    $legacyModelMarker = Join-Path $runtimeHome "models\Systran\faster-whisper-small"
    $hfModelMarker = Join-Path $runtimeHome "models\models--Systran--faster-whisper-small"
    $modelExists = (Test-Path -LiteralPath $legacyModelMarker) -or (Test-Path -LiteralPath $hfModelMarker)
    if (-not $modelExists -or $Force) {
        Write-Host "Downloading faster-whisper small model (~460 MB, first run takes a while)..."
        & $venvPython (Join-Path $PSScriptRoot "video_inbox_runtime\download_model.py") --model small --download-root (Join-Path $runtimeHome "models")
        if ($LASTEXITCODE -ne 0) { throw "ASR model download failed" }
    } else {
        Write-Host "ASR model already present"
    }
}

Write-Host "==> environment check"
& $venvPython (Join-Path $PSScriptRoot "video_inbox_runtime\main.py") doctor
Write-Host "bootstrap done. Add $bin to PATH or use scripts\video-inbox.ps1 directly."
