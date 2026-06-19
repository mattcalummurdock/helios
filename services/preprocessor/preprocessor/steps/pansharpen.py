"""Step 3: pansharpening (Planet only via OTB)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def pansharpen(input_dir: Path, sensor_type: str, work_dir: Path) -> Path:
    out_dir = work_dir / "pansharpen"
    out_dir.mkdir(parents=True, exist_ok=True)

    if sensor_type != "planet":
        logger.info("Skipping pansharpening for %s", sensor_type)
        for src in input_dir.glob("*.tif"):
            shutil.copy(src, out_dir / src.name)
        return out_dir

    tifs = sorted(input_dir.glob("*.tif"))
    if len(tifs) < 2:
        for src in tifs:
            shutil.copy(src, out_dir / src.name)
        return out_dir

    pan = tifs[0]
    ms = tifs[1]
    dest = out_dir / "pansharpened.tif"
    cmd = [
        "otbcli_GramSchmidtPanSharpening",
        "-inp",
        str(pan),
        "-inm",
        str(ms),
        "-out",
        str(dest),
    ]
    try:
        logger.info("Running OTB Gram-Schmidt: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("OTB pansharpening failed (%s), using multispectral", exc)
        shutil.copy(ms, dest)

    return out_dir
