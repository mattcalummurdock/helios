#!/bin/bash
set -e

export CELERY_IMPORTS="scene_watcher.tasks,alert_service.tasks"

python -c "from helios_common.health import start_health_server; start_health_server(8080)"

exec celery -A helios_common.celery_app worker \
    -Q scene_watch \
    --beat \
    --loglevel=info \
    --concurrency=1
