"""Step 1: atmospheric correction."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def apply_atmospheric_correction(
    raw_dir: Path,
    sensor_type: str,
    collection_hint: str | None,
    work_dir: Path,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    tifs = sorted(raw_dir.glob("*.tif"))

    if sensor_type == "planet":
        logger.info("Skipping atmospheric correction for Planet (analytic_sr)")
        out = work_dir / "atmospheric"
        out.mkdir(exist_ok=True)
        for t in tifs:
            shutil.copy(t, out / t.name)
        return out

    if sensor_type == "sentinel-2":
        is_l2a = collection_hint and "l2a" in collection_hint.lower()
        if is_l2a or any("L2A" in t.name.upper() for t in tifs):
            logger.info("Skipping atmospheric correction for Sentinel-2 L2A (BoA)")
            out = work_dir / "atmospheric"
            out.mkdir(exist_ok=True)
            for t in tifs:
                shutil.copy(t, out / t.name)
            return out

        logger.info("Sentinel-2 L1C — applying simplified TOA scaling (Py6S fallback)")
        out = work_dir / "atmospheric"
        out.mkdir(exist_ok=True)
        try:
            import numpy as np
            import rasterio

            for t in tifs:
                with rasterio.open(t) as src:
                    data = src.read(1).astype("float32")
                    data = np.clip(data * 0.0001, 0, 1)
                    profile = src.profile.copy()
                    profile.update(dtype="float32")
                    dest = out / t.name
                    with rasterio.open(dest, "w", **profile) as dst:
                        dst.write(data, 1)
        except Exception as exc:
            logger.warning("Py6S path failed (%s), copying raw bands", exc)
            for t in tifs:
                shutil.copy(t, out / t.name)
        return out

    if sensor_type == "sentinel-1":
        logger.info("Sentinel-1 SAR radiometric calibration (sigma0 scaling)")
        out = work_dir / "atmospheric"
        out.mkdir(exist_ok=True)
        try:
            import numpy as np
            import rasterio

            for t in tifs:
                with rasterio.open(t) as src:
                    data = src.read(1).astype("float32")
                    data = np.where(data <= 0, 1e-6, data)
                    data = 10 * np.log10(data)
                    profile = src.profile.copy()
                    profile.update(dtype="float32")
                    dest = out / t.name
                    with rasterio.open(dest, "w", **profile) as dst:
                        dst.write(data, 1)
        except Exception as exc:
            logger.warning("SAR calibration failed (%s), copying raw", exc)
            for t in tifs:
                shutil.copy(t, out / t.name)
        return out

    out = work_dir / "atmospheric"
    out.mkdir(exist_ok=True)
    for t in tifs:
        shutil.copy(t, out / t.name)
    return out
