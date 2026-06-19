# Helios — AI-Based Satellite Image Analysis MVP

Phase 1 infrastructure for an autonomous satellite surveillance system: Docker Compose with 10 services, PostGIS schema, Celery/Redis task queues, and GPU-ready Triton inference server.

## Prerequisites

### Windows (recommended setup)

1. **Docker Desktop** with WSL2 backend enabled
2. **WSL2** (Ubuntu 22.04 recommended)
3. **NVIDIA GPU drivers** installed on Windows (for RTX 3060)
4. **NVIDIA Container Toolkit** in WSL2:

   ```bash
   # Inside WSL2 Ubuntu
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

5. Verify GPU access:

   ```bash
   nvidia-smi
   docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
   ```

### Hardware notes (RTX 3060 6GB)

The MVP doc targets 16GB VRAM for production Triton serving. Your RTX 3060 6GB is sufficient for **Phase 1** (empty Triton model repository). In **Phase 3**, use:

- `yolov8s-obb` instead of `yolov8m-obb`
- Smaller batch sizes (`batch=4` or lower)
- Load one model at a time if VRAM is tight

## Quick Start

```bash
# From project root (in WSL2 or Linux)
cp .env.example .env
docker compose up --build
```

First startup may take several minutes while images build and PostGIS initializes.

## Service Port Map

| Service | Host Port | Internal | Description |
|---------|-----------|----------|-------------|
| frontend | 3000 | 3000 | Next.js status dashboard |
| fastapi | 8080 | 8000 | REST API + `/health` |
| triton | 8000 | 8000 | Triton HTTP inference |
| triton | 8001 | 8001 | Triton gRPC |
| triton | 8002 | 8002 | Triton Prometheus metrics |
| postgres | 5433 | 5432 | PostGIS database |
| redis | — | 6379 | Celery broker (internal) |

## Verification Checklist

1. All containers running:

   ```bash
   docker compose ps
   ```

2. API health (DB connected):

   ```bash
   curl http://localhost:8080/health
   # Expected: {"status":"ok","db":"connected","phase":1}
   ```

3. Triton ready:

   ```bash
   curl http://localhost:8000/v2/health/ready
   ```

4. Frontend loads at [http://localhost:3000](http://localhost:3000)

5. PostGIS schema initialized:

   ```bash
   docker compose exec postgres psql -U helios -d helios -c "\dt"
   ```

   Expected tables: `aois`, `scenes`, `detections`, `change_events`, `alerts`

6. Celery Beat scheduling (scene-watcher logs):

   ```bash
   docker compose logs scene-watcher --tail 50
   ```

   Look for `Scene Watcher poll [high/medium]` task executions.

## Architecture (Phase 1)

```
Satellite APIs (Phase 2) → scene-watcher → Redis queues → workers → PostGIS
                                                              ↓
                                                         Triton (GPU)
                                                              ↓
                                                         fastapi → frontend
```

### Celery Queues

| Queue | Worker Service |
|-------|----------------|
| `scene_watch` | scene-watcher (also runs Celery Beat) |
| `preprocessing` | preprocessor |
| `inference` | inference-service |
| `change_detection` | change-detection |
| `default` | alert-service |

### PostGIS Tables

- `aois` — analyst Areas of Interest (2 seed AOIs included)
- `scenes` — satellite scene catalogue
- `detections` — ML detection results
- `change_events` — T1/T2 change analysis
- `alerts` — fired alert records

## Project Structure

```
helios/
├── docker-compose.yml
├── migrations/
│   ├── 001_init_postgis.sql
│   └── 002_scenes_external_id.sql
├── data/                     # Raw scene downloads (gitignored)
├── tiles/                    # 640x640 chips (gitignored)
├── shared/helios_common/     # Celery, DB, config
├── services/                 # Pipeline workers
├── backend/                  # FastAPI
├── frontend/                 # Next.js
└── models/                   # Triton model repo (empty in Phase 1)
```

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Description |
|----------|-------------|
| `POSTGRES_*` | Database credentials |
| `DATABASE_URL` | Async SQLAlchemy connection |
| `DATABASE_URL_SYNC` | Sync connection for Celery workers |
| `REDIS_URL` | Celery broker/backend |
| `TRITON_URL` | Triton server address |
| `JWT_SECRET` | API auth secret (Phase 4) |
| `COPERNICUS_*` | Copernicus API credentials (Phase 2) |
| `PLANET_API_KEY` | Planet Labs API key (Phase 2) |
| `KAGGLE_*` | Kaggle API for MSTAR dataset (Phase 3) |
| `TRITON_YOLO_MODEL` | Triton model name for YOLO (default `yolov8_detection`) |
| `YOLO_MODEL_SIZE` | YOLO backbone size: `s` for 6GB VRAM (Phase 3) |
| `DETECTIONS_DIR` | Grad-CAM and crop storage path |
| `CESIUM_ION_TOKEN` | Cesium globe token (Phase 5) |

## Troubleshooting

**Triton fails to start (GPU):** Ensure NVIDIA Container Toolkit is installed and Docker Desktop has GPU support enabled in Settings → Resources → WSL Integration.

**Postgres init errors:** Remove the volume and restart:

```bash
docker compose down -v
docker compose up --build
```

**Worker can't connect to DB:** Wait for postgres healthcheck to pass; workers depend on `service_healthy`.

## Phase 2 — Satellite Ingestion & Preprocessing

Phase 2 adds autonomous scene discovery (Copernicus CDSE + Planet Labs), download, preprocessing, and tiling.

### Setup

1. Register at [Copernicus Data Space](https://dataspace.copernicus.eu) and [Planet Labs](https://planet.com)
2. Add credentials to `.env`:

   ```
   COPERNICUS_CLIENT_ID=your-id
   COPERNICUS_CLIENT_SECRET=your-secret
   PLANET_API_KEY=your-planet-key
   ```

3. **Existing database** (created in Phase 1): apply migration 002:

   ```powershell
   docker compose exec -T postgres psql -U helios -d helios < migrations/002_scenes_external_id.sql
   ```

4. Rebuild pipeline services:

   ```powershell
   docker compose up -d --build scene-watcher preprocessor inference-service
   ```

### Data flow

```
Celery Beat → poll_active_aois → Copernicus STAC + Planet quick-search
    → download to /data/scenes/{id}/raw/
    → preprocess_scene (6 steps) → /tiles/{scene_id}/{row}_{col}.tif
    → run_inference (Triton YOLO/MSTAR + Grad-CAM + change detection enqueue)
