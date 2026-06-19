"""Shared paths for ML scripts."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = REPO_ROOT / "ml"
DATASETS_DIR = ML_ROOT / "datasets"
ARTIFACTS_DIR = ML_ROOT / "artifacts"
CONFIGS_DIR = ML_ROOT / "configs"
MODELS_REPO = REPO_ROOT / "models"

DOTA_CLASSES = ["vehicle", "ship", "aircraft", "helicopter"]

DOTA_CATEGORY_MAP = {
    "small-vehicle": "vehicle",
    "large-vehicle": "vehicle",
    "plane": "aircraft",
    "helicopter": "helicopter",
    "ship": "ship",
    "harbor": None,
    "storage-tank": None,
    "bridge": None,
    "ground-track-field": None,
    "soccer-ball-field": None,
    "tennis-court": None,
    "swimming-pool": None,
    "baseball-diamond": None,
    "roundabout": None,
    "basketball-court": None,
}
