#!/usr/bin/env python3
"""Export trained models to Triton model repository with config.pbtxt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.models.mstar_cnn import MStarCNN  # noqa: E402
from ml.paths import ARTIFACTS_DIR, MODELS_REPO  # noqa: E402


def write_yolo_config(model_dir: Path, use_tensorrt: bool) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    version_dir = model_dir / "1"
    version_dir.mkdir(parents=True, exist_ok=True)
    platform = "tensorrt_plan" if use_tensorrt else "onnxruntime_onnx"
    ext = "plan" if use_tensorrt else "onnx"
    pbtxt = f"""name: "yolov8_detection"
platform: "{platform}"
max_batch_size: 8
input [
  {{
    name: "images"
    data_type: TYPE_FP32
    dims: [ 3, 640, 640 ]
  }}
]
output [
  {{
    name: "output0"
    data_type: TYPE_FP32
    dims: [ -1, -1 ]
  }}
]
"""
    (model_dir / "config.pbtxt").write_text(pbtxt, encoding="utf-8")
    return version_dir / f"model.{ext}"


def write_mstar_config(model_dir: Path) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    version_dir = model_dir / "1"
    version_dir.mkdir(parents=True, exist_ok=True)
    pbtxt = """name: "mstar_sar"
platform: "onnxruntime_onnx"
max_batch_size: 8
input [
  {
    name: "input"
    data_type: TYPE_FP32
    dims: [ 1, 224, 224 ]
  }
]
output [
  {
    name: "output"
    data_type: TYPE_FP32
    dims: [ 8 ]
  }
]
"""
    (model_dir / "config.pbtxt").write_text(pbtxt, encoding="utf-8")
    return version_dir / "model.onnx"


def write_bit_config(model_dir: Path) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    version_dir = model_dir / "1"
    version_dir.mkdir(parents=True, exist_ok=True)
    pbtxt = """name: "bit_change"
platform: "onnxruntime_onnx"
max_batch_size: 4
input [
  {
    name: "t1"
    data_type: TYPE_FP32
    dims: [ 3, 256, 256 ]
  },
  {
    name: "t2"
    data_type: TYPE_FP32
    dims: [ 3, 256, 256 ]
  }
]
output [
  {
    name: "change_mask"
    data_type: TYPE_FP32
    dims: [ 1, 256, 256 ]
  }
]
"""
    (model_dir / "config.pbtxt").write_text(pbtxt, encoding="utf-8")
    return version_dir / "model.onnx"


def export_yolo(weights: Path, onnx_path: Path) -> None:
    from ultralytics import YOLO

    if not weights.exists():
        print(f"YOLO weights missing: {weights}")
        return
    model = YOLO(str(weights))
    model.export(format="onnx", imgsz=640, opset=17, simplify=True)
    exported = weights.parent / "best.onnx"
    if not exported.exists():
        exported = weights.with_suffix(".onnx")
    if exported.exists():
        onnx_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(exported, onnx_path)
        print(f"YOLO ONNX -> {onnx_path}")


def export_mstar(checkpoint: Path, onnx_path: Path, num_classes: int = 8) -> None:
    model = MStarCNN(num_classes=num_classes)
    if checkpoint.exists():
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        if "classes" in ckpt:
            num_classes = len(ckpt["classes"])
    model.eval()
    dummy = torch.randn(1, 1, 224, 224)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )
    print(f"MSTAR ONNX -> {onnx_path}")


def export_bit(checkpoint: Path, onnx_path: Path) -> None:
    """Export trained SimpleBIT (dual t1/t2 inputs)."""
    import torch.nn as nn

    sys.path.insert(0, str(REPO_ROOT))
    from ml.scripts.train_bit_simple import SimpleBIT  # noqa: WPS433

    class BitWrapper(nn.Module):
        def __init__(self, core: nn.Module) -> None:
            super().__init__()
            self.core = core

        def forward(self, t1, t2):
            x = torch.cat([t1, t2], dim=1)
            return torch.sigmoid(self.core(x))

    model = SimpleBIT()
    if checkpoint.exists():
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
    wrapper = BitWrapper(model)
    wrapper.eval()
    t1 = torch.randn(1, 3, 256, 256)
    t2 = torch.randn(1, 3, 256, 256)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        wrapper,
        (t1, t2),
        str(onnx_path),
        input_names=["t1", "t2"],
        output_names=["change_mask"],
        opset_version=17,
    )
    print(f"BIT ONNX -> {onnx_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", type=Path, default=MODELS_REPO)
    parser.add_argument("--tensorrt", action="store_true")
    args = parser.parse_args()

    yolo_weights = ARTIFACTS_DIR / "yolo" / "best.pt"
    mstar_ckpt = ARTIFACTS_DIR / "mstar" / "best.pth"
    bit_ckpt = ARTIFACTS_DIR / "bit" / "best.pth"

    yolo_dir = args.models_dir / "yolov8_detection"
    yolo_onnx = write_yolo_config(yolo_dir, args.tensorrt)
    if not args.tensorrt:
        export_yolo(yolo_weights, yolo_onnx)

    mstar_dir = args.models_dir / "mstar_sar"
    mstar_onnx = write_mstar_config(mstar_dir)
    export_mstar(mstar_ckpt, mstar_onnx)

    bit_dir = args.models_dir / "bit_change"
    bit_onnx = write_bit_config(bit_dir)
    export_bit(bit_ckpt, bit_onnx)

    manifest = {
        "yolov8_detection": str(yolo_onnx),
        "mstar_sar": str(mstar_onnx),
        "bit_change": str(bit_onnx),
    }
    with open(args.models_dir / "export_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("Triton export complete. Restart triton and check /v2/models/ready")


if __name__ == "__main__":
    main()
