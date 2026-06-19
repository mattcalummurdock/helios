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
