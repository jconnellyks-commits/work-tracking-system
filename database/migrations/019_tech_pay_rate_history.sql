-- Migration 019: Tech pay rate history
-- Tracks changes to technician minimum pay rates with effective dates
-- so pay calculations use the rate that was active when the work was done.

CREATE TABLE IF NOT EXISTS tech_pay_rate_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tech_id INT NOT NULL,
    rate DECIMAL(10, 2) NOT NULL,
    effective_date DATE NOT NULL,
    end_date DATE DEFAULT NULL,
    changed_by INT DEFAULT NULL,
    notes VARCHAR(200) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_tech_effective (tech_id, effective_date)
);

-- Seed current rates as initial history records
INSERT INTO tech_pay_rate_history (tech_id, rate, effective_date, notes)
SELECT tech_id, COALESCE(hourly_rate, 0), COALESCE(hire_date, created_at), 'Initial rate (seeded from migration)'
FROM technicians
WHERE hourly_rate IS NOT NULL AND hourly_rate > 0;
