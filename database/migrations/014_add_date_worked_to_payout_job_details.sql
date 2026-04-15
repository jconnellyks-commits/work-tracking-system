-- Add date_worked column to payout_job_details for per-entry granularity
ALTER TABLE payout_job_details ADD COLUMN date_worked DATE NULL AFTER job_id;
