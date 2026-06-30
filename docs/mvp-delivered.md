# Helios MVP 

**AI-Based Satellite Image Analysis**  
Real-time 3D globe surveillance · Autonomous ingestion pipeline · Deep-learning detection & change analysis

This document records what has been built for the Helios MVP to date: the infrastructure, ML pipeline, backend services, analyst dashboard, and the production-ready Vercel deployment used for live demonstrations.

---

## 1. Executive Summary

Helios is a persistent, autonomous satellite surveillance prototype. The system ingests satellite imagery through a Celery-based worker pipeline, runs GPU inference via NVIDIA Triton, stores geospatial results in PostGIS, and presents them on an interactive 3D Cesium globe with alerts, movement vectors, AOI management, and multi-format export.

The MVP stack is implemented as **10 Docker Compose services** (PostGIS, Redis, Triton, five Celery workers, FastAPI, Next.js) plus a **standalone Vercel-hosted frontend** that serves a curated operational snapshot for stakeholder demos without requiring the full backend to be online.

| Area | Delivered |
|------|-----------|
| Infrastructure | Docker Compose, PostGIS schema, Celery/Redis queues, health checks |
| Data pipeline | Scene Watcher, 5-step preprocessor, tiling, autonomous task routing |
| ML | YOLOv8-OBB (DOTA), MSTAR SAR CNN + CBAM, BIT change detection, Triton ONNX serving |
| Backend | FastAPI REST + WebSocket, JWT auth, export (PDF/CSV/KML/GeoJSON), 6 alert rules |
| Frontend | Cesium 3D globe, AOI Manager (Leaflet), timeline, alerts, export modal |
| Demo | Seeded multi-region showcase, static export to Vercel, 5 global detection pins |

**Live demo URL (Vercel):** _[add your deployment URL here]_

---

## 2. System Architecture Delivered

The end-to-end flow connects satellite APIs → preprocessing → inference → spatial analytics → alerting → analyst dashboard.

```
Copernicus / Planet APIs
        ↓
  Scene Watcher (Celery Beat)
        ↓
  Preprocessor → 640×640 tiles
        ↓
  Inference Service → Triton (YOLO / MSTAR / BIT)
        ↓
  PostGIS (AOIs, scenes, detections, changes, alerts)
        ↓
  FastAPI (REST + WebSocket)  →  Next.js + CesiumJS globe
```

### 2.1 Containerised services (10 services)

| Service | Role |
|---------|------|
| `postgres` | PostGIS 15 — spatial catalogue for AOIs, scenes, detections, changes, alerts |
| `redis` | Celery broker and result backend |
| `triton` | NVIDIA Triton Inference Server — YOLO, MSTAR, BIT models |
| `scene-watcher` | Scheduled Copernicus/Planet polling + Celery Beat |
| `preprocessor` | GDAL-based atmospheric correction, orthorectification, pansharpening, tiling |
| `inference-service` | Tile inference, NMS, Grad-CAM, detection persistence |
| `change-detection` | Bitemporal BIT inference + movement vector computation |
| `alert-service` | Threshold-based alert scanning (5-minute beat) |
| `fastapi` | REST API, WebSocket fan-out, export generation |
| `frontend` | Next.js operational dashboard |

> **Screenshot — Docker Compose stack**  
> Insert a terminal or Docker Desktop screenshot showing all Helios containers healthy (`docker compose ps`).  
> *Shows the full microservice stack running as designed in the MVP plan.*

---

## 3. Phase 1 — Infrastructure & Database

### 3.1 PostGIS schema

A complete spatial schema was implemented and versioned through SQL migrations:

- **`aois`** — analyst Areas of Interest with priority, monitoring flag, and polygon geometry (EPSG:4326)
- **`scenes`** — satellite scene catalogue with external IDs, sensor type, cloud cover, processing status
- **`detections`** — ML outputs with class, subclass, confidence, heading, OBB polygon, crop/Grad-CAM paths
- **`change_events`** — appeared / disappeared / moved events with distance, speed, bearing
- **`alerts`** — severity-ranked alerts with acknowledgement workflow

