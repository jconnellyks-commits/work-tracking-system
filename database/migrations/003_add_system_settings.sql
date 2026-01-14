-- Migration: Add system settings and mileage rate history tables
-- Date: 2026-01-13
-- Description: Add tables for global settings and mileage rate tracking

-- System settings table
CREATE TABLE IF NOT EXISTS system_settings (
    setting_id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(50) NOT NULL UNIQUE,
    setting_value VARCHAR(255) NOT NULL,
    description TEXT,
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Mileage rate history table
CREATE TABLE IF NOT EXISTS mileage_rate_history (
    rate_id INT AUTO_INCREMENT PRIMARY KEY,
    rate_per_mile DECIMAL(6,4) NOT NULL,
    effective_date DATE NOT NULL,
    end_date DATE,
    description VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_effective_date (effective_date),
    INDEX idx_date_range (effective_date, end_date)
);

-- Insert default mileage rate (2026 IRS standard mileage rate)
INSERT INTO mileage_rate_history (rate_per_mile, effective_date, description)
VALUES (0.67, '2026-01-01', '2026 IRS standard mileage rate');

-- Insert default settings
INSERT INTO system_settings (setting_key, setting_value, description, effective_date)
VALUES ('current_mileage_rate', '0.67', 'Current IRS mileage rate per mile', '2026-01-01');
