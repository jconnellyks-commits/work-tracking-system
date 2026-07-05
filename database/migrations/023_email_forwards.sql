CREATE TABLE IF NOT EXISTS email_forwards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    tech_id INT NOT NULL,
    assignment_id INT,
    gmail_message_id VARCHAR(100) NOT NULL,
    forwarded_to VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    error_message TEXT,
    forwarded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES job_assignments(assignment_id) ON DELETE SET NULL,
    INDEX idx_job_id (job_id),
    INDEX idx_assignment_id (assignment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