Spatial indexes on AOI polygons and detection bounding boxes support fast viewport and time-range queries.

### 3.2 Celery task orchestration

Four dedicated queues route work across independent workers:

| Queue | Worker |
|-------|--------|
| `scene_watch` | scene-watcher (+ Celery Beat) |
| `preprocessing` | preprocessor |
| `inference` | inference-service |
| `change_detection` | change-detection |
| `default` | alert-service |

Beat schedules include high-priority AOI polling (every 30 minutes), medium-priority polling (every 2 hours), and alert scans (every 5 minutes).

---

## 4. Phase 2 — Satellite Ingestion & Preprocessing

### 4.1 Satellite API integration

Client modules connect to:

- **Copernicus Data Space** — STAC search, OAuth token flow, S3-compatible scene download (Sentinel-1 SAR, Sentinel-2 optical)
- **Planet Labs** — quick-search and asset download for high-resolution optical passes

The Scene Watcher discovers new scenes per AOI, writes catalogue rows, and enqueues preprocessing automatically.

### 4.2 Five-step preprocessing pipeline

Each scene passes through a GDAL-based pipeline (`preprocessor/pipeline.py`):

1. **Atmospheric correction** — Py6S for Sentinel-2; skip for Planet SR; SAR sigma0 calibration for Sentinel-1  
2. **Orthorectification** — `gdalwarp` to EPSG:4326 with DEM support  
3. **Pansharpening** — Planet/WorldView path when applicable  
4. **Band normalisation** — float32 RGB (optical) or VV/VH stack (SAR)  
5. **Tiling** — 640×640 chips at 20% overlap with preserved geotransform metadata  

Processed tiles are stored under `/tiles/{scene_id}/` and inference is enqueued on completion.

### 4.3 Training augmentation library

`shared/helios_common/augmentation.py` provides an albumentations pipeline (flips, rotations, brightness/contrast jitter, CutMix) integrated into YOLO training configs.

---

## 5. Phase 3 — Machine Learning & Triton Serving

Three models form the intelligence core. Each was trained, evaluated, and exported for Triton serving.

### 5.1 Model 1 — YOLOv8-OBB target detection (DOTA)

| Item | Detail |
|------|--------|
| Dataset | DOTA v1.0, MVP-focused classes: vehicle, ship, aircraft, helicopter |
| Base model | YOLOv8-OBB (Ultralytics), oriented bounding boxes |
| Training | 60-epoch fine-tune, cosine LR, FP16, scene-level train/val/test split |
| Artifacts | `best.pt`, loss curve, mAP curve, confusion matrix, PR curves under `ml/artifacts/yolo/` |
| Serving | ONNX export → Triton model `yolov8_detection` |

Training scripts: `download_dota.py`, `convert_dota_obb.py`, `train_yolov8.py`, `export_triton.py`.



### 5.2 Model 2 — MSTAR SAR classification (ResNet-18 + CBAM)

| Item | Detail |
|------|--------|
| Dataset | MSTAR 10-class military vehicle taxonomy |
| Architecture | ResNet-18 adapted for single-channel SAR + CBAM attention (`ml/models/cbam.py`, `ml/models/mstar_cnn.py`) |
| Training | Depression-angle split (17° train / 15° test), Adam, cosine decay |
| Artifacts | `best.pth`, confusion matrix under `ml/artifacts/mstar/` |
| Serving | ONNX → Triton model `mstar_sar` |
| Runtime routing | Sentinel-1 scenes route to MSTAR; optical scenes route to YOLO |

### 5.3 Model 3 — BIT bitemporal change detection (LEVIR-CD)

| Item | Detail |
|------|--------|
| Dataset | LEVIR-CD (+ WHU-CD download scripts) |
| Model | Siamese BIT network (`train_bit.py`, `train_bit_simple.py`) |
| Inference | Triton model `bit_change`; tile-pair comparison in change-detection worker |
| Output | Change masks → movement events (distance, speed, bearing) in PostGIS |

### 5.4 Grad-CAM explainability

Grad-CAM heatmaps are generated at inference time and stored alongside detection crops. The API serves them at `GET /detections/{id}/gradcam` and `GET /detections/{id}/crop` for analyst review in the globe side panel.

