-- Migration: Add external_url field to jobs table
-- Date: 2026-01-14
-- Description: Add URL field to link jobs to external platform pages

ALTER TABLE jobs ADD COLUMN external_url VARCHAR(500) AFTER commissions;
