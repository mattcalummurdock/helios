
	RESTRICTED — AUTHORISED PERSONNEL ONLY	

AI-BASED SATELLITE
IMAGE ANALYSIS
MVP — Phase-Wise Implementation Plan
Real-Time 3D Globe Surveillance | Autonomous Satellite Ingestion | Deep Learning Detection & Change Analysis

7
Phases	5
Services	3
ML Models	4
Globe Layers

Phase 1
Infra Setup	→	Phase 2
Data Pipeline	→	Phase 3
ML Models	→	Phase 4
Backend API	→	Phase 5
3D Globe	→	Phase 6
Integration	→	Phase 7
Deployment	

Estimated MVP Build: 3–4 Weeks  |  Stack: Next.js + FastAPI + Celery + Triton + PostGIS + CesiumJS


TABLE OF CONTENTS

  1.  Document Overview & System Architecture

This document is the complete phase-wise implementation guide for building the AI-Based Satellite Image Analysis MVP. Unlike a traditional demo, this is a persistent, autonomous surveillance system — satellite data is ingested on a schedule, processed through a deep learning pipeline, and streamed live to an interactive 3D globe. No uploads, no manual triggers. The system runs continuously and the analyst simply watches the globe update.

1.1  What Makes This MVP Different
No upload interface — the system autonomously connects to real satellite APIs (Copernicus/Planet Labs) and pulls imagery on a configured schedule
Real ML, not inference-only — the detection model is fine-tuned on the DOTA satellite dataset, the change detection uses a pretrained Siamese network on LEVIR-CD, and an optional SAR branch is trained on MSTAR military vehicle data
Live 3D globe built in Next.js with CesiumJS (via Resium) — detections appear as georeferenced markers in real time via WebSocket
Full operational output — KML/CSV/PDF report export, AOI management, alert panel, movement vectors, and timeline scrubber are all part of the prototype

1.2  End-to-End System Architecture

Layer	Description
Satellite APIs	Copernicus (Sentinel-1 SAR + Sentinel-2 Optical) and Planet Labs (daily 3m revisit) — automated polling, no manual download
Scene Watcher	Python microservice polling APIs on schedule, triggering the pipeline when a new scene covers a monitored AOI
Preprocessor	Atmospheric correction, orthorectification, pansharpening, tiling 640x640 with 20% overlap
Inference Service	Fine-tuned YOLOv8 detection model served via Triton Inference Server on GPU
Change Detection	Siamese BIT model comparing T1 vs T2 per AOI, writing change events to PostGIS
Alert Service	Threshold-based alert firing, pushing events via WebSocket to connected globe clients
FastAPI Backend	REST + WebSocket API consumed by Next.js frontend
PostGIS Database	Stores all detections, change events, alerts, AOIs, and scene metadata with spatial indexing
Next.js + CesiumJS	3D globe dashboard — live detection markers, AOI polygons, movement vectors, alert panel, timeline scrubber

1.3  Complete Technology Stack

Frontend
Next.js + Resium (CesiumJS)	API
FastAPI + WebSockets	Pipeline
Celery + Redis

ML Serving
Triton Inference Server	Detection
YOLOv8 fine-tuned (DOTA)	Change Det.
Siamese BIT (LEVIR-CD)

SAR Branch
CNN on MSTAR	Database
PostgreSQL + PostGIS	Containers
Docker Compose

1.4  Phase Timeline at a Glance

Phase	Scope & Timeline
Phase 1 — Week 1	Infrastructure, environment setup, Docker Compose, GPU configuration, PostGIS schema, Celery/Redis
Phase 2 — Week 1–2	Satellite API connections, Scene Watcher service, preprocessing pipeline, tile storage
Phase 3 — Week 2	ML model fine-tuning (YOLOv8 on DOTA), SAR CNN on MSTAR, Siamese change detection on LEVIR-CD, Triton setup
Phase 4 — Week 2–3	FastAPI backend, REST endpoints, WebSocket server, PostGIS queries, alert logic
Phase 5 — Week 3	Next.js 3D globe, CesiumJS layers, AOI manager, alert panel, timeline scrubber, movement vectors
Phase 6 — Week 3–4	System integration, end-to-end testing, PDF/KML/CSV export, performance tuning
Phase 7 — Week 4	Docker Compose production config, monitoring, demo preparation, analyst walkthrough

PHASE
01	Infrastructure & Environment Setup
Hardware · Docker · Database · Task Queue · GPU	DURATION
Week 1

