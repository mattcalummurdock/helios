"""Step 4: band normalisation to float32 [0,1] RGB or VV/VH stack."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio

logger = logging.getLogger(__name__)


def _normalize_band(data: np.ndarray) -> np.ndarray:
    data = data.astype("float32")
    vmin, vmax = float(np.nanmin(data)), float(np.nanmax(data))
    if vmax - vmin < 1e-6:
        return np.zeros_like(data, dtype="float32")
    return np.clip((data - vmin) / (vmax - vmin), 0, 1)


def normalize_bands(input_dir: Path, sensor_type: str, output_path: Path) -> Path:
    tifs = {p.stem.upper(): p for p in input_dir.glob("*.tif")}

    if sensor_type == "sentinel-1":
        band_order = [tifs[k] for k in ("VV", "VH") if k in tifs]
        if not band_order:
            band_order = sorted(input_dir.glob("*.tif"))[:2]
    elif sensor_type == "planet":
        band_order = sorted(input_dir.glob("*.tif"))[:3]
    else:
        for rgb_keys in [("B04", "B03", "B02"), ("B4", "B3", "B2")]:
            if all(k in tifs for k in rgb_keys):
                band_order = [tifs[k] for k in rgb_keys]
                break
        else:
            band_order = sorted(input_dir.glob("*.tif"))[:3]

    if not band_order:
        raise ValueError(f"No bands found in {input_dir}")

    bands = []
    profile = None
    for path in band_order:
        with rasterio.open(path) as src:
            bands.append(_normalize_band(src.read(1)))
            if profile is None:
                profile = src.profile.copy()

    stack = np.stack(bands, axis=0)
    profile.update(count=stack.shape[0], dtype="float32", compress="lzw")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(stack)

    logger.info("Wrote normalized stack %s (%d bands)", output_path, stack.shape[0])
    return output_path
