-- Migration 006: Add source_hash for duplicate detection on imports
-- This hash uniquely identifies scraped entries regardless of how they're split between technicians

ALTER TABLE time_entries
ADD COLUMN source_hash VARCHAR(64) NULL AFTER notes;

-- Index for fast lookup during imports
CREATE INDEX idx_time_entries_source_hash ON time_entries(source_hash);