Everything else depends on this phase being correct. Rushing environment setup causes compounding failures in later phases. Allocate proper time here.

1.1  Hardware Requirements
GPU: NVIDIA GPU with minimum 16GB VRAM for Triton Inference Server (RTX 3090/4090 or A-series). A100 is the production target but any modern NVIDIA GPU works for MVP
Install CUDA 12.x and verify with nvidia-smi before proceeding to any ML setup
Install NVIDIA Container Toolkit (nvidia-docker2) to expose GPU inside Docker containers: sudo apt install nvidia-container-toolkit
Minimum 32GB RAM on the host for comfortable operation of all services simultaneously
Minimum 500GB SSD storage — satellite tiles accumulate quickly

1.2  Docker Compose Setup
The entire MVP runs via Docker Compose. Define a single docker-compose.yml with the following named services:
postgres — PostgreSQL 15 with PostGIS 3.3 extension. Mount a persistent volume for data. Set POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD environment variables
redis — Redis 7 for Celery task queue. No persistence needed for MVP
triton — NVIDIA Triton Inference Server (nvcr.io/nvidia/tritonserver:23.10-py3). Mount the /models directory as a volume. Expose ports 8000 (HTTP), 8001 (gRPC), 8002 (metrics)
scene-watcher — Custom Python service. Polls satellite APIs on schedule. Pushes tasks to Celery
preprocessor — Custom Python service. Celery worker consuming preprocessing tasks
inference-service — Custom Python service. Celery worker sending tiles to Triton and writing detections to PostGIS
change-detection — Custom Python service. Celery worker running Siamese model on AOI image pairs
alert-service — Custom Python service. Monitors PostGIS for threshold breaches and pushes WebSocket events
fastapi — FastAPI application. Exposes REST and WebSocket endpoints to Next.js frontend
frontend — Next.js application. Served on port 3000

1.3  PostGIS Database Schema
Create the following tables immediately after PostGIS is running. All geometry columns use SRID 4326 (WGS84).

Table	Columns	Purpose
aois	id, name, priority (high/medium/low), polygon (GEOMETRY POLYGON), created_at, last_pass_at, monitoring_active (bool)	Analyst-defined Areas of Interest. The Scene Watcher polls against these bounding boxes.
scenes	id, aoi_id, satellite_source, acquisition_timestamp, cloud_cover_pct, scene_path, processed (bool), created_at	Catalogue of every satellite scene downloaded. Links detections to their source imagery.
detections	id, scene_id, aoi_id, class, subclass, confidence, lat, lon, heading_degrees, bbox_polygon (GEOMETRY), detection_image_path, timestamp	One row per detected object per scene pass.
change_events	id, aoi_id, event_type (appeared/disappeared/moved), detection_id_t1, detection_id_t2, distance_moved_m, speed_kmh, bearing_degrees, timestamp, alert_fired (bool)	Every detected change between consecutive passes of the same AOI.
alerts	id, aoi_id, change_event_id, alert_type, severity (critical/high/medium), lat, lon, description, acknowledged (bool), acknowledged_by, timestamp	Fired alerts. Pushed to frontend via WebSocket.

Create a spatial index on detections.bbox_polygon and aois.polygon for fast bounding-box queries: CREATE INDEX ON detections USING GIST(bbox_polygon)
Create a composite index on (aoi_id, timestamp) for efficient time-range queries

1.4  Celery + Redis Task Queue
Install Celery 5.x and configure it to use Redis as both broker and result backend
Define four Celery task queues: scene_watch, preprocessing, inference, change_detection — this allows independent scaling of each service
Configure Celery Beat scheduler to run the Scene Watcher task every 2 hours for medium-priority AOIs, every 30 minutes for high-priority AOIs
Set task routing so preprocessing tasks go to the preprocessor worker, inference tasks to the inference worker, and so on

PHASE
02	Satellite Data Ingestion & Preprocessing Pipeline
Real API connections · Scene Watcher · Tiling · Augmentation	DURATION
Week 1–2

This phase replaces the concept of an upload interface entirely. The system autonomously discovers new satellite imagery, downloads only the relevant AOI portion, and prepares it for the ML pipeline.

