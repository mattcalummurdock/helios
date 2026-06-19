#!/usr/bin/env python3
"""Run MSTAR -> YOLO -> BIT -> Triton export sequentially."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = REPO_ROOT / ".venv-train" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

LOG_DIR = REPO_ROOT / "ml" / "artifacts" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS = [
    ("organize", REPO_ROOT / "ml" / "scripts" / "organize_datasets.py", []),
    ("mstar", REPO_ROOT / "ml" / "scripts" / "train_mstar.py", []),
    ("yolo", REPO_ROOT / "ml" / "scripts" / "train_yolov8.py", []),
    ("bit", REPO_ROOT / "ml" / "scripts" / "train_bit_simple.py", []),
    ("export", REPO_ROOT / "ml" / "scripts" / "export_triton.py", []),
]


class Tee:
    """Write to terminal and a log file at the same time."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._file = log_path.open("a", encoding="utf-8", errors="replace")

    def write(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()
        self._file.write(text)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _log_line(tee: Tee, text: str) -> None:
    tee.write(text if text.endswith("\n") else text + "\n")


def run_step(name: str, script: Path, extra: list[str], tee: Tee) -> None:
    banner = f"\n{'=' * 60}\nSTEP: {name}\n{'=' * 60}\n"
    _log_line(tee, banner)

    cmd = [str(PYTHON), "-u", str(script), *extra]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        tee.write(line)
    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"train_all_{stamp}.log"
    tee = Tee(log_path)

    header = (
        f"train_all started at {datetime.now(timezone.utc).isoformat()}\n"
        f"python: {PYTHON}\n"
        f"log file: {log_path}\n"
    )
    _log_line(tee, header)
    print(f"Logging to {log_path}", flush=True)

    try:
        for name, script, extra in SCRIPTS:
            run_step(name, script, extra, tee)
        _log_line(tee, "\nAll training and export steps complete.\n")
    except subprocess.CalledProcessError as exc:
        _log_line(tee, f"\nFAILED (exit {exc.returncode}): {' '.join(exc.cmd)}\n")
        raise SystemExit(exc.returncode) from exc
    finally:
        tee.close()


if __name__ == "__main__":
    main()
