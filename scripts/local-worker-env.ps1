# Shared env for local Celery workers (preprocessor + inference on host PC).
# Docker stack must be up: postgres, redis, triton, fastapi, frontend.

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$DataRoot = Join-Path $RepoRoot "data"
$TilesDir = Join-Path $RepoRoot "tiles"
New-Item -ItemType Directory -Force -Path $DataRoot, $TilesDir | Out-Null

$env:PYTHONPATH = @(
    (Join-Path $RepoRoot "shared"),
    (Join-Path $RepoRoot "services\preprocessor"),
    (Join-Path $RepoRoot "services\inference-service"),
    (Join-Path $RepoRoot "services\scene-watcher"),
    (Join-Path $RepoRoot "services\change-detection"),
    (Join-Path $RepoRoot "services\alert-service")
) -join ";"

$env:DATABASE_URL_SYNC = "postgresql://helios:changeme@localhost:5433/helios"
$env:DATABASE_URL = "postgresql+asyncpg://helios:changeme@localhost:5433/helios"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:TRITON_URL = "localhost:8000"
$env:DATA_ROOT = $DataRoot
$env:TILES_DIR = $TilesDir
$env:DETECTIONS_DIR = Join-Path $DataRoot "detections"
$env:ARTIFACTS_DIR = Join-Path $RepoRoot "ml\artifacts"
$env:MPLBACKEND = "Agg"

New-Item -ItemType Directory -Force -Path $env:DETECTIONS_DIR | Out-Null

Write-Host "Local worker env ready (repo: $RepoRoot)"
Write-Host "  REDIS_URL=$($env:REDIS_URL)"
Write-Host "  DATABASE_URL_SYNC=$($env:DATABASE_URL_SYNC)"
Write-Host "  TRITON_URL=$($env:TRITON_URL)"
Write-Host "  DATA_ROOT=$($env:DATA_ROOT)"
