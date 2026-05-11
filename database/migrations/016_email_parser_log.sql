CREATE TABLE IF NOT EXISTS email_parser_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    platform VARCHAR(20) NOT NULL,
    email_type VARCHAR(30) NOT NULL,
    ticket_number VARCHAR(50),
    client_name VARCHAR(200),
    subject VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL,
    job_id INT,
    error_message TEXT,
    gmail_message_id VARCHAR(100),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE SET NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_platform (platform),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