2.1  Satellite API Connections
2.1.1  Copernicus Data Space API (Primary — Free)
Register at dataspace.copernicus.eu and obtain API credentials
Use the OData or STAC API endpoint to search for scenes: filter by AOI bounding box, acquisition date > last_pass_at, cloud cover < 30%
Sentinel-2 (optical): request bands B04 (Red), B03 (Green), B02 (Blue), B08 (NIR) at 10m resolution only — do not download the full 1GB scene
Sentinel-1 (SAR): request GRD (Ground Range Detected) IW (Interferometric Wide) mode products in VV+VH polarisation
Use the S3-compatible access to download only the specific tile covering the AOI bounding box — use the boto3 library with the Copernicus S3 endpoint

2.1.2  Planet Labs API (Optional High-Resolution)
Register at planet.com/explorer for API key — free trial tier provides limited daily scene downloads sufficient for MVP demo
Use Planet's Data API with the quick-search endpoint: POST /data/v1/quick-search with an AOI geometry filter and item_types: [PSScene] for 3m resolution daily imagery
Activate and download assets using the Orders API — request analytic_sr (surface reflectance) assets
Planet data comes atmospherically corrected as surface reflectance — skip atmospheric correction step for Planet imagery

2.2  Scene Watcher Service
The Scene Watcher is a Python microservice running on a Celery Beat schedule. It is the entry point of the entire autonomous pipeline.
On each scheduled run, query the aois table for all active AOIs
For each AOI, call the Copernicus STAC API with the AOI polygon as a spatial filter and last_pass_at as the date filter
If a new scene exists that hasn't been catalogued in the scenes table, insert a new scenes record and enqueue a preprocessing Celery task with the scene_id
Log every poll attempt, result, and any API errors to a structured log — this is critical for debugging in a demo environment where timing matters
Update last_pass_at in the aois table after each successful scene discovery

2.3  Preprocessing Pipeline
The Preprocessor Celery worker picks up tasks from the preprocessing queue and executes the following steps in order:

Step 1	Atmospheric Correction — For Sentinel-2: apply Py6S radiative transfer correction to convert TOA reflectance to BOA surface reflectance. For Planet: skip (already SR). For Sentinel-1 SAR: apply radiometric calibration converting DN to sigma-naught backscatter values using GDAL/SNAP.

Step 2	Orthorectification — Use gdalwarp with a 30m SRTM DEM (download once from NASA EarthData) to terrain-correct all scenes. Reproject to EPSG:4326 (WGS84). Verify RMS reprojection error < 1 pixel.

Step 3	Pansharpening (WorldView / Planet only) — Apply Gram-Schmidt Spectral Sharpening via the Orfeo Toolbox (OTB) to fuse high-res panchromatic with multispectral bands. Sentinel imagery skips this step.

Step 4	Band Normalisation — Normalise all band values to [0, 1] float32 range using per-scene min/max. Stack into 3-band RGB GeoTIFF for optical; 2-band VV/VH GeoTIFF for SAR.

Step 5	Tiling — Tile processed images into 640x640 pixel chips with 20% overlap using Rasterio sliding window. Store each tile as a GeoTIFF preserving the affine geotransform. Naming: /tiles/{scene_id}/{row}_{col}.tif

Step 6	Enqueue Inference — After tiling, push all tile paths as a single inference Celery task to the inference queue. Update scenes.processed = true in PostGIS.

2.4  Data Augmentation (Training Only)
Applied during ML model fine-tuning in Phase 3. Not applied during inference.
Random horizontal and vertical flips — satellite images have no canonical orientation
Rotations at 0°, 90°, 180°, 270° — cover all cardinal perspectives
Brightness and contrast jitter via albumentations — simulate varying solar illumination conditions
CutMix augmentation — paste regions from one image onto another to improve rare class detection
Implement all augmentations as an albumentations Compose pipeline integrated into the MMDetection/YOLOv8 training config

PHASE
03	ML Model Development & Training
YOLOv8 fine-tuning · SAR CNN · Siamese Change Detection · Triton	DURATION
Week 2

Three separate ML models form the intelligence core of the MVP. Each addresses a distinct requirement: target detection, SAR-mode classification, and change/movement detection.

3.1  Model 1 — Target Detection: YOLOv8 Fine-tuned on DOTA
3.1.1  Dataset Preparation
Download DOTA v1.0 dataset from the official DOTA site (captain-whu.github.io/DOTA)
Select 4 operationally focused classes for MVP: vehicle, ship, aircraft, helicopter
Convert DOTA annotation format (.txt with polygon coordinates) to YOLOv8 OBB format using a conversion script — each line becomes: class cx cy w h angle (normalised)
Split dataset: 80% train, 10% validation, 10% test — use scene-level split (not tile-level) to prevent data leakage between splits
Apply preprocessing and augmentation pipeline from Phase 2 to all training tiles

