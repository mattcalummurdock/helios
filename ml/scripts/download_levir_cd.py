#!/usr/bin/env python3
"""Download LEVIR-CD dataset."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import DATASETS_DIR  # noqa: E402

LEVIR_URLS = [
    "https://justchenhao.github.io/LEVIR/CD_LEVIR.zip",
    "https://www.dropbox.com/s/18fb5jo0npu5evm/LEVIR-CD256.zip?dl=1",
]


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"Already downloaded: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"Downloading {url}")
    downloaded = 0
    with httpx.stream("GET", url, timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"\r  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB", end="", flush=True)
                else:
                    print(f"\r  {downloaded / 1e6:.1f} MB", end="", flush=True)
    print("\n  Done.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DATASETS_DIR / "levir_cd")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    zip_path = args.output / "CD_LEVIR.zip"
    marker = args.output / ".extracted"

    if not zip_path.exists() or zip_path.stat().st_size < 1_000_000:
        last_err = None
        for url in LEVIR_URLS:
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
            raise SystemExit(f"All LEVIR-CD mirrors failed: {last_err}")

    if marker.exists():
        print(f"Already extracted: {args.output}")
        return

    print(f"Extracting {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(args.output)
    marker.touch()
    print(f"LEVIR-CD extracted to {args.output}")


if __name__ == "__main__":
    main()
