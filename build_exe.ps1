Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Build single-file GUI executable with bundled ffmpeg.
pyinstaller --noconfirm --clean .\Video_Stitcher.spec

Write-Host "Build finished. Output: .\dist\Video_Stitcher.exe"