3.1.2  Fine-tuning Configuration
Base model: YOLOv8m-obb (medium variant — balances speed and accuracy for MVP)
Download pretrained weights: yolov8m-obb.pt from Ultralytics
Training command: yolo obb train model=yolov8m-obb.pt data=dota_mvp.yaml epochs=60 imgsz=640 batch=16 lr0=0.001 cos_lr=True
Use cosine learning rate schedule with warm-up for first 3 epochs
Train with mixed precision (FP16) to maximise GPU memory efficiency
Target validation mAP50: >65% on the 4-class DOTA subset — accept nothing below 60% for demo

3.1.3  Training Outputs to Capture
Training loss curve (box loss + classification loss + DFL loss) — export as PNG for the MVP submission document
Validation mAP curve over epochs — shows learning progress
Confusion matrix on test set — shows per-class performance
Precision-Recall curves per class
Export final weights: best.pt (highest validation mAP checkpoint)

CRITICAL NOTE	These 4 training metric charts (loss curve, mAP curve, confusion matrix, PR curves) must be included in the MVP demo. To a defence evaluator, seeing real training metrics is the single biggest credibility signal — it proves the model was actually trained on satellite data, not just loaded from a generic checkpoint.

3.2  Model 2 — SAR Classification: CNN on MSTAR
3.2.1  Dataset Preparation
Download MSTAR (Moving and Stationary Target Acquisition and Recognition) dataset — 10 military ground vehicle classes including T72 tank, BMP2 APC, BTR70 APC, ZSU234 AAgun, and others
MSTAR images are 128x128 greyscale SAR chips — resize to 224x224 for the classifier
Standard split: depression angle 17° for training, 15° for testing (this is the established benchmark split — do not deviate)

3.2.2  Model Architecture & Training
Architecture: ResNet-18 pretrained on ImageNet, adapted for single-channel (greyscale) SAR input by modifying the first Conv2d layer to accept 1 channel
Add a CBAM (Convolutional Block Attention Module) after layer3 to focus the network on discriminative SAR scattering features
Training: 40 epochs, Adam optimiser, lr=0.0001, cosine decay, batch=32
Target accuracy: >95% on MSTAR 10-class test split — published CNN benchmarks achieve 99%+ so this is a conservative floor
Save confusion matrix — the visual separation between tank classes (T72 vs T62 vs T34) is compelling for a defence demo

3.3  Model 3 — Change Detection: Siamese BIT Network
3.3.1  Dataset
Primary dataset: LEVIR-CD — large-scale remote sensing change detection. Download from the official LEVIR-CD repository
Supplement with WHU-CD for additional structural change examples
Each sample is a T1/T2 image pair with a binary change mask label

3.3.2  Model: BIT (Binary change detection with Image Transformers)
Use the open-source BIT implementation from the open-cd library: pip install open-cd
BIT uses a ResNet backbone + Transformer encoder to compare bi-temporal feature maps — it is state of the art on LEVIR-CD
Fine-tune pretrained BIT weights on LEVIR-CD for 50 epochs with batch size 8
Target F1-score: >0.87 on LEVIR-CD test set (published benchmark is ~0.90)
The model outputs a binary change mask (same size as input) — changed pixels are white, unchanged are black
During inference, run BIT on the same AOI area from T1 (previous pass) and T2 (current pass) to detect what has changed

3.4  Grad-CAM Explainability
Integrate pytorch-grad-cam (pip install grad-cam) for the YOLOv8 detection model
When any detection marker is clicked on the globe, the backend generates a Grad-CAM heatmap for that specific crop
Grad-CAM highlights which pixels drove the classification decision — allows an analyst to see that the model focused on a vehicle's turret silhouette, not background noise
Store Grad-CAM heatmap images as PNG alongside detection crops — serve via FastAPI static file endpoint

3.5  Triton Inference Server Setup
Export YOLOv8 best.pt to ONNX: model.export(format='onnx', imgsz=640, opset=17)
Convert ONNX to TensorRT engine for maximum A100/RTX throughput using trtexec: trtexec --onnx=yolov8m-obb.onnx --saveEngine=model.plan --fp16
Export MSTAR ResNet-18 to ONNX: torch.onnx.export(model, dummy_input, 'mstar_cnn.onnx')
Export BIT change detection model to ONNX
Organise Triton model repository: /models/yolov8_detection/1/model.plan, /models/mstar_sar/1/model.onnx, /models/bit_change/1/model.onnx
Create config.pbtxt for each model specifying input/output tensor names, shapes, and data types
Triton handles batching automatically — configure max_batch_size=8 for the detection model