### 5.5 Triton model repository

Triton exposes HTTP (8000), gRPC (8001), and Prometheus metrics (8002). The inference worker uses `helios_common/triton_client.py` for YOLO OBB parsing, MSTAR classification, and BIT mask inference, including cross-tile NMS.

---

## 6. Phase 4 — FastAPI Backend, WebSocket & Alerts

### 6.1 REST API

JWT authentication (`POST /auth/token`) protects all operational routes. Implemented endpoints:

| Endpoint | Capability |
|----------|------------|
| `GET/POST/PATCH/DELETE /aois` | AOI GeoJSON CRUD; new AOIs trigger scene poll |
| `GET /detections` | Filter by bbox, time range, class, confidence, AOI |
| `GET /detections/{id}/crop` | Satellite crop PNG |
| `GET /detections/{id}/gradcam` | Grad-CAM heatmap PNG |
| `GET /changes` | Change events with T1/T2 coordinates |
| `GET /alerts` | Severity-filtered alert list |
| `PATCH /alerts/{id}/acknowledge` | Analyst acknowledgement |
| `GET /scenes` | Scene catalogue per AOI |
| `GET /export` | PDF mission report, CSV, KML, GeoJSON |

Export is implemented with ReportLab (PDF), CSV writer, KML placemarks, and GeoJSON feature collections (`backend/services/export_service.py`).

### 6.2 Real-time WebSocket (`/ws`)

A connection manager broadcasts live events to all connected globe clients:

- `detection_created` — new marker on the globe  
- `change_detected` — movement vector update  
- `alert_fired` — alert panel notification  
- `scene_processing` / `scene_processing_complete` — AOI pulse animation  
- `ping` / `pong` — 30-second heartbeat  

Workers publish to Redis; FastAPI fans out to WebSocket clients (`backend/main.py`, `shared/helios_common/events.py`).

### 6.3 Alert engine (six rule types)

`services/alert-service/alert_service/rules.py` implements:

| Alert type | Logic |
|------------|-------|
| `new_object` | Class appears after absence across consecutive passes |
| `disappearance` | Tracked class missing for multiple passes |
| `formation_change` | DBSCAN cluster count shift >30% |
| `movement_threshold` | Displacement exceeds configurable metres (default 500 m) |
| `density_surge` | Detection count >2× 30-day rolling average |
| `no_coverage` | AOI exceeds revisit interval × 1.5 |

Alerts are deduplicated within a 6-hour window and pushed immediately via WebSocket.

---

## 7. Phase 5 — 3D Globe Dashboard (Next.js + CesiumJS)

The analyst-facing product is a dark-themed operational dashboard built in Next.js 14 with Cesium World Terrain and Bing aerial imagery (Cesium Ion token).

### 7.1 Globe page

**Layers and controls delivered:**

- **Detection layer** — class-coloured billboards scaled by confidence; click opens detail panel with model label, coordinates, heading, timestamp, satellite source, and crop/Grad-CAM image  
- **AOI layer** — semi-transparent polygons with priority and last-pass metadata; processing pulse animation on scene events  
- **Movement vector layer** — polylines from T1→T2 (green appeared, red disappeared, yellow moved); click for distance, speed, bearing  
- **Coverage layer** — recency heat colouring per AOI (green <6 h, yellow <48 h, red stale)  
- **Toolbar** — toggle Detections / AOIs / Vectors / Coverage; Export modal; Alerts bell with badge count  
- **Timeline scrubber** — 30-day window; drag to filter detections by time; LIVE mode reconnects WebSocket stream  

> **Screenshot — Full globe overview (Vercel)**  
> Insert a wide screenshot of the live Vercel deployment showing the 3D globe with multiple detection pins across Ukraine / Black Sea / airfield regions.  
> *Primary hero image for the MVP — establishes operational 3D surveillance context.*

> **Screenshot — Globe toolbar & layers**  
> Insert a crop showing the top toolbar (Detections, AOIs, Vectors, Coverage, Export) with at least one layer active.  
> *Shows analyst layer controls matching the MVP spec.*

