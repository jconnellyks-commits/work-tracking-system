-- 015: Add billing_rate to jobs, create job_reimbursables table

ALTER TABLE jobs ADD COLUMN billing_rate DECIMAL(10,2) DEFAULT NULL AFTER billing_type;

CREATE TABLE job_reimbursables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    category ENUM('travel','parts','misc') NOT NULL DEFAULT 'misc',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Set billing_rate for existing hourly job NV-04142601 ($4680 / 72 hrs = $65/hr)
UPDATE jobs SET billing_rate = 65.00 WHERE ticket_number = 'NV-04142601';