PHASE
04	FastAPI Backend — REST, WebSocket & Spatial Services
API endpoints · WebSocket streaming · Alert logic · Spatial queries	DURATION
Week 2–3

The FastAPI backend is the central nervous system — it connects the ML pipeline output in PostGIS to the Next.js globe frontend. It handles REST queries, real-time WebSocket event streaming, and the alert management system.

4.1  FastAPI Application Structure
Organise into routers: /aois, /detections, /changes, /alerts, /scenes, /export, /ws (WebSocket)
Use SQLAlchemy async with asyncpg driver for non-blocking PostGIS queries
Use GeoAlchemy2 for spatial query support in SQLAlchemy models
Use python-jose for JWT authentication — the globe frontend sends a Bearer token with every request
Run with uvicorn with 4 worker processes: uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000

4.2  REST API Endpoints

Endpoint	Description	Used By
GET /aois	Returns all AOIs as GeoJSON FeatureCollection. Each feature includes polygon geometry, name, priority, last_pass_at, monitoring_active.	Globe AOI layer source. Called on dashboard load.
POST /aois	Creates a new AOI from a GeoJSON polygon body. Immediately triggers the Scene Watcher for the new AOI.	AOI Manager page in frontend.
DELETE /aois/{id}	Deactivates monitoring for an AOI (sets monitoring_active=false). Does not delete historical detections.	AOI Manager delete action.
GET /detections	Returns detections filtered by bbox (bounding box), time_range, class[], confidence_min. Returns GeoJSON FeatureCollection.	Globe detection layer. Filters by current camera viewport bbox.
GET /detections/{id}/gradcam	Returns Grad-CAM PNG image for a specific detection crop.	Detection info panel in globe.
GET /changes	Returns change events filtered by aoi_id and time_range. Includes T1/T2 coordinates and movement vector.	Globe movement vector layer.
GET /alerts	Returns all alerts, optionally filtered by aoi_id, severity, and acknowledged status. Sorted by timestamp desc.	Alert panel in globe dashboard.
PATCH /alerts/{id}/acknowledge	Marks an alert as acknowledged with analyst identifier.	Alert panel acknowledge button.
GET /scenes	Returns scene catalogue for an AOI — what was imaged, when, by which satellite, cloud cover.	Coverage layer metadata.
GET /export	Generates export in requested format: pdf, csv, kml, geojson. Accepts bbox and time_range filters.	Export button in globe.

4.3  WebSocket Endpoint (/ws)
The WebSocket is the real-time channel between the backend and every connected globe client. It is what makes the globe feel live.
Maintain a connection manager class that tracks all connected WebSocket clients
On new detection written to PostGIS (by the Inference Service), broadcast a detection_created event to all connected clients with the full detection GeoJSON feature
On new change event written, broadcast a change_detected event with T1/T2 coords, event_type, and movement vector
On alert fired, broadcast an alert_fired event with full alert payload including severity, coordinates, and description
On new scene acquisition started, broadcast a scene_processing event with aoi_id — the globe uses this to animate the AOI polygon
Implement heartbeat ping every 30 seconds to detect and clean up dead connections
Clients reconnect automatically with exponential backoff if the WebSocket drops — implement this in the Next.js frontend

4.4  Alert Service Logic
The Alert Service runs as a separate Celery periodic task every 5 minutes, scanning for new change events that meet alert thresholds.

Alert Type	Trigger & Severity Logic
New Object Alert	Fires when a class appears in an AOI that was not present in the previous 3 consecutive passes. Severity: CRITICAL for tanks/aircraft, HIGH for vehicles, MEDIUM for ships.
Disappearance Alert	Fires when a previously tracked object class is absent for 2 consecutive passes after having been present for 3+. May indicate concealment or repositioning.
Formation Change Alert	Fires when DBSCAN cluster count in an AOI changes by more than 30% between passes. Indicates major troop movement or dispersal.
Movement Threshold Alert	Fires when change event distance_moved_m exceeds configurable threshold (default: 500m between passes). Includes projected next position based on bearing.
Density Surge Alert	Fires when detection count in an AOI exceeds the 30-day rolling average by 2x or more. Indicates rapid concentration of assets.
No-Coverage Alert	Fires when an AOI has not received a satellite pass for longer than its expected revisit interval x 1.5. Warns analysts of intelligence gap.