```

### Preprocessing steps

1. Atmospheric correction (skip L2A/Planet; SAR sigma0 calibration)
2. Orthorectification (`gdalwarp` → EPSG:4326)
3. Pansharpening (Planet only, OTB if installed)
4. Band normalisation → float32 RGB/VV-VH stack
5. Tiling 640×640 @ 20% overlap
6. Enqueue inference + mark `scenes.processed = true`

### Phase 2 verification

```powershell
# Manual poll trigger
docker compose exec scene-watcher celery -A helios_common.celery_app call scene_watcher.tasks.poll_active_aois --kwargs='{"priority_filter":"high"}'

# Check catalogue
docker compose exec postgres psql -U helios -d helios -c "SELECT id, external_scene_id, sensor_type, processed FROM scenes;"

# Check files on host
dir data\scenes
dir tiles

# Preprocessor logs
docker compose logs preprocessor --tail 50
```

**Pass criteria:**
- New `scenes` rows with `external_scene_id` after poll (requires valid API credentials)
- Raw bands under `data/scenes/{id}/raw/`
- Tiles under `tiles/{scene_id}/`
- `scenes.processed = true` and inference task enqueued in logs
- Structured JSON logs: `poll_start`, `scene_discovered`, `poll_complete`

**Without credentials:** Scene Watcher logs `poll_error` with auth messages; Beat continues without crashing.

### Training augmentation (Phase 3)

Use [`shared/helios_common/augmentation.py`](shared/helios_common/augmentation.py) in YOLOv8 training:

```python
from helios_common.augmentation import get_training_augmentation
transform = get_training_augmentation(image_size=640)
```

## Phase 3 — ML Models & Triton Serving

Phase 3 adds YOLOv8-OBB (DOTA), MSTAR SAR CNN, BIT change detection, Triton ONNX export, Grad-CAM, and real inference/change-detection workers.

See [`ml/README.md`](ml/README.md) for full training steps.

### Setup

1. **WSL2 CUDA venv** on host:

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r ml/requirements-train.txt
   ```

2. Add `KAGGLE_USERNAME` / `KAGGLE_KEY` to `.env` for MSTAR dataset.

3. **Existing database**: apply migration 003:

   ```powershell
   docker compose exec -T postgres psql -U helios -d helios < migrations/003_detection_gradcam.sql
   ```

4. Download datasets, train, export:

   ```bash
   python ml/scripts/download_dota.py
   python ml/scripts/convert_dota_obb.py
   python ml/scripts/train_yolov8.py
   python ml/scripts/download_mstar_kaggle.py
   python ml/scripts/train_mstar.py
   python ml/scripts/download_levir_cd.py
   python ml/scripts/train_bit.py
   python ml/scripts/export_triton.py
   docker compose restart triton
   ```

5. Rebuild inference workers:

   ```powershell
   docker compose up -d --build inference-service change-detection fastapi
   ```

### Runtime flow

```
preprocess_scene → tiles/
    → run_inference (sensor_type routing)
        → sentinel-2/planet: YOLOv8 via Triton
        → sentinel-1: MSTAR via Triton
    → detections + Grad-CAM PNGs in /data/detections/{id}/
    → detect_changes (BIT via Triton) → change_events
```

### Phase 3 verification

```powershell
curl http://localhost:8000/v2/models/yolov8_detection/ready
curl http://localhost:8000/v2/models/mstar_sar/ready
curl http://localhost:8000/v2/models/bit_change/ready

dir ml\artifacts\yolo\*.png
dir ml\artifacts\mstar\confusion_matrix.png

docker compose exec inference-service celery -A helios_common.celery_app call inference_service.tasks.run_inference --args='[1, []]'
curl http://localhost:8080/detections/1/gradcam
```

**Pass criteria:**
- YOLO mAP50 >65% (floor 60%), 4 charts in `ml/artifacts/yolo/`
- MSTAR >95% on 15° test, confusion matrix saved
- BIT F1 >0.85 on LEVIR-CD test
- 3 Triton models ready; inference logs avg tile time <500ms
- Grad-CAM PNG served via `GET /detections/{id}/gradcam`

## Next Phase

Phase 4 implements full detection API, WebSocket alerts, and auth. See `docs/mvp.md`.
