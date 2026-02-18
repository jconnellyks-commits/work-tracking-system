-- Migration 009: Add scheduled_start_time to jobs
-- Stores the scheduled start time for a job (separate from job_date)
-- Populated from scrapers or manual entry

ALTER TABLE jobs ADD COLUMN scheduled_start_time TIME NULL;
