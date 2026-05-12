-- Migration 018: Job schedule table for multi-day job scheduling
CREATE TABLE IF NOT EXISTS job_schedule (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    scheduled_date DATE NOT NULL,
    tech_id INT NULL,
    notes VARCHAR(255) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id) ON DELETE SET NULL,
    INDEX idx_job_schedule_job (job_id),
    INDEX idx_job_schedule_date (scheduled_date),
    INDEX idx_job_schedule_tech_date (tech_id, scheduled_date),
    UNIQUE KEY uq_job_schedule_entry (job_id, scheduled_date, tech_id)
);
