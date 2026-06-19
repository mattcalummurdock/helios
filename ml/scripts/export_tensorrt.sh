#!/usr/bin/env bash
# Optional TensorRT FP16 engine for YOLO (requires trtexec on host)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ONNX="${REPO_ROOT}/models/yolov8_detection/1/model.onnx"
PLAN="${REPO_ROOT}/models/yolov8_detection/1/model.plan"
if [[ ! -f "$ONNX" ]]; then
  echo "Run export_triton.py first: $ONNX not found"
  exit 1
fi
trtexec --onnx="$ONNX" --saveEngine="$PLAN" --fp16
echo "Update config.pbtxt platform to tensorrt_plan and restart Triton"
