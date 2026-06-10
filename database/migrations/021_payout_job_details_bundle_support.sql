-- Allow payout_job_details to reference bundles instead of individual jobs
ALTER TABLE payout_job_details MODIFY COLUMN job_id INT NULL;
ALTER TABLE payout_job_details ADD COLUMN bundle_id INT NULL AFTER job_id;
ALTER TABLE payout_job_details ADD CONSTRAINT fk_pjd_bundle FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id);
