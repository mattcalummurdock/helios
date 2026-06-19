"""Planet Labs Data API — quick-search and Orders."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from helios_common.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PlanetSceneCandidate:
    external_id: str
    acquisition_timestamp: datetime
    cloud_cover_pct: float | None
    item: dict[str, Any]


class PlanetClient:
    def __init__(self) -> None:
        if not settings.planet_api_key:
            raise ValueError("Planet API key not configured (PLANET_API_KEY)")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"api-key {settings.planet_api_key}"}

    def search_scenes(
        self,
        aoi_geojson: dict[str, Any],
        last_pass_at: datetime | None,
        known_external_ids: set[str],
    ) -> list[PlanetSceneCandidate]:
        filters: list[dict[str, Any]] = [
            {"type": "GeometryFilter", "field_name": "geometry", "config": aoi_geojson},
            {"type": "StringInFilter", "field_name": "item_type", "config": ["PSScene"]},
        ]
        if last_pass_at:
            if last_pass_at.tzinfo is None:
                last_pass_at = last_pass_at.replace(tzinfo=timezone.utc)
            filters.append(
                {
                    "type": "DateRangeFilter",
                    "field_name": "acquired",
                    "config": {"gte": last_pass_at.isoformat().replace("+00:00", "Z")},
                }
            )

        body = {
            "item_types": ["PSScene"],
            "filter": {"type": "AndFilter", "config": filters},
        }

        url = f"{settings.planet_api_base}/data/v1/quick-search"
        with httpx.Client(timeout=120) as client:
            response = client.post(url, json=body, headers=self._headers)
            response.raise_for_status()
            features = response.json().get("features", [])

        candidates: list[PlanetSceneCandidate] = []
        for item in features:
            external_id = item.get("id", "")
            if not external_id or external_id in known_external_ids:
                continue
            props = item.get("properties", {})
            acq_str = props.get("acquired")
            if not acq_str:
                continue
            acq = datetime.fromisoformat(acq_str.replace("Z", "+00:00"))
            cloud = props.get("cloud_percent")
            candidates.append(
                PlanetSceneCandidate(
                    external_id=external_id,
                    acquisition_timestamp=acq,
                    cloud_cover_pct=float(cloud) if cloud is not None else None,
                    item=item,
                )
            )

        candidates.sort(key=lambda c: c.acquisition_timestamp, reverse=True)
        return candidates

    def download_scene(self, item_id: str, output_dir: str) -> str:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        order_url = f"{settings.planet_api_base}/compute/ops/orders/v2"
        order_body = {
            "name": f"helios-{item_id}",
            "products": [
                {
                    "item_ids": [item_id],
                    "item_type": "PSScene",
                    "product_bundle": "analytic_sr",
                }
            ],
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(order_url, json=order_body, headers=self._headers)
            response.raise_for_status()
            order_id = response.json()["id"]

            status_url = f"{order_url}/{order_id}"
            for _ in range(60):
                status_resp = client.get(status_url, headers=self._headers)
                status_resp.raise_for_status()
                state = status_resp.json().get("state")
                if state == "success":
                    break
                if state in ("failed", "cancelled"):
                    raise RuntimeError(f"Planet order {order_id} failed: {state}")
                time.sleep(10)
            else:
                raise TimeoutError(f"Planet order {order_id} timed out")

            results_resp = client.get(f"{status_url}/results", headers=self._headers)
            results_resp.raise_for_status()
            results = results_resp.json().get("results", [])

            for i, result in enumerate(results):
                download_url = result.get("location") or result.get("delivery", {}).get("url")
                if not download_url:
                    continue
                dest = out / f"planet_{i}.tif"
                with client.stream("GET", download_url) as dl:
                    dl.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in dl.iter_bytes(8192):
                            f.write(chunk)

        manifest = out / "manifest.txt"
        files = [str(p) for p in out.glob("*.tif")]
        manifest.write_text("\n".join(files))
        return str(out)
