#!/usr/bin/env python3
"""Normalize all Phase 3 datasets under ml/datasets/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import DATASETS_DIR  # noqa: E402

MSTAR_SRC = REPO_ROOT / "datasets" / "Padded_imgs"
MSTAR_DST = DATASETS_DIR / "mstar"


def move_contents(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if target.exists():
            continue
        shutil.move(str(item), str(target))
    print(f"Moved {src} -> {dst}")


def flatten_nested(parent: Path, nested_name: str) -> None:
    nested = parent / nested_name
    if not nested.is_dir():
        return
    for item in nested.iterdir():
        target = parent / item.name
        if target.exists():
            continue
        shutil.move(str(item), str(target))
    nested.rmdir()
    print(f"Flattened {nested} into {parent}")


def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    # MSTAR: datasets/Padded_imgs -> ml/datasets/mstar/
    if MSTAR_SRC.exists():
        move_contents(MSTAR_SRC, MSTAR_DST)
        if MSTAR_SRC.exists() and not any(MSTAR_SRC.iterdir()):
            MSTAR_SRC.rmdir()

    flatten_nested(DATASETS_DIR / "levir_cd", "LEVIR-CD256")
    flatten_nested(DATASETS_DIR / "whu_cd", "WHU-CD-256")

    # Remove failed empty dota_raw if present
    dota_raw = DATASETS_DIR / "dota_raw"
    if dota_raw.exists() and not any(dota_raw.rglob("*.png")) and not any(dota_raw.rglob("*.jpg")):
        shutil.rmtree(dota_raw, ignore_errors=True)

    print("Dataset layout:")
    for name in ("mstar", "dota", "levir_cd", "whu_cd"):
        p = DATASETS_DIR / name
        status = "OK" if p.exists() else "MISSING"
        print(f"  {name}: {status} -> {p}")


if __name__ == "__main__":
    main()
