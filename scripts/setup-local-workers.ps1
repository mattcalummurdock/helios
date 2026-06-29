# One-time setup for local preprocessor + inference workers on Windows.
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$Venv = Join-Path $RepoRoot ".venv-workers"
if (-not (Test-Path $Venv)) {
    python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

& $Pip install -U pip wheel
& $Pip install opencv-python-headless==4.10.0.84
& $Pip install -r requirements-local-workers.txt
& $Pip install "ultralytics>=8.2.0" --no-deps
& $Pip uninstall -y opencv-python 2>$null

& $Py -c "import cv2; import celery; import rasterio; print('OK cv2', cv2.__version__)"

Write-Host "`nSetup complete. Next:"
Write-Host "  1. docker compose up -d postgres redis triton fastapi frontend"
Write-Host "  2. Two terminals: scripts\run-local-preprocessor.ps1  and  scripts\run-local-inference.ps1"
Write-Host "  3. scripts\trigger-demo-pipeline.ps1"
