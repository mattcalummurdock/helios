#!/usr/bin/env python3
"""Train MSTAR ResNet18+CBAM with 17° train / 15° test split."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.models.mstar_cnn import MStarCNN  # noqa: E402
from ml.paths import ARTIFACTS_DIR, DATASETS_DIR  # noqa: E402

ANGLE_RE = re.compile(r"(\d{2})\s*deg|depression[_-]?(\d{2})|(\d{2})[_-]degree", re.I)
# MSTAR chip filename prefixes (Kaggle padded_imgs: HB = 17°, HA = 15°)
MSTAR_PREFIX_ANGLE = {"HA": 15, "HB": 17, "HC": 15, "HD": 17}


def infer_angle(path: Path) -> int | None:
    prefix = path.stem[:2].upper()
    if prefix in MSTAR_PREFIX_ANGLE:
        return MSTAR_PREFIX_ANGLE[prefix]
    for part in path.parts:
        m = ANGLE_RE.search(part)
        if m:
            return int(next(g for g in m.groups() if g))
    return None


def discover_samples(root: Path) -> list[tuple[Path, str, int | None]]:
    samples: list[tuple[Path, str, int | None]] = []
    for cls_dir in sorted(root.iterdir()):
        if not cls_dir.is_dir():
            continue
        class_name = cls_dir.name
        for img in cls_dir.rglob("*"):
            if img.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif"}:
                samples.append((img, class_name, infer_angle(img)))
    return samples


class MStarDataset(Dataset):
    def __init__(self, samples: list[tuple[Path, str]], class_to_idx: dict[str, int], transform) -> None:
        self.samples = samples
        self.class_to_idx = class_to_idx
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, cls_name = self.samples[idx]
        img = Image.open(path).convert("L")
        x = self.transform(img)
        y = self.class_to_idx[cls_name]
        return x, y


def build_transforms(train: bool):
    base = [transforms.Resize((224, 224)), transforms.ToTensor()]
    if train:
        base.insert(1, transforms.RandomHorizontalFlip())
        base.insert(1, transforms.RandomRotation(10))
    return transforms.Compose(base)


def split_by_angle(all_samples: list[tuple[Path, str, int | None]]) -> tuple[list, list]:
    train, test = [], []
    has_15 = any(a == 15 for _, _, a in all_samples)
    has_17 = any(a == 17 for _, _, a in all_samples)
    if has_15 and has_17:
        for path, cls, angle in all_samples:
            if angle == 15:
                test.append((path, cls))
            elif angle == 17:
                train.append((path, cls))
            else:
                train.append((path, cls))
        return train, test

    # Single depression angle (e.g. Kaggle Padded_imgs HB-only): stratified 80/20 per class
    import random

    rng = random.Random(42)
    by_class: dict[str, list[Path]] = {}
    for path, cls, _ in all_samples:
        by_class.setdefault(cls, []).append(path)
    for cls, paths in by_class.items():
        paths = sorted(paths)
        rng.shuffle(paths)
        n = int(len(paths) * 0.8)
        train.extend((p, cls) for p in paths[:n])
        test.extend((p, cls) for p in paths[n:])
    return train, test


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=DATASETS_DIR / "mstar",
        help="MSTAR root with class subfolders (default: ml/datasets/mstar)",
    )
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    all_samples = discover_samples(args.data)
    if not all_samples:
        raise SystemExit(f"No MSTAR images under {args.data}")

    classes = sorted({s[1] for s in all_samples})
    class_to_idx = {c: i for i, c in enumerate(classes)}
    train_samples, test_samples = split_by_angle(all_samples)
    print(f"Train={len(train_samples)} Test={len(test_samples)} Classes={len(classes)}")

    train_ds = MStarDataset(train_samples, class_to_idx, build_transforms(True))
    test_ds = MStarDataset(test_samples, class_to_idx, build_transforms(False))
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch, shuffle=False, num_workers=0)

    model = MStarCNN(num_classes=len(classes)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss()

    out_dir = ARTIFACTS_DIR / "mstar"
    out_dir.mkdir(parents=True, exist_ok=True)
    best_acc = 0.0
    best_path = out_dir / "best.pth"

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for x, y in test_loader:
                x, y = x.to(device), y.to(device)
                pred = model(x).argmax(dim=1)
                correct += (pred == y).sum().item()
                total += y.size(0)
        acc = correct / max(total, 1)
        print(f"Epoch {epoch + 1}/{args.epochs} loss={total_loss / len(train_loader):.4f} acc={acc:.4f}")
        if acc > best_acc:
            best_acc = acc
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "classes": classes,
                    "class_to_idx": class_to_idx,
                    "accuracy": acc,
                },
                best_path,
            )

    # Confusion matrix on test set
    ckpt = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    y_true, y_pred = [], []
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            pred = model(x).argmax(dim=1).cpu().numpy()
            y_pred.extend(pred.tolist())
            y_true.extend(y.numpy().tolist())

    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(10, 8))
    ConfusionMatrixDisplay(cm, display_labels=classes).plot(ax=ax, xticks_rotation=45)
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix.png", dpi=150)
    plt.close(fig)

    with open(out_dir / "classes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(classes))

    print(f"Best accuracy: {best_acc:.4f} saved to {best_path}")


if __name__ == "__main__":
    main()