Write all fired alerts to the alerts PostGIS table
Push alert via WebSocket to all connected clients immediately
Prevent duplicate alerts: check if an alert of the same type for the same AOI was fired within the last 6 hours before firing again

PHASE
05	Next.js 3D Globe Dashboard
CesiumJS · Live layers · AOI Manager · Alert panel · Timeline · Export	DURATION
Week 3

The globe is what the defence client sees. Every feature here must feel operational, responsive, and credible. Use a dark military-style theme throughout — dark background, muted greens and blues, high-contrast alert colours.

5.1  CesiumJS Setup in Next.js
Install Resium (React wrapper for CesiumJS): npm install resium cesium
Configure next.config.js to copy CesiumJS static assets: use the copy-webpack-plugin to copy node_modules/cesium/Build/Cesium to public/cesium
Set CESIUM_BASE_URL in the Cesium config to point to the static assets path
Obtain a free Cesium Ion access token from ion.cesium.com — required for Bing Maps aerial imagery base layer
Configure the Viewer with: terrain provider (CesiumTerrainProvider with Cesium World Terrain for 3D elevation), imagery layer (Bing Maps Aerial), and navigation controls
Set initial camera position to a relevant AOI location on first load

5.2  Globe Layers
5.2.1  Detection Layer (Live)
On WebSocket detection_created event, add a CesiumJS BillboardGraphics entity at the detection lat/lon
Billboard icon differs by class: red tank icon for ground vehicles, blue ship icon for naval, yellow aircraft icon for aircraft, orange helicopter for helicopter
Billboard scale is proportional to confidence score — higher confidence = larger icon
On click, open a side panel showing: class, subclass, confidence score, WGS84 coordinates (6dp), heading, timestamp, satellite source, and the Grad-CAM heatmap image fetched from GET /detections/{id}/gradcam
Layer has a toggle button in the globe toolbar to show/hide all detection markers

5.2.2  AOI Layer (Live)
On globe load, fetch GET /aois and render each AOI polygon as a CesiumJS PolygonGraphics entity
AOI polygons are semi-transparent with a glowing blue outline
When a scene_processing WebSocket event arrives for an AOI, animate the polygon outline to pulse (cycle opacity between 0.3 and 0.9 at 1Hz) until scene_processing_complete arrives
AOI polygon tooltip shows: name, priority, last pass timestamp, satellite source of last pass, and number of active detections

5.2.3  Change / Movement Vector Layer
On WebSocket change_detected event, render a CesiumJS PolylineGraphics arrow from T1 detection position to T2 detection position
Arrow colour: green for appeared, red for disappeared, yellow for moved
Arrow thickness proportional to estimated speed — fast-moving assets get thicker arrows
Clicking an arrow shows the change event detail: event type, class, distance moved, estimated speed, bearing, time delta between passes

5.2.4  Coverage Layer (Toggleable)
Render a heatmap rectangle over each AOI showing recency of coverage — colour graduated from bright green (imaged < 6 hours ago) through yellow to red (imaged > 48 hours ago)
This tells analysts at a glance where their intelligence is fresh and where it is stale
Tooltip shows: last pass timestamp, satellite used, cloud cover of last pass

5.3  Alert Panel
Slide-out panel on the right side of the globe, always accessible via a bell icon with badge count
Lists all unacknowledged alerts in descending severity then timestamp order
Each alert card shows: severity badge (CRITICAL/HIGH/MEDIUM in red/amber/blue), alert type, AOI name, description, and timestamp
Fly To button on each card: animates the Cesium camera to fly to the alert location and zoom in on the AOI
Acknowledge button marks the alert as reviewed (PATCH /alerts/{id}/acknowledge) and removes it from the unacknowledged list
New alerts arriving via WebSocket slide in at the top of the panel with an animation — no page refresh required
Critical alerts also trigger a browser notification (using the Web Notifications API — request permission on first load)

5.4  Timeline Scrubber
Horizontal timeline bar at the bottom of the globe, showing the last 30 days
Drag the scrubber handle to a point in time — the globe re-fetches detections from GET /detections with time_range ending at the selected timestamp
All detection markers on the globe update to show what was detected at that point in time
A small bar chart above the scrubber shows detection volume per day — gives analysts a quick view of activity spikes over time
A LIVE button on the right of the scrubber snaps back to real-time and re-connects the WebSocket stream

