from pathlib import Path

from helios_common.config import settings


def scene_root(scene_id: int) -> Path:
    return Path(settings.data_root) / "scenes" / str(scene_id)


def scene_raw_dir(scene_id: int) -> Path:
    return scene_root(scene_id) / "raw"


def scene_processed_path(scene_id: int) -> Path:
    return scene_root(scene_id) / "processed.stack.tif"


def scene_tiles_dir(scene_id: int) -> Path:
    return Path(settings.tiles_dir) / str(scene_id)


def tile_path(scene_id: int, row: int, col: int) -> Path:
    return scene_tiles_dir(scene_id) / f"{row}_{col}.tif"


def ensure_scene_dirs(scene_id: int) -> Path:
    raw = scene_raw_dir(scene_id)
    raw.mkdir(parents=True, exist_ok=True)
    scene_tiles_dir(scene_id).mkdir(parents=True, exist_ok=True)
    return raw
