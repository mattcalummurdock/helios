FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/requirements.txt /app/shared/requirements.txt
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

COPY services/change-detection/requirements.txt /app/change-detection/requirements.txt
RUN pip install --no-cache-dir -r /app/change-detection/requirements.txt

COPY shared/helios_common /app/helios_common
COPY services/scene-watcher/scene_watcher /app/scene_watcher
COPY services/preprocessor/preprocessor /app/preprocessor
COPY services/inference-service/inference_service /app/inference_service
COPY services/change-detection/change_detection /app/change_detection
COPY services/alert-service/alert_service /app/alert_service

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY services/change-detection/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
