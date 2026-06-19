#!/bin/bash
set -e

export CELERY_IMPORTS="preprocessor.tasks"

python3 -c "from helios_common.health import start_health_server; start_health_server(8080)"

exec celery -A helios_common.celery_app worker \
    -Q preprocessing \
    --loglevel=info \
    --concurrency=1