5.5  AOI Manager Page
Separate Next.js page (route: /aois) — not the globe, a dedicated management screen
Left panel: list of all existing AOIs with name, priority, last pass, status toggle (active/inactive)
Right panel: a 2D Leaflet.js map (npm install leaflet react-leaflet) with a polygon draw tool
Analyst draws a polygon on the Leaflet map, enters a name and priority, clicks Save — POST /aois is called and the new AOI appears immediately on the globe and begins being monitored
Delete button calls DELETE /aois/{id} with a confirmation modal
Priority dropdown (High/Medium/Low) controls how frequently the Scene Watcher checks for new imagery over this AOI

5.6  Export Functionality
Export button in the globe toolbar opens a modal with format options: PDF Mission Report, CSV Detections, KML for ArcGIS/Google Earth, GeoJSON
Time range selector and class filter in the export modal — analysts can export just aircraft detections from the last 24 hours if needed
PDF Mission Report generated by the FastAPI backend using ReportLab: includes mission timestamp, AOI name, total detection counts by class, annotated scene image, detection table with coordinates
CSV export contains: detection_id, class, subclass, confidence, lat, lon, heading, timestamp, satellite_source — importable directly into ArcGIS or Excel
KML export wraps each detection as a Placemark with icon styled by class — opens in Google Earth Pro with correct geolocation
All exports are triggered by GET /export?format=pdf&bbox=...&time_range=...&classes=... and return the file as a download

PHASE
06	End-to-End Integration & Testing
Pipeline wiring · WebSocket validation · ML accuracy testing · Load testing	DURATION
Week 3–4

Integration is where every assumption made in isolation gets tested against reality. Allocate significant time here — it will surface issues in tile coordinate transforms, WebSocket reliability, and Triton model I/O shapes.

6.1  Pipeline Integration Test
Manually trigger the Scene Watcher for a test AOI and trace the full chain: scene discovered → preprocessing queued → tiles created → Triton inference called → detections written to PostGIS → WebSocket event fires → globe marker appears
Verify coordinate accuracy: pick a known landmark (airport, port) within the AOI and confirm the detection marker lands on it in the globe — pixel-to-WGS84 transform errors will be obvious here
Verify tile overlap: check that objects at tile boundaries are detected correctly and not duplicated — implement NMS (Non-Maximum Suppression) across tile boundaries using the lat/lon coordinates
Verify SAR mode switch: ingest a Sentinel-1 SAR scene, confirm the pipeline routes it to the MSTAR CNN classifier branch and not the optical YOLOv8 branch

6.2  WebSocket Reliability Testing
Open 5 simultaneous browser tabs with the globe — verify all receive the same events in the same order
Simulate a WebSocket disconnect and verify the frontend reconnects and re-fetches missed detections from the REST API
Simulate a backend service restart mid-pipeline and verify Celery tasks retry correctly and no detections are lost

6.3  ML Model Validation

Component	Validation Test
YOLOv8 Detection	Run inference on 50 held-out DOTA tiles not used in training. Manually verify at least 20 detections visually — do the boxes look correct? Minimum acceptable mAP50: 65%
MSTAR SAR CNN	Run on full MSTAR 15° test split. Overall accuracy must be >95%. Per-class confusion matrix must show no catastrophic confusions (e.g. tank misclassified as AAgun is acceptable; tank as truck is not)
BIT Change Detection	Run on 20 LEVIR-CD test pairs. F1-score must be >0.85. Visually inspect 5 change masks — do the highlighted regions correspond to real changes in the image pair?
Grad-CAM	For 10 random detections, verify Grad-CAM heatmap highlights the object, not the background. If >30% of heatmaps are highlighting background, the classification model needs retraining
Alert System	Manually insert synthetic change events into PostGIS and verify the correct alert types fire within 5 minutes. Test all 6 alert types.
Export	Generate all 4 export formats (PDF, CSV, KML, GeoJSON) and open each in its target application. Verify coordinates in KML open at correct globe location in Google Earth.

6.4  Performance Benchmarks
Inference latency: time from tile arriving at Triton to detection written in PostGIS. Target: <500ms per tile
Globe update latency: time from detection written in PostGIS to marker appearing on globe (includes WebSocket delivery). Target: <2 seconds
Full pipeline latency: time from new scene discovered to first detection on globe. Target: <15 minutes for a typical AOI (the majority of time is download + preprocessing)
Export latency: PDF report generation for 500 detections. Target: <10 seconds
Concurrent globe clients: verify 10 simultaneous WebSocket connections all receive events without delay

PHASE
07	Production Docker Config, Monitoring & Demo Preparation
Final Docker Compose · Monitoring · Demo script · Submission checklist	DURATION
Week 4

