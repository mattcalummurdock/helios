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


def detection_dir(detection_id: int) -> Path:
    return Path(settings.detections_dir) / str(detection_id)


def resolve_detection_asset(
    stored_path: str | None,
    detection_id: int,
    filename: str,
) -> Path | None:
    """Resolve a detection crop/gradcam file across host paths and Docker /data mounts."""
    candidates: list[Path] = []
    if stored_path:
        candidates.append(Path(stored_path))
        normalized = stored_path.replace("\\", "/")
        lower = normalized.lower()
        for marker in ("/data/", "data/detections/"):
            idx = lower.find(marker)
            if idx >= 0:
                rel = normalized[idx:].lstrip("/")
                candidates.append(Path("/") / rel)
    candidates.append(detection_dir(detection_id) / filename)
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return path
    return None
