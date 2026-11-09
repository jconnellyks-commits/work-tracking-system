-- Post-lock adjustments for bundled pay. A bundle's locked payout rows carry
-- bundle_id with no job_id, so adjustments for them need the same key.
ALTER TABLE payout_adjustments ADD COLUMN bundle_id INT NULL AFTER job_id,
    ADD CONSTRAINT fk_payout_adjustments_bundle FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id) ON DELETE SET NULL,
    ADD INDEX idx_payout_adjustments_bundle (bundle_id);
