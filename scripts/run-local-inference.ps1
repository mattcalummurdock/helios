# Run inference Celery worker on host (connects to Docker redis/postgres/triton).
. "$PSScriptRoot\local-worker-env.ps1"
$env:CELERY_IMPORTS = "inference_service.tasks"

$Python = Join-Path $RepoRoot ".venv-workers\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = Join-Path $RepoRoot ".venv-train\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    Write-Error "No venv found. Run: python -m venv .venv-workers && pip install -r requirements-local-workers.txt"
    exit 1
}

Write-Host "Starting LOCAL inference worker (queue=inference)..."
& $Python -m celery -A helios_common.celery_app worker -Q inference --loglevel=info --pool=solo --concurrency=1