7.1  Production Docker Compose Configuration
Add restart: unless-stopped to all service definitions — ensures services recover from crashes automatically
Configure Docker healthchecks for each service: FastAPI (/health endpoint), Triton (/v2/health/ready), PostGIS (pg_isready), Redis (redis-cli ping)
Configure Docker log rotation to prevent disk exhaustion during long-running demo periods
Add environment variable file (.env) with all credentials — Copernicus API key, Planet API key, PostGIS password, JWT secret — never hardcode
Write a startup script (start.sh) that: brings up Docker Compose, runs PostGIS migrations, seeds test AOIs, and opens the browser to the globe URL

7.2  Monitoring Setup
Add a Prometheus container and a Grafana container to Docker Compose
Triton exposes Prometheus metrics on port 8002 automatically — configure Prometheus to scrape it
Create a Grafana dashboard with: GPU utilisation %, inference latency per model, detections per hour, active WebSocket connections, Celery queue depth per queue
Configure Grafana alerts for: GPU memory >90%, inference latency >1s, Celery queue depth >100 tasks
Make the Grafana dashboard accessible from a /monitoring route in the Next.js app via iframe — gives the demo a professional operations centre feel

7.3  Demo Preparation
The demo experience is as important as the technology. Script it precisely.
Pre-load 2–3 real AOIs with historical Sentinel-2 data already processed and detections already in PostGIS — do not rely on live satellite passes during the demo (revisit cycles are unpredictable)
Pre-stage a T1/T2 image pair for one AOI with clear visible change between them — this is the centrepiece of the change detection demonstration
Load the Grad-CAM heatmaps for 5 interesting detections in advance so they appear instantly on click
Prepare a scripted 10-minute walkthrough: open globe → point out live AOI monitoring → click detection marker → show Grad-CAM → switch to SAR mode → show change detection overlay → show movement vector → alert fires → fly to alert location → export PDF
Have the training metric charts (loss curve, confusion matrix, mAP curve) ready to display as supporting slides — present them when explaining the ML depth

7.4  Final Delivery Checklist

#	Deliverable	Acceptance Criteria
1	Infrastructure	Docker Compose brings up all 10 services cleanly with docker compose up. All healthchecks pass within 60 seconds.
2	Satellite Ingestion	Scene Watcher polls Copernicus API, discovers new scenes, and triggers preprocessing for at least 2 active AOIs.
3	Preprocessing	Raw Sentinel-2 scene processed to normalised GeoTIFF tiles in under 5 minutes for a 50km² AOI.
4	YOLOv8 Detection	Fine-tuned model achieves >65% mAP50 on held-out DOTA test set. Training metric charts available.
5	MSTAR SAR CNN	ResNet-18 achieves >95% accuracy on MSTAR 15° test split. Confusion matrix shows no critical misclassifications.
6	BIT Change Detection	F1-score >0.85 on LEVIR-CD test set. Change masks visually correct on 5 manually inspected pairs.
7	Triton Serving	All 3 models loaded and healthy in Triton. Inference latency <500ms per tile under single-request load.
8	PostGIS Storage	Detections, change events, and alerts correctly written with valid WGS84 geometries. Spatial index verified.
9	WebSocket Streaming	Globe marker appears within 2 seconds of detection being written to PostGIS. Tested with 5 concurrent clients.
10	3D Globe	Detection markers, AOI polygons, movement vectors, and coverage layer all render correctly in Cesium. Timeline scrubber works.
11	Alert Panel	All 6 alert types fire correctly. Alerts appear in panel via WebSocket without page refresh. Acknowledge works.
12	AOI Manager	New AOI drawn on Leaflet map, saved via API, appears on globe, and begins being monitored within 1 polling cycle.
13	Grad-CAM	Heatmap visible in detection info panel. Highlights object, not background, for >70% of tested detections.
14	SAR Mode Toggle	Toggling SAR mode in globe switches model branch in inference pipeline. UI correctly reflects SAR mode state.
15	Export	PDF mission report, CSV, KML, and GeoJSON all generated and open correctly in target applications.
16	Monitoring	Grafana dashboard shows GPU utilisation, inference latency, and queue depth. Prometheus scraping Triton metrics.
17	Demo Script	10-minute scripted walkthrough rehearsed end-to-end at least twice with pre-loaded AOI data.



END OF MVP IMPLEMENTATION PLAN
RESTRICTED — FOR AUTHORISED PERSONNEL ONLY