#!/usr/bin/env python3
"""Seed multiple change vectors (moved / appeared / disappeared) across demo AOIs.

Usage:
  DATABASE_URL_SYNC=postgresql://helios:changeme@localhost:5433/helios
  PYTHONPATH=shared
  python ml/scripts/seed_demo_change_vector.py
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from geoalchemy2.elements import WKTElement
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from helios_common.db import SyncSessionLocal  # noqa: E402
from helios_common.models import ChangeEvent, ChangeEventType, Detection  # noqa: E402


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _bbox_wkt(lon: float, lat: float, delta: float = 0.002) -> str:
    return (
        f"POLYGON(({lon - delta} {lat + delta}, {lon + delta} {lat + delta}, "
        f"{lon + delta} {lat - delta}, {lon - delta} {lat - delta}, "
        f"{lon - delta} {lat + delta}))"
    )


def _add_detection(
    session,
    *,
    scene_id: int,
    aoi_id: int,
    cls: str,
    subclass: str | None,
    lat: float,
    lon: float,
    confidence: float = 0.85,
    heading: float = 0.0,
    ts: datetime,
) -> Detection:
    row = Detection(
        scene_id=scene_id,
        aoi_id=aoi_id,
        class_=cls,
        subclass=subclass,
        confidence=confidence,
        lat=lat,
        lon=lon,
        heading_degrees=heading,
        bbox_polygon=WKTElement(_bbox_wkt(lon, lat), srid=4326),
        timestamp=ts,
    )
    session.add(row)
    session.flush()
    return row


def _scene_id(session, external_id: str) -> int:
    sid = session.execute(
        text("SELECT id FROM scenes WHERE external_scene_id = :ext"),
        {"ext": external_id},
    ).scalar()
    if not sid:
        raise SystemExit(f"Scene missing: {external_id}. Run seed_demo.py first.")
    return int(sid)


def main() -> int:
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        session.execute(text("DELETE FROM change_events"))
        session.commit()

        created: list[str] = []

        # --- Kyiv: T62 moved (~8 km) ---
        kyiv_t1_scene = _scene_id(session, "demo-kyiv-vehicles-t1")
        kyiv_t2_scene = _scene_id(session, "demo-kyiv-vehicles-t2")
        t1 = session.execute(
            text(
                "SELECT id, lat, lon, class, subclass FROM detections "
                "WHERE id = 35"
            )
        ).first()
        if t1:
            t1_id, t1_lat, t1_lon, cls, subclass = t1
            t2 = _add_detection(
                session,
                scene_id=kyiv_t2_scene,
                aoi_id=1,
                cls=cls,
                subclass=subclass,
                lat=float(t1_lat) + 0.055,
                lon=float(t1_lon) + 0.085,
                heading=45.0,
                ts=now,
            )
            dist = _haversine_m(float(t1_lat), float(t1_lon), t2.lat, t2.lon)
            session.add(
                ChangeEvent(
                    aoi_id=1,
                    event_type=ChangeEventType.MOVED,
                    detection_id_t1=int(t1_id),
                    detection_id_t2=t2.id,
                    distance_moved_m=dist,
                    bearing_degrees=_bearing_degrees(float(t1_lat), float(t1_lon), t2.lat, t2.lon),
                    speed_kmh=(dist / 1000.0) / 2.0,
                    timestamp=now,
                )
            )
            created.append(f"Kyiv MOVED {subclass or cls} ({dist:.0f} m)")

        # --- Kyiv: vehicle disappeared (T1 only) ---
        ghost = _add_detection(
            session,
            scene_id=kyiv_t1_scene,
            aoi_id=1,
            cls="vehicle",
            subclass="BTR_60",
            lat=50.42,
            lon=30.52,
            confidence=0.79,
            ts=now,
        )
        session.add(
            ChangeEvent(
                aoi_id=1,
                event_type=ChangeEventType.DISAPPEARED,
                detection_id_t1=ghost.id,
                timestamp=now,
            )
        )
        created.append("Kyiv DISAPPEARED BTR-60")

        # --- Black Sea: ship moved (~6 km along coast) ---
        ship = session.execute(
            text("SELECT id, lat, lon, class, subclass FROM detections WHERE id = 36")
        ).first()
        if ship:
            s1_id, s_lat, s_lon, s_cls, s_sub = ship
            s2 = _add_detection(
                session,
                scene_id=_scene_id(session, "demo-black-sea-ships-t1"),
                aoi_id=2,
                cls=s_cls,
                subclass=s_sub,
                lat=float(s_lat) + 0.035,
                lon=float(s_lon) + 0.055,
                heading=120.0,
                ts=now,
            )
            dist = _haversine_m(float(s_lat), float(s_lon), s2.lat, s2.lon)
            session.add(
                ChangeEvent(
                    aoi_id=2,
                    event_type=ChangeEventType.MOVED,
                    detection_id_t1=int(s1_id),
                    detection_id_t2=s2.id,
                    distance_moved_m=dist,
                    bearing_degrees=_bearing_degrees(float(s_lat), float(s_lon), s2.lat, s2.lon),
                    speed_kmh=(dist / 1000.0) / 1.5,
                    timestamp=now,
                )
            )
            created.append(f"Black Sea MOVED {s_sub or s_cls} ({dist:.0f} m)")

        # --- Black Sea: new ship appeared ---
        appeared = _add_detection(
            session,
            scene_id=_scene_id(session, "demo-black-sea-ships-t1"),
            aoi_id=2,
            cls="ship",
            subclass="Patrol craft",
            lat=46.415,
            lon=30.695,
            confidence=0.81,
            ts=now,
        )
        session.add(
            ChangeEvent(
                aoi_id=2,
                event_type=ChangeEventType.APPEARED,
                detection_id_t2=appeared.id,
                timestamp=now,
            )
        )
        created.append("Black Sea APPEARED Patrol craft")

        # --- Lviv airfield: An-26 moved ---
        ac = session.execute(
            text("SELECT id, lat, lon, class, subclass FROM detections WHERE id = 37")
        ).first()
        if ac:
            a1_id, a_lat, a_lon, a_cls, a_sub = ac
            a2 = _add_detection(
                session,
                scene_id=_scene_id(session, "demo-airfield-aircraft-t1"),
                aoi_id=3,
                cls=a_cls,
                subclass=a_sub,
                lat=float(a_lat) + 0.012,
                lon=float(a_lon) + 0.018,
                heading=30.0,
                ts=now,
            )
            dist = _haversine_m(float(a_lat), float(a_lon), a2.lat, a2.lon)
            session.add(
                ChangeEvent(
                    aoi_id=3,
                    event_type=ChangeEventType.MOVED,
                    detection_id_t1=int(a1_id),
                    detection_id_t2=a2.id,
                    distance_moved_m=dist,
                    bearing_degrees=_bearing_degrees(float(a_lat), float(a_lon), a2.lat, a2.lon),
                    speed_kmh=(dist / 1000.0) / 1.0,
                    timestamp=now,
                )
            )
            created.append(f"Lviv MOVED {a_sub or a_cls} ({dist:.0f} m)")

        # --- Lviv: helicopter appeared on pad ---
        heli = _add_detection(
            session,
            scene_id=_scene_id(session, "demo-airfield-aircraft-t1"),
            aoi_id=3,
            cls="helicopter",
            subclass="Mi-8MT",
            lat=49.885,
            lon=24.775,
            confidence=0.77,
            ts=now,
        )
        session.add(
            ChangeEvent(
                aoi_id=3,
                event_type=ChangeEventType.APPEARED,
                detection_id_t2=heli.id,
                timestamp=now,
            )
        )
        created.append("Lviv APPEARED Mi-8MT")

        session.commit()
        print(f"Seeded {len(created)} change events:")
        for line in created:
            print(f"  - {line}")
        print("\nRefresh globe, click Vectors (N) to fly to them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
