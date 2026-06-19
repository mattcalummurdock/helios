"""Copernicus Data Space — OAuth, STAC search, S3 download."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import boto3
import httpx
from botocore.config import Config

from helios_common.config import settings

logger = logging.getLogger(__name__)

S2_COLLECTIONS = ["sentinel-2-l2a", "sentinel-2-l1c"]
S1_COLLECTIONS = ["sentinel-1-grd"]
S2_BANDS = {"B02", "B03", "B04", "B08"}
S1_BANDS = {"VV", "VH"}


@dataclass
class StacSceneCandidate:
    external_id: str
    collection: str
    sensor_type: str
    acquisition_timestamp: datetime
    cloud_cover_pct: float | None
    item: dict[str, Any]


class CopernicusClient:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires: datetime | None = None
        self._s3_access_key: str | None = None
        self._s3_secret_key: str | None = None

    def _ensure_credentials(self) -> None:
        if not settings.copernicus_client_id or not settings.copernicus_client_secret:
            raise ValueError("Copernicus credentials not configured (COPERNICUS_CLIENT_ID/SECRET)")

    def get_access_token(self) -> str:
        self._ensure_credentials()
        now = datetime.now(timezone.utc)
        if self._access_token and self._token_expires and now < self._token_expires:
            return self._access_token

        with httpx.Client(timeout=60) as client:
            response = client.post(
                settings.copernicus_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.copernicus_client_id,
                    "client_secret": settings.copernicus_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expires = now.replace(microsecond=0) + __import__("datetime").timedelta(
            seconds=max(expires_in - 60, 60)
        )
        return self._access_token

    def _get_s3_credentials(self) -> tuple[str, str]:
        if self._s3_access_key and self._s3_secret_key:
            return self._s3_access_key, self._s3_secret_key

        token = self.get_access_token()
        with httpx.Client(timeout=60) as client:
            response = client.get(
                settings.copernicus_s3_credentials_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

        self._s3_access_key = data["accessKeyId"]
        self._s3_secret_key = data["secretAccessKey"]
        return self._s3_access_key, self._s3_secret_key

    def search_scenes(
        self,
        aoi_geojson: dict[str, Any],
        last_pass_at: datetime | None,
        known_external_ids: set[str],
    ) -> list[StacSceneCandidate]:
        token = self.get_access_token()
        datetime_filter = "1970-01-01T00:00:00Z/.."
        if last_pass_at:
            if last_pass_at.tzinfo is None:
                last_pass_at = last_pass_at.replace(tzinfo=timezone.utc)
            datetime_filter = f"{last_pass_at.isoformat().replace('+00:00', 'Z')}/.."

        candidates: list[StacSceneCandidate] = []

        for collections, sensor_type in [
            (S2_COLLECTIONS, "sentinel-2"),
            (S1_COLLECTIONS, "sentinel-1"),
        ]:
            body: dict[str, Any] = {
                "collections": collections,
                "datetime": datetime_filter,
                "intersects": aoi_geojson,
                "limit": 10,
            }
            if sensor_type == "sentinel-2":
                body["query"] = {"eo:cloud_cover": {"lt": settings.max_cloud_cover * 100}}

            with httpx.Client(timeout=120) as client:
                response = client.post(
                    settings.copernicus_stac_url,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                features = response.json().get("features", [])

            for item in features:
                external_id = item.get("id", "")
                if not external_id or external_id in known_external_ids:
                    continue

                props = item.get("properties", {})
                dt_str = props.get("datetime") or props.get("start_datetime")
                if not dt_str:
                    continue
                acq = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

                cloud = props.get("eo:cloud_cover")
                cloud_pct = float(cloud) if cloud is not None else None

                candidates.append(
                    StacSceneCandidate(
                        external_id=external_id,
                        collection=item.get("collection", collections[0]),
                        sensor_type=sensor_type,
                        acquisition_timestamp=acq,
                        cloud_cover_pct=cloud_pct,
                        item=item,
                    )
                )

        candidates.sort(key=lambda c: c.acquisition_timestamp, reverse=True)
        return candidates

    def _parse_s3_path(self, href: str) -> tuple[str, str] | None:
        if href.startswith("s3://"):
            parts = href[5:].split("/", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
        if "eodata" in href:
            parsed = urlparse(href)
            path = parsed.path.lstrip("/")
            bucket = path.split("/")[0] if "/" in path else "eodata"
            key = "/".join(path.split("/")[1:]) if "/" in path else path
            return bucket, key
        return None

    def _select_assets(self, item: dict[str, Any], sensor_type: str) -> dict[str, str]:
        assets = item.get("assets", {})
        selected: dict[str, str] = {}
        target_bands = S2_BANDS if sensor_type == "sentinel-2" else S1_BANDS

        for name, asset in assets.items():
            band = asset.get("common_name", name).upper()
            if band in target_bands or name.upper() in target_bands:
                href = asset.get("href", "")
                if href:
                    selected[band if band in target_bands else name.upper()] = href

        if not selected and sensor_type == "sentinel-2":
            for name, asset in assets.items():
                if re.match(r"^B0[2348]$", name.upper()):
                    href = asset.get("href", "")
                    if href:
                        selected[name.upper()] = href

        if not selected and sensor_type == "sentinel-1":
            for name, asset in assets.items():
                if name.upper() in S1_BANDS:
                    selected[name.upper()] = href

        return selected

    def download_scene_bands(
        self,
        candidate: StacSceneCandidate,
        output_dir: str,
    ) -> str:
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        assets = self._select_assets(candidate.item, candidate.sensor_type)
        if not assets:
            raise ValueError(f"No downloadable assets for {candidate.external_id}")

        access_key, secret_key = self._get_s3_credentials()
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.copernicus_s3_endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

        downloaded: list[str] = []
        for band, href in assets.items():
            dest = out / f"{band}.tif"
            s3_path = self._parse_s3_path(href)
            if s3_path:
                bucket, key = s3_path
                logger.info("Downloading S3 %s/%s -> %s", bucket, key, dest)
                s3.download_file(bucket, key, str(dest))
            else:
                token = self.get_access_token()
                with httpx.Client(timeout=300) as client:
                    with client.stream(
                        "GET", href, headers={"Authorization": f"Bearer {token}"}
                    ) as response:
                        response.raise_for_status()
                        with open(dest, "wb") as f:
                            for chunk in response.iter_bytes(8192):
                                f.write(chunk)
            downloaded.append(str(dest))

        manifest = out / "manifest.txt"
        manifest.write_text("\n".join(downloaded))
        return str(out)
