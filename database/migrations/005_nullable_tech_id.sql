-- Migration: Make tech_id nullable on time_entries
-- Date: 2026-01-15
-- Description: Allow time entries to be created without a technician assigned
--              (for scraped/imported data that needs manual assignment)

-- Remove the NOT NULL constraint from tech_id
ALTER TABLE time_entries MODIFY COLUMN tech_id INT NULL;
