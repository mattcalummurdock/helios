"""Step 5: tile into 640x640 chips with overlap."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

from helios_common.config import settings
from helios_common.paths import tile_path

logger = logging.getLogger(__name__)


def tile_image(stack_path: Path, scene_id: int) -> list[str]:
    tile_size = settings.tile_size
    stride = int(tile_size * (1 - settings.tile_overlap))
    tile_paths: list[str] = []

    with rasterio.open(stack_path) as src:
        height, width = src.height, src.width
        row_idx = 0
        for row_off in range(0, max(height - tile_size + 1, 1), max(stride, 1)):
            col_idx = 0
            for col_off in range(0, max(width - tile_size + 1, 1), max(stride, 1)):
                window = Window(col_off, row_off, tile_size, tile_size)
                if window.width < tile_size or window.height < tile_size:
                    continue
                data = src.read(window=window)
                if np.nanmax(data) <= 0:
                    col_idx += 1
                    continue

                # uint8 RGB tiles — OpenCV inference cannot read float32 GeoTIFF
                if data.dtype != np.uint8:
                    data = data.astype(np.float32)
                    if np.nanmax(data) <= 1.0:
                        data = np.clip(data * 255.0, 0, 255)
                    else:
                        data = np.clip(data, 0, 255)
                    data = data.astype(np.uint8)

                transform = src.window_transform(window)
                profile = src.profile.copy()
                profile.update(
                    height=tile_size,
                    width=tile_size,
                    transform=transform,
                    dtype="uint8",
                    count=data.shape[0],
                )
                out = tile_path(scene_id, row_idx, col_idx)
                out.parent.mkdir(parents=True, exist_ok=True)
                with rasterio.open(out, "w", **profile) as dst:
                    dst.write(data)
                tile_paths.append(str(out))
                col_idx += 1
            row_idx += 1

    logger.info("Created %d tiles for scene %s", len(tile_paths), scene_id)
    return tile_paths
