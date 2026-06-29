# Run preprocessing Celery worker on host (connects to Docker redis/postgres/triton).
. "$PSScriptRoot\local-worker-env.ps1"
$env:CELERY_IMPORTS = "preprocessor.tasks"

$Python = Join-Path $RepoRoot ".venv-workers\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = Join-Path $RepoRoot ".venv-train\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    Write-Error "No venv found. Run: python -m venv .venv-workers && pip install -r requirements-local-workers.txt"
    exit 1
}

Write-Host "Starting LOCAL preprocessor worker (queue=preprocessing)..."
& $Python -m celery -A helios_common.celery_app worker -Q preprocessing --loglevel=info --pool=solo --concurrency=1
