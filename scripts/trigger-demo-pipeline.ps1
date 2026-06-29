# Enqueue preprocessing for all demo scenes (requires local or docker preprocessor worker).
. "$PSScriptRoot\local-worker-env.ps1"

$Python = Join-Path $RepoRoot ".venv-workers\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = Join-Path $RepoRoot ".venv-train\Scripts\python.exe"
}

foreach ($id in 1, 2, 3, 4) {
    Write-Host "Enqueue preprocess_scene(scene_id=$id)..."
    & $Python -m celery -A helios_common.celery_app call preprocessor.tasks.preprocess_scene --args="[$id]"
}

Write-Host "Done. Watch preprocessor + inference terminal windows for logs."
