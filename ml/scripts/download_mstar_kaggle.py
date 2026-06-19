#!/usr/bin/env python3
"""Download MSTAR 8-class dataset from Kaggle."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from ml.paths import DATASETS_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DATASETS_DIR / "mstar")
    args = parser.parse_args()

    username = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    if not username or not key:
        raise SystemExit(
            "Set KAGGLE_USERNAME and KAGGLE_KEY in .env or environment. "
            "Dataset: https://www.kaggle.com/datasets/atreyamajumdar/mstar-dataset-8-classes"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    cmd = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        "atreyamajumdar/mstar-dataset-8-classes",
        "-p",
        str(args.output),
        "--unzip",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # Normalize: expect class folders under output
    print(f"MSTAR downloaded to {args.output}")
    for item in args.output.iterdir():
        print(f"  {item.name}")


if __name__ == "__main__":
    main()
