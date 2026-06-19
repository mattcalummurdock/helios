# Helios ML Training Guide

Train models on **host WSL2** with CUDA (RTX 3060 6GB). Docker runs Triton + inference workers only.

## Setup

```bash
cd /mnt/c/Users/MSI/Desktop/helios   # or your repo path
python3 -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements-train.txt
pip install -e shared/  # optional; scripts add repo to PYTHONPATH
```

Add to `.env`:

```
KAGGLE_USERNAME=your-user
KAGGLE_KEY=your-key
ML_DATA_DIR=./ml/datasets
YOLO_MODEL_SIZE=s
```

## 1. Datasets

```bash
python ml/scripts/download_dota.py
python ml/scripts/convert_dota_obb.py

python ml/scripts/download_mstar_kaggle.py
python ml/scripts/download_levir_cd.py
python ml/scripts/download_whu_cd.py   # manual WHU files if needed
```

## 2. Training (VRAM-safe defaults)

| Model | Command | Output |
|-------|---------|--------|
| YOLOv8-OBB | `python ml/scripts/train_yolov8.py` | `ml/artifacts/yolo/best.pt` + 4 PNG charts |
| MSTAR CNN | `python ml/scripts/train_mstar.py` | `ml/artifacts/mstar/best.pth` + confusion matrix |
| BIT | `python ml/scripts/train_bit.py` | `ml/artifacts/bit/best.pth` + metrics.json |

Training takes hours on GPU. Charts must exist under `ml/artifacts/yolo/` before Phase 3 sign-off.

## 3. Export to Triton

```bash
python ml/scripts/export_triton.py
# Optional TensorRT (host with trtexec):
bash ml/scripts/export_tensorrt.sh
docker compose restart triton
```

Verify:

```bash
curl http://localhost:8000/v2/models/yolov8_detection/ready
curl http://localhost:8000/v2/models/mstar_sar/ready
curl http://localhost:8000/v2/models/bit_change/ready
```

## 4. End-to-end inference

After preprocessing produces tiles:

```powershell
docker compose exec inference-service celery -A helios_common.celery_app call inference_service.tasks.run_inference --args='[1, []]'
curl http://localhost:8080/detections/1/gradcam
```

## VRAM notes (3060 6GB)

- YOLO: `yolov8s-obb`, batch 4, FP16
- MSTAR: batch 16
- BIT: batch 2
- Triton serves ONNX by default; TensorRT optional via `export_tensorrt.sh`
