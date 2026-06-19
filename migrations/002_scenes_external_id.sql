-- Phase 2: scene deduplication and sensor routing
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS external_scene_id VARCHAR(255);
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS sensor_type VARCHAR(32);

UPDATE scenes SET external_scene_id = 'legacy-' || id::text WHERE external_scene_id IS NULL;
UPDATE scenes SET sensor_type = 'sentinel-2' WHERE sensor_type IS NULL;

ALTER TABLE scenes ALTER COLUMN external_scene_id SET NOT NULL;
ALTER TABLE scenes ALTER COLUMN sensor_type SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_scenes_external_scene_id ON scenes (external_scene_id);
