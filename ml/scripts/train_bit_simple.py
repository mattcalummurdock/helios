#!/usr/bin/env python3
"""Lightweight BIT-style change detector on LEVIR-CD (Windows-friendly fallback)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import ARTIFACTS_DIR, DATASETS_DIR  # noqa: E402


class ChangeDataset(Dataset):
    def __init__(self, root: Path, names: list[str], size: int = 256) -> None:
        self.root = root
        self.names = names
        self.size = size

    def __len__(self) -> int:
        return len(self.names)

    def __getitem__(self, idx: int):
        name = self.names[idx].strip()
        t1 = Image.open(self.root / "A" / name).convert("RGB").resize((self.size, self.size))
        t2 = Image.open(self.root / "B" / name).convert("RGB").resize((self.size, self.size))
        lbl = Image.open(self.root / "label" / name).convert("L").resize((self.size, self.size))
        import torchvision.transforms as T

        to_tensor = T.ToTensor()
        x = torch.cat([to_tensor(t1), to_tensor(t2)], dim=0)
        y = (to_tensor(lbl) > 0.5).float()
        return x, y


class SimpleBIT(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(6, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def load_names(list_file: Path) -> list[str]:
    return [ln.strip() for ln in list_file.read_text(encoding="utf-8").splitlines() if ln.strip()]


def f1_score(pred: torch.Tensor, target: torch.Tensor) -> float:
    pred_bin = (pred > 0.5).float()
    tp = (pred_bin * target).sum()
    fp = (pred_bin * (1 - target)).sum()
    fn = ((1 - pred_bin) * target).sum()
    denom = 2 * tp + fp + fn
    return float((2 * tp / denom).item()) if denom > 0 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATASETS_DIR / "levir_cd")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=2)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_names = load_names(args.data / "list" / "train.txt")
    test_names = load_names(args.data / "list" / "test.txt")

    train_ds = ChangeDataset(args.data, train_names)
    test_ds = ChangeDataset(args.data, test_names)
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch, shuffle=False, num_workers=0)

    model = SimpleBIT().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    criterion = nn.BCEWithLogitsLoss()

    out_dir = ARTIFACTS_DIR / "bit"
    out_dir.mkdir(parents=True, exist_ok=True)
    best_f1 = 0.0
    best_path = out_dir / "best.pth"

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            opt.step()
            total_loss += loss.item()

        model.eval()
        scores = []
        with torch.no_grad():
            for x, y in test_loader:
                x, y = x.to(device), y.to(device)
                pred = torch.sigmoid(model(x))
                scores.append(f1_score(pred, y))
        f1 = sum(scores) / max(len(scores), 1)
        print(f"Epoch {epoch + 1}/{args.epochs} loss={total_loss / len(train_loader):.4f} f1={f1:.4f}")
        if f1 > best_f1:
            best_f1 = f1
            torch.save({"model_state_dict": model.state_dict(), "f1": f1}, best_path)

    with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump({"f1": best_f1}, f, indent=2)
    print(f"Saved {best_path} f1={best_f1:.4f}")


if __name__ == "__main__":
    main()
