-- Helios MVP Phase 1: PostGIS schema initialization
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TYPE aoi_priority AS ENUM ('high', 'medium', 'low');
CREATE TYPE change_event_type AS ENUM ('appeared', 'disappeared', 'moved');
CREATE TYPE alert_severity AS ENUM ('critical', 'high', 'medium');

CREATE TABLE aois (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    priority aoi_priority NOT NULL DEFAULT 'medium',
    polygon GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_pass_at TIMESTAMPTZ,
    monitoring_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE scenes (
    id SERIAL PRIMARY KEY,
    aoi_id INTEGER NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    satellite_source VARCHAR(64) NOT NULL,
    acquisition_timestamp TIMESTAMPTZ NOT NULL,
    cloud_cover_pct REAL,
    scene_path TEXT,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE detections (
    id SERIAL PRIMARY KEY,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    aoi_id INTEGER NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    class VARCHAR(64) NOT NULL,
    subclass VARCHAR(64),
    confidence REAL NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    heading_degrees REAL,
    bbox_polygon GEOMETRY(POLYGON, 4326),
    detection_image_path TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE change_events (
    id SERIAL PRIMARY KEY,
    aoi_id INTEGER NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    event_type change_event_type NOT NULL,
    detection_id_t1 INTEGER REFERENCES detections(id) ON DELETE SET NULL,
    detection_id_t2 INTEGER REFERENCES detections(id) ON DELETE SET NULL,
    distance_moved_m REAL,
    speed_kmh REAL,
    bearing_degrees REAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_fired BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    aoi_id INTEGER NOT NULL REFERENCES aois(id) ON DELETE CASCADE,
    change_event_id INTEGER REFERENCES change_events(id) ON DELETE SET NULL,
    alert_type VARCHAR(64) NOT NULL,
    severity alert_severity NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    description TEXT,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_aois_polygon ON aois USING GIST (polygon);
CREATE INDEX idx_detections_bbox_polygon ON detections USING GIST (bbox_polygon);
CREATE INDEX idx_detections_aoi_timestamp ON detections (aoi_id, timestamp);
CREATE INDEX idx_change_events_aoi_timestamp ON change_events (aoi_id, timestamp);
CREATE INDEX idx_alerts_aoi_timestamp ON alerts (aoi_id, timestamp);
CREATE INDEX idx_scenes_aoi_id ON scenes (aoi_id);

-- Seed test AOIs for pipeline development
INSERT INTO aois (name, priority, polygon, monitoring_active) VALUES
(
    'Test AOI - Kyiv Region',
    'high',
    ST_GeomFromText(
        'POLYGON((30.40 50.35, 30.60 50.35, 30.60 50.50, 30.40 50.50, 30.40 50.35))',
        4326
    ),
    TRUE
),
(
    'Test AOI - Black Sea Port',
    'medium',
    ST_GeomFromText(
        'POLYGON((30.60 46.40, 30.80 46.40, 30.80 46.55, 30.60 46.55, 30.60 46.40))',
        4326
    ),
    TRUE
);
