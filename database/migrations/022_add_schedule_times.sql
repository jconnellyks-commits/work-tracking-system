-- Add arrival window time fields to job_schedule
ALTER TABLE job_schedule ADD COLUMN start_time TIME NULL;
ALTER TABLE job_schedule ADD COLUMN latest_start_time TIME NULL;
