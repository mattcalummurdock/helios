"""Grad-CAM heatmap generation for YOLOv8 detections."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import numpy as np

from helios_common.config import settings

logger = logging.getLogger(__name__)


def generate_yolo_gradcam(
    crop_path: str | Path,
    yolo_weights_or_onnx: str | Path | None = None,
) -> bytes:
    """Generate Grad-CAM PNG bytes for a detection crop."""
    crop_path = Path(crop_path)
    weights = Path(yolo_weights_or_onnx or settings.yolo_weights_path)

    try:
        return _gradcam_pytorch(crop_path, weights)
    except Exception as exc:
        logger.warning("Grad-CAM fallback for %s: %s", crop_path, exc)
        return _gradcam_fallback(crop_path)


def _gradcam_pytorch(crop_path: Path, weights: Path) -> bytes:
    import cv2
    import torch
    from PIL import Image

    img_bgr = cv2.imread(str(crop_path))
    if img_bgr is None:
        raise FileNotFoundError(crop_path)

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb).resize((640, 640))
    input_tensor = torch.from_numpy(np.array(pil)).float().permute(2, 0, 1).unsqueeze(0) / 255.0

    from ultralytics import YOLO

    model = YOLO(str(weights))
    torch_model = model.model
    torch_model.eval()

    target_layers = [torch_model.model[-2]]
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.image import show_cam_on_image

    cam = GradCAM(model=torch_model, target_layers=target_layers)
    grayscale = cam(input_tensor=input_tensor, targets=None)[0, :]
    cam_image = show_cam_on_image(
        input_tensor.squeeze(0).permute(1, 2, 0).numpy(),
        grayscale,
        use_rgb=True,
    )

    ok, buf = cv2.imencode(".png", cv2.cvtColor(cam_image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Failed to encode Grad-CAM PNG")
    return buf.tobytes()


def _gradcam_fallback(crop_path: Path) -> bytes:
    """Simple edge-based heatmap when full Grad-CAM stack unavailable."""
    import cv2

    img = cv2.imread(str(crop_path))
    if img is None:
        raise FileNotFoundError(crop_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    heat = cv2.applyColorMap(edges, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img, 0.6, heat, 0.4, 0)
    ok, buf = cv2.imencode(".png", overlay)
    if not ok:
        raise RuntimeError("Failed to encode fallback Grad-CAM PNG")
    return buf.tobytes()


def save_gradcam_png(crop_path: str | Path, output_path: str | Path) -> str:
    png_bytes = generate_yolo_gradcam(crop_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png_bytes)
    return str(out)
