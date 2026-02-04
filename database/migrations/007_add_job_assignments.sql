-- Migration 007: Add job assignments and SMS notifications
-- Adds tables for tracking technician assignments to jobs with SMS notification support

-- Job Assignments table
CREATE TABLE IF NOT EXISTS job_assignments (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    tech_id INT NOT NULL,
    status ENUM('invited', 'accepted', 'declined', 'expired', 'cancelled') DEFAULT 'accepted',
    is_primary BOOLEAN DEFAULT FALSE,
    assigned_by INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP NULL,
    sms_sent BOOLEAN DEFAULT FALSE,
    sms_sent_at TIMESTAMP NULL,
    sms_delivery_status VARCHAR(50) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(user_id),

    -- Prevent duplicate assignments
    UNIQUE KEY unique_job_tech (job_id, tech_id),

    -- Indexes for common queries
    INDEX idx_job_assignments_job (job_id),
    INDEX idx_job_assignments_tech (tech_id),
    INDEX idx_job_assignments_status (status),
    INDEX idx_job_assignments_assigned_at (assigned_at)
);

-- SMS Notifications audit log
CREATE TABLE IF NOT EXISTS sms_notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    notification_type ENUM('job_assignment', 'invitation', 'reminder', 'cancellation', 'update', 'other') NOT NULL,
    assignment_id INT NULL,
    tech_id INT NULL,
    phone_number VARCHAR(20) NOT NULL,
    message_body TEXT NOT NULL,
    status ENUM('pending', 'sent', 'delivered', 'failed') DEFAULT 'pending',
    provider_message_id VARCHAR(100),
    provider_response TEXT,
    error_message TEXT,
    sent_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assignment_id) REFERENCES job_assignments(assignment_id) ON DELETE SET NULL,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id) ON DELETE SET NULL,

    -- Indexes
    INDEX idx_sms_notifications_assignment (assignment_id),
    INDEX idx_sms_notifications_tech (tech_id),
    INDEX idx_sms_notifications_status (status),
    INDEX idx_sms_notifications_created (created_at)
);

-- Add relationship from Job to assignments
-- (handled by SQLAlchemy relationship, no schema change needed)

-- Add relationship from Technician to assignments
-- (handled by SQLAlchemy relationship, no schema change needed)
