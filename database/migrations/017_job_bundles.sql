-- Job bundles table
CREATE TABLE IF NOT EXISTS job_bundles (
    bundle_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NULL,
    status ENUM('active', 'closed') NOT NULL DEFAULT 'active',
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Add bundle_id to jobs
ALTER TABLE jobs ADD COLUMN bundle_id INT NULL,
    ADD CONSTRAINT fk_jobs_bundle FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id) ON DELETE SET NULL,
    ADD INDEX idx_jobs_bundle (bundle_id);

-- Add bundle_id to time_entries, make job_id nullable
ALTER TABLE time_entries ADD COLUMN bundle_id INT NULL,
    ADD CONSTRAINT fk_time_entries_bundle FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id) ON DELETE SET NULL,
    ADD INDEX idx_time_entries_bundle (bundle_id);

ALTER TABLE time_entries MODIFY COLUMN job_id INT NULL;
