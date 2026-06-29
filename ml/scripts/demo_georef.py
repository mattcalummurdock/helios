#!/usr/bin/env python3
"""Convert demo JPG chips to georeferenced Sentinel-style band GeoTIFFs for preprocessing."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import rasterio
from rasterio.transform import from_bounds


def aoi_bounds_wgs84(west: float, south: float, east: float, north: float) -> tuple[float, float, float, float]:
    return west, south, east, north


def jpg_to_sentinel_bands(
    jpg_path: Path,
    bounds: tuple[float, float, float, float],
    raw_dir: Path,
    size: int = 1280,
) -> Path:
    """Write B02/B03/B04 GeoTIFFs covering bounds from an RGB JPG."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(jpg_path))
    if img is None:
        raise FileNotFoundError(jpg_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)

    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, size, size)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "uint16",
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "lzw",
    }

    # Scale 8-bit RGB to uint16-ish range like Sentinel L2A
    for band_name, channel in (("B04", 0), ("B03", 1), ("B02", 2)):
        data = (img[:, :, channel].astype(np.uint16) * 256)
        out = raw_dir / f"{band_name}.tif"
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(data, 1)

    return raw_dir
