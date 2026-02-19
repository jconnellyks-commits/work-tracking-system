-- Migration 010: Add SMS opt-in tracking and availability response fields
-- Adds opt-in/out tracking to technicians and availability response to job_assignments

ALTER TABLE technicians
  ADD COLUMN sms_opted_in BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN sms_opted_in_at TIMESTAMP NULL,
  ADD COLUMN sms_opted_out_at TIMESTAMP NULL;

ALTER TABLE job_assignments
  ADD COLUMN availability_response ENUM('pending','yes','no') NULL,
  ADD COLUMN availability_responded_at TIMESTAMP NULL;
