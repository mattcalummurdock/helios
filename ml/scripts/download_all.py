#!/usr/bin/env python3
"""Download all Phase 3 training datasets (DOTA, LEVIR-CD, WHU-CD)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    "download_dota.py",
    "download_levir_cd.py",
    "download_whu_cd.py",
]


def main() -> None:
    for name in SCRIPTS:
        script = REPO_ROOT / "ml" / "scripts" / name
        print(f"\n{'=' * 60}\nRunning {name}\n{'=' * 60}")
        subprocess.run([sys.executable, str(script)], check=True, cwd=str(REPO_ROOT))
    print("\nAll dataset downloads complete.")


if __name__ == "__main__":
    main()
