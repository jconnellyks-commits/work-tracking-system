-- Migration 013: Add is_spam column to sms_notifications
-- Also cleans up old test messages

ALTER TABLE sms_notifications ADD COLUMN is_spam BOOLEAN NOT NULL DEFAULT FALSE AFTER delivered_at;

-- Delete test messages (ids 1-33, pre-production testing period)
DELETE FROM sms_notifications WHERE notification_id <= 33;
