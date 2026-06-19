#!/usr/bin/env python3
"""Download DOTA v1.0 for YOLO-OBB training."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import DATASETS_DIR  # noqa: E402

# Official Aliyun OSS mirrors return 404 as of 2026; Ultralytics hosts a YOLO-ready DOTA v1.0 pack.
DOTA_URLS = [
    "https://github.com/ultralytics/assets/releases/download/v0.0.0/DOTAv1.zip",
]


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 10_000_000:
        print(f"Already downloaded: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
        return

    print(f"Downloading {url}")
    print(f"  -> {dest}")
    downloaded = 0
    with httpx.stream("GET", url, timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"\r  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB", end="", flush=True)
                else:
                    print(f"\r  {downloaded / 1e6:.1f} MB", end="", flush=True)
    print("\n  Done.")


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    marker = dest_dir / ".extracted"
    if marker.exists():
        print(f"Already extracted: {dest_dir}")
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {zip_path.name} -> {dest_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    marker.touch()
    print(f"Extracted to {dest_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download DOTA v1.0 (Ultralytics YOLO pack)")
    parser.add_argument("--output", type=Path, default=DATASETS_DIR / "dota")
    args = parser.parse_args()

    out = args.output
    zip_path = out / "DOTAv1.zip"
    last_err = None

    if not zip_path.exists() or zip_path.stat().st_size < 10_000_000:
        for url in DOTA_URLS:
            try:
                download_file(url, zip_path)
                last_err = None
                break
            except Exception as exc:
                print(f"  Failed: {exc}")
                last_err = exc
                if zip_path.exists():
                    zip_path.unlink()

    if last_err:
        print(
            "All DOTA mirrors failed. Manual: https://captain-whu.github.io/DOTA/dataset.html "
            f"(Google Drive) -> extract under {out}"
        )
        raise SystemExit(1) from last_err

    extract_zip(zip_path, out)
    print("DOTA download complete.")


if __name__ == "__main__":
    main()