> **Screenshot — Detection detail panel**  
> Click a detection pin on Vercel; capture the side panel with class, confidence, model designation (e.g. T62, An-26, Ropucha-class LST), coordinates, and satellite crop image.  
> *Demonstrates ML output + explainability at the point of interaction.*

> **Screenshot — Movement vectors**  
> Enable the Vectors layer and fly to the Kyiv vehicle change demo; capture yellow/green/red arrows between T1 and T2 positions.  
> *Shows temporal change analysis on the globe.*

> **Screenshot — Coverage layer**  
> Toggle Coverage and capture AOI polygons with green/yellow/red recency colouring.  
> *Shows intelligence freshness at a glance.*

> **Screenshot — Timeline scrubber**  
> Capture the bottom timeline bar with the detection volume chart and scrubber handle (optionally with LIVE button visible).  
> *Shows historical replay capability.*

### 7.2 Alert panel

Slide-out panel sorted by severity and timestamp. Each card includes fly-to, acknowledge, and browser notification support for critical alerts.

> **Screenshot — Alert panel open (Vercel)**  
> Open the bell icon; capture 2–3 alerts with CRITICAL/HIGH/MEDIUM badges and descriptions.  
> *Shows operational alerting without leaving the globe.*

### 7.3 AOI Manager (`/aois`)

Dedicated management page with:

- Left panel — AOI list with priority, last pass, 7-day detection count, monitoring toggle, deactivate  
- Right panel — Leaflet map with polygon draw tool; inline draft form (name, priority, save/cancel)  

> **Screenshot — AOI Manager (Vercel)**  
> Insert screenshot of `/aois` with the AOI list and Leaflet map showing existing AOI polygons.  
> *Shows analyst workflow for defining and managing Areas of Interest.*

### 7.4 Export modal

Export from the globe toolbar supports PDF mission report, CSV, KML, and GeoJSON with optional AOI and class filters. On the Vercel static deployment, client-side export generates the same formats from the bundled demo dataset.

> **Screenshot — Export modal (Vercel)**  
> Open Export on Vercel; capture the format dropdown and class checkboxes.  
> *Shows GIS interoperability (ArcGIS, Google Earth, Excel).*

---

## 8. Phase 6 — Integration, Demo Data & End-to-End Showcase

A full demo dataset was built to support repeatable stakeholder walkthroughs across multiple theatres.

### 8.1 Demo asset pipeline

Scripts under `ml/scripts/`:

| Script | Purpose |
|--------|---------|
| `pick_demo_images.py` | Scan DOTA val images with trained YOLO; select vehicle/ship/aircraft/helicopter showcase chips |
| `seed_demo.py` | Stage georeferenced Sentinel-style bands for Kyiv, Black Sea, and airfield AOIs |
| `seed_five_point_demo.py` | Five global showcase detections with defence-relevant model labels (T62, An-26, Mi-8MT, etc.) |
| `seed_demo_change_vector.py` | Movement vectors (moved / appeared / disappeared) across demo AOIs |
| `seed_demo_alerts.py` | Operational alerts linked to change events |
| `export_demo_static.py` | Export PostGIS snapshot + crop images → `frontend/public/demo/` |

### 8.2 Showcase regions seeded

| Region | Showcase content |
|--------|------------------|
| Kyiv | Vehicle column (T62), T1/T2 change vectors |
| Black Sea | Naval anchorage (Ropucha-class LST) |
| Lviv airfield | Fixed-wing (An-26) and rotary (Mi-8MT) |
| Baltic | Helicopter detection pin |
| Levant | SAR-style vehicle pass (2S1) |

**Exported static bundle (Vercel):** 5 AOIs · 13 detections · 6 change events · 7 alerts · 4 scenes · 5 crop images

---

## Conclusion

The Helios MVP delivers a working autonomous satellite analysis stack: from API ingestion and GDAL preprocessing through three trained models on Triton, into a PostGIS operational database, and out to a Cesium-based 3D analyst dashboard with live alerts, change vectors, AOI management, and multi-format export. The deployment packages a curated, defence-relevant showcase dataset for reliable live demonstrations.

