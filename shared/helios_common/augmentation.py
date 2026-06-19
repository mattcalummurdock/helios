"""Training-only augmentation pipeline for Phase 3 YOLOv8 fine-tuning."""

from __future__ import annotations

import albumentations as A
from albumentations.pytorch import ToTensorV2


def get_training_augmentation(image_size: int = 640) -> A.Compose:
    """Albumentations Compose per MVP §2.4 — not used during inference."""
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.Rotate(limit=90, p=0.5, border_mode=0),
            A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
            A.Cutout(num_holes=4, max_h_size=32, max_w_size=32, p=0.3),
            A.Resize(image_size, image_size),
            ToTensorV2(),
        ],
        bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]),
    )
