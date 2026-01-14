-- Migration: Add financial fields to jobs and time_entries
-- Date: 2026-01-13
-- Description: Add expenses/commissions to jobs, add mileage/personal_expenses/per_diem to time_entries

-- Add new columns to jobs table
ALTER TABLE jobs
ADD COLUMN expenses DECIMAL(10,2) DEFAULT 0 AFTER estimated_hours,
ADD COLUMN commissions DECIMAL(10,2) DEFAULT 0 AFTER expenses;

-- Add new columns to time_entries table
ALTER TABLE time_entries
ADD COLUMN mileage DECIMAL(8,2) DEFAULT 0 AFTER hours_worked,
ADD COLUMN personal_expenses DECIMAL(10,2) DEFAULT 0 AFTER mileage,
ADD COLUMN per_diem DECIMAL(10,2) DEFAULT 0 AFTER personal_expenses;

-- Update existing records to have 0 instead of NULL for new fields
UPDATE jobs SET expenses = 0 WHERE expenses IS NULL;
UPDATE jobs SET commissions = 0 WHERE commissions IS NULL;
UPDATE time_entries SET mileage = 0 WHERE mileage IS NULL;
UPDATE time_entries SET personal_expenses = 0 WHERE personal_expenses IS NULL;
UPDATE time_entries SET per_diem = 0 WHERE per_diem IS NULL;
