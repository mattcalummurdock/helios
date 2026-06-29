"""Step 2: orthorectification to EPSG:4326."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from helios_common.config import settings

logger = logging.getLogger(__name__)


def orthorectify(input_dir: Path, work_dir: Path, aoi_bounds: tuple[float, float, float, float]) -> Path:
    """Reproject rasters to WGS84, clipped to AOI bounds (minx, miny, maxx, maxy)."""
    out_dir = work_dir / "ortho"
    out_dir.mkdir(parents=True, exist_ok=True)
    minx, miny, maxx, maxy = aoi_bounds

    if _gdalwarp_available():
        return _orthorectify_gdalwarp(input_dir, out_dir, aoi_bounds)
    logger.warning("gdalwarp not found — using rasterio warp (local dev fallback)")
    return _orthorectify_rasterio(input_dir, out_dir, aoi_bounds)


def _gdalwarp_available() -> bool:
    import shutil

    return shutil.which("gdalwarp") is not None


def _orthorectify_gdalwarp(
    input_dir: Path, out_dir: Path, aoi_bounds: tuple[float, float, float, float]
) -> Path:
    minx, miny, maxx, maxy = aoi_bounds
    dem_args: list[str] = []
    dem_path = Path(settings.dem_path)
    if dem_path.exists():
        dem_args = ["-rpc", "-to", f"RPC_DEM={dem_path}"]

    for src in sorted(input_dir.glob("*.tif")):
        dest = out_dir / src.name
        cmd = [
            "gdalwarp",
            "-t_srs",
            "EPSG:4326",
            "-te",
            str(minx),
            str(miny),
            str(maxx),
            str(maxy),
            "-r",
            "bilinear",
            "-co",
            "COMPRESS=LZW",
            *dem_args,
            str(src),
            str(dest),
        ]
        logger.info("Running: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_dir


def _orthorectify_rasterio(
    input_dir: Path, out_dir: Path, aoi_bounds: tuple[float, float, float, float]
) -> Path:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    minx, miny, maxx, maxy = aoi_bounds
    dst_crs = CRS.from_epsg(4326)

    for src_path in sorted(input_dir.glob("*.tif")):
        dest = out_dir / src_path.name
        with rasterio.open(src_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs or dst_crs,
                dst_crs,
                src.width,
                src.height,
                *rasterio.transform.array_bounds(src.height, src.width, src.transform),
                dst_bounds=(minx, miny, maxx, maxy),
            )
            profile = src.profile.copy()
            profile.update(crs=dst_crs, transform=transform, width=width, height=height)
            with rasterio.open(dest, "w", **profile) as dst:
                for band in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band),
                        destination=rasterio.band(dst, band),
                        src_transform=src.transform,
                        src_crs=src.crs or dst_crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear,
                    )
        logger.info("Rasterio ortho: %s -> %s", src_path.name, dest)
    return out_dir
