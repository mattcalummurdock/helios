FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 \
    libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY shared/requirements.txt /app/shared/requirements.txt
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

COPY services/inference-service/requirements.txt /app/inference-service/requirements.txt

# ultralytics depends on opencv-python (GUI) which needs libxcb/X11 — unusable in slim Docker.
# Install ultralytics with --no-deps; keep only opencv-python-headless.
RUN pip install --no-cache-dir -r /app/inference-service/requirements.txt \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "ultralytics>=8.2.0" --no-deps \
    && pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true \
    && rm -rf /usr/local/lib/python3.11/site-packages/cv2 \
        /usr/local/lib/python3.11/site-packages/opencv_python*.dist-info \
        /usr/local/lib/python3.11/site-packages/opencv_python-*.dist-info \
    && pip install --no-cache-dir --force-reinstall opencv-python-headless==4.10.0.84 \
    && python -c "import cv2; cv2.__version__; print('cv2 OK', cv2.__file__)" \
    && python -c "import subprocess, sys; freeze=subprocess.check_output([sys.executable,'-m','pip','freeze']).decode(); bad=[l for l in freeze.splitlines() if l.startswith('opencv-python==')]; assert not bad, f'opencv-python installed: {bad}'"

COPY shared/helios_common /app/helios_common
COPY services/scene-watcher/scene_watcher /app/scene_watcher
COPY services/preprocessor/preprocessor /app/preprocessor
COPY services/inference-service/inference_service /app/inference_service
COPY services/change-detection/change_detection /app/change_detection
COPY services/alert-service/alert_service /app/alert_service

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg

COPY services/inference-service/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh \
    && python -c "import inference_service.tasks; print('inference_service.tasks OK')"

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
