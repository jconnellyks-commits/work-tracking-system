-- Migration 011: Add default timezone system setting
INSERT INTO system_settings (setting_key, setting_value, description)
VALUES ('timezone', 'America/Chicago', 'Application timezone for date/time calculations (IANA timezone name, e.g. America/Chicago, America/New_York, America/Los_Angeles)')
ON DUPLICATE KEY UPDATE
    description = VALUES(description);
