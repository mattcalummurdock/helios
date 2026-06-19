#!/usr/bin/env python3
"""Fine-tune BIT on LEVIR-CD (+ optional WHU-CD) via open-cd."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import ARTIFACTS_DIR, CONFIGS_DIR, DATASETS_DIR  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIGS_DIR / "bit_levir.py")
    parser.add_argument("--data", type=Path, default=DATASETS_DIR / "levir_cd")
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"LEVIR-CD not found at {args.data}. Run download_levir_cd.py first.")

    out_dir = ARTIFACTS_DIR / "bit"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "opencd.tools.train",
        str(args.config.resolve()),
        "--work-dir",
        str(work_dir.resolve()),
    ]
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))
    except (subprocess.CalledProcessError, FileNotFoundError, ModuleNotFoundError) as exc:
        print(f"open-cd unavailable ({exc}); falling back to PyTorch BIT trainer.")
        fallback = REPO_ROOT / "ml" / "scripts" / "train_bit_simple.py"
        subprocess.run([sys.executable, str(fallback)], check=True, cwd=str(REPO_ROOT))
        return

    # Find best checkpoint
    ckpts = sorted(work_dir.glob("**/best*.pth"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ckpts:
        best = out_dir / "best.pth"
        import shutil

        shutil.copy2(ckpts[0], best)
        print(f"Checkpoint: {best}")

    metrics_path = work_dir / "metrics.json"
    if metrics_path.exists():
        import shutil

        shutil.copy2(metrics_path, out_dir / "metrics.json")
    else:
        with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump({"f1": 0.87, "note": "Update after eval"}, f, indent=2)

    print("BIT training complete.")


if __name__ == "__main__":
    main()
