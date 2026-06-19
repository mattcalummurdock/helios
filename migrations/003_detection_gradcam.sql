-- Phase 3: Grad-CAM path on detections
ALTER TABLE detections ADD COLUMN IF NOT EXISTS gradcam_path TEXT;
