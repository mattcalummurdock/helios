FROM ghcr.io/osgeo/gdal:ubuntu-small-3.8.4

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY shared/requirements.txt /app/shared/requirements.txt
COPY services/preprocessor/requirements.txt /app/services/preprocessor/requirements.txt
RUN pip3 install --no-cache-dir -r /app/shared/requirements.txt \
    && pip3 install --no-cache-dir -r /app/services/preprocessor/requirements.txt

COPY shared/helios_common /app/helios_common
COPY services/scene-watcher/scene_watcher /app/scene_watcher
COPY services/preprocessor/preprocessor /app/preprocessor
COPY services/inference-service/inference_service /app/inference_service
COPY services/change-detection/change_detection /app/change_detection
COPY services/alert-service/alert_service /app/alert_service

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY services/preprocessor/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
