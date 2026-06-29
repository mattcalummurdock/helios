import enum
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helios_common.db import Base


def _pg_enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Map Postgres lowercase enum labels to Python str enums."""
    return [member.value for member in enum_cls]


class AoiPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChangeEventType(str, enum.Enum):
    APPEARED = "appeared"
    DISAPPEARED = "disappeared"
    MOVED = "moved"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class SensorType(str, enum.Enum):
    SENTINEL_2 = "sentinel-2"
    SENTINEL_1 = "sentinel-1"
    PLANET = "planet"


class Aoi(Base):
    __tablename__ = "aois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[AoiPriority] = mapped_column(
        Enum(
            AoiPriority,
            name="aoi_priority",
            create_type=False,
            values_callable=_pg_enum_values,
        ),
        nullable=False,
    )
    polygon = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_pass_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monitoring_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scenes: Mapped[list["Scene"]] = relationship(back_populates="aoi")
    detections: Mapped[list["Detection"]] = relationship(back_populates="aoi")
    change_events: Mapped[list["ChangeEvent"]] = relationship(back_populates="aoi")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="aoi")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aoi_id: Mapped[int] = mapped_column(ForeignKey("aois.id", ondelete="CASCADE"), nullable=False)
    satellite_source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_scene_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    sensor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    acquisition_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float)
    scene_path: Mapped[str | None] = mapped_column(Text)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    aoi: Mapped["Aoi"] = relationship(back_populates="scenes")
    detections: Mapped[list["Detection"]] = relationship(back_populates="scene")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    aoi_id: Mapped[int] = mapped_column(ForeignKey("aois.id", ondelete="CASCADE"), nullable=False)
    class_: Mapped[str] = mapped_column("class", String(64), nullable=False)
    subclass: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    heading_degrees: Mapped[float | None] = mapped_column(Float)
    bbox_polygon = mapped_column(Geometry("POLYGON", srid=4326))
    detection_image_path: Mapped[str | None] = mapped_column(Text)
    gradcam_path: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scene: Mapped["Scene"] = relationship(back_populates="detections")
    aoi: Mapped["Aoi"] = relationship(back_populates="detections")


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aoi_id: Mapped[int] = mapped_column(ForeignKey("aois.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[ChangeEventType] = mapped_column(
        Enum(
            ChangeEventType,
            name="change_event_type",
            create_type=False,
            values_callable=_pg_enum_values,
        ),
        nullable=False,
    )
    detection_id_t1: Mapped[int | None] = mapped_column(
        ForeignKey("detections.id", ondelete="SET NULL")
    )
    detection_id_t2: Mapped[int | None] = mapped_column(
        ForeignKey("detections.id", ondelete="SET NULL")
    )
    distance_moved_m: Mapped[float | None] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    bearing_degrees: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alert_fired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    aoi: Mapped["Aoi"] = relationship(back_populates="change_events")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="change_event")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aoi_id: Mapped[int] = mapped_column(ForeignKey("aois.id", ondelete="CASCADE"), nullable=False)
    change_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("change_events.id", ondelete="SET NULL")
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            create_type=False,
            values_callable=_pg_enum_values,
        ),
        nullable=False,
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    aoi: Mapped["Aoi"] = relationship(back_populates="alerts")
    change_event: Mapped["ChangeEvent | None"] = relationship(back_populates="alerts")
