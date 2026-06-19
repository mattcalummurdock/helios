from helios_common.clients.copernicus import CopernicusClient, StacSceneCandidate
from helios_common.clients.planet import PlanetClient
from helios_common.paths import ensure_scene_dirs


def download_copernicus_scene(scene_id: int, candidate: StacSceneCandidate) -> str:
    raw_dir = ensure_scene_dirs(scene_id)
    client = CopernicusClient()
    return client.download_scene_bands(candidate, str(raw_dir))


def download_planet_scene(scene_id: int, item_id: str) -> str:
    raw_dir = ensure_scene_dirs(scene_id)
    client = PlanetClient()
    return client.download_scene(item_id, str(raw_dir))
