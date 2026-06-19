#!/usr/bin/env python3
"""Train YOLOv8-OBB on DOTA MVP classes (VRAM-safe yolov8s, batch 4)."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import ARTIFACTS_DIR, CONFIGS_DIR  # noqa: E402


def save_training_charts(results_csv: Path, out_dir: Path, model, data_yaml: Path) -> None:
    import pandas as pd

    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(results_csv)

    # 1. Loss curve
    fig, ax = plt.subplots(figsize=(10, 6))
    for col in ["train/box_loss", "train/cls_loss", "train/dfl_loss"]:
        if col in df.columns:
            ax.plot(df["epoch"], df[col], label=col.split("/")[-1])
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.legend()
    ax.set_title("Training Loss")
    fig.tight_layout()
    fig.savefig(out_dir / "loss_curve.png", dpi=150)
    plt.close(fig)

    # 2. mAP curve
    fig, ax = plt.subplots(figsize=(10, 6))
    map_col = "metrics/mAP50(B)" if "metrics/mAP50(B)" in df.columns else "metrics/mAP50"
    if map_col in df.columns:
        ax.plot(df["epoch"], df[map_col], label="mAP50")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("mAP50")
    ax.legend()
    ax.set_title("Validation mAP50")
    fig.tight_layout()
    fig.savefig(out_dir / "map_curve.png", dpi=150)
    plt.close(fig)

    # 3. Confusion matrix + 4. PR curves via ultralytics val
    metrics = model.val(data=str(data_yaml), split="test", plots=True)
    run_dir = Path(model.trainer.save_dir) if hasattr(model, "trainer") else out_dir
    for name in ("confusion_matrix.png", "confusion_matrix_normalized.png"):
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / "confusion_matrix.png")
            break
    pr_src = run_dir / "PR_curve.png"
    if pr_src.exists():
        shutil.copy2(pr_src, out_dir / "pr_curves.png")
    else:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "PR curves generated during val", ha="center")
        ax.axis("off")
        fig.savefig(out_dir / "pr_curves.png", dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=CONFIGS_DIR / "dota_ultralytics.yaml")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--model-size", type=str, default=os.getenv("YOLO_MODEL_SIZE", "s"))
    args = parser.parse_args()

    from ultralytics import YOLO

    out_dir = ARTIFACTS_DIR / "yolo"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = f"yolov8{args.model_size}-obb.pt"
    model = YOLO(model_name)

    results = model.train(
        data=str(args.data.resolve()),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        lr0=0.001,
        cos_lr=True,
        warmup_epochs=3,
        amp=True,
        project=str(out_dir),
        name="train",
        exist_ok=True,
        save=True,
        plots=True,
    )

    best_src = Path(results.save_dir) / "weights" / "best.pt"
    best_dst = out_dir / "best.pt"
    if best_src.exists():
        shutil.copy2(best_src, best_dst)
        print(f"Saved {best_dst}")

    results_csv = Path(results.save_dir) / "results.csv"
    if results_csv.exists():
        save_training_charts(results_csv, out_dir, model, args.data)
    else:
        print("Warning: results.csv not found; charts may be incomplete")

    print("Training complete. Artifacts in", out_dir)


if __name__ == "__main__":
    main()
