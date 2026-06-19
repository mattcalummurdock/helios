#!/bin/bash
set -e

python -c "from helios_common.health import start_health_server; start_health_server(8080)"

exec celery -A helios_common.celery_app worker \
    -Q change_detection \
    --loglevel=info \
    --concurrency=1
