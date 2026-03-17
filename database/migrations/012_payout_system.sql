-- Migration 012: Payout System
-- Adds payout infrastructure tables and modifies existing tables

-- 1. Add worker_type to technicians
ALTER TABLE technicians ADD COLUMN worker_type VARCHAR(20) NOT NULL DEFAULT 'contractor';

-- 2. Add 'locked' to pay_periods status enum
ALTER TABLE pay_periods MODIFY COLUMN status ENUM('open', 'locked', 'closed', 'archived') DEFAULT 'open';

-- 3. Payout table (one per tech per pay period, created at lock time)
CREATE TABLE payouts (
    payout_id INT AUTO_INCREMENT PRIMARY KEY,
    period_id INT NOT NULL,
    tech_id INT NOT NULL,
    status ENUM('locked', 'paid') NOT NULL DEFAULT 'locked',
    total_hours DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_base_pay DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_mileage_pay DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_per_diem DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_personal_expenses DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_bonuses DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_deductions DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_advance_repayment DECIMAL(10,2) NOT NULL DEFAULT 0,
    net_payout DECIMAL(10,2) NOT NULL DEFAULT 0,
    locked_at DATETIME NOT NULL,
    paid_at DATETIME NULL,
    paid_by INT NULL,
    notes TEXT NULL,
    FOREIGN KEY (period_id) REFERENCES pay_periods(period_id),
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id),
    FOREIGN KEY (paid_by) REFERENCES users(user_id),
    UNIQUE KEY uq_payout_period_tech (period_id, tech_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Payout job detail (snapshot per job per tech per payout)
CREATE TABLE payout_job_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payout_id INT NOT NULL,
    job_id INT NOT NULL,
    hours DECIMAL(10,2) NOT NULL DEFAULT 0,
    base_pay DECIMAL(10,2) NOT NULL DEFAULT 0,
    mileage_pay DECIMAL(10,2) NOT NULL DEFAULT 0,
    per_diem DECIMAL(10,2) NOT NULL DEFAULT 0,
    personal_expenses DECIMAL(10,2) NOT NULL DEFAULT 0,
    effective_rate DECIMAL(10,2) NOT NULL DEFAULT 0,
    profit_share DECIMAL(10,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (payout_id) REFERENCES payouts(payout_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Payout line items (bonuses and deductions)
CREATE TABLE payout_line_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payout_id INT NOT NULL,
    type ENUM('bonus', 'deduction') NOT NULL,
    description TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payout_id) REFERENCES payouts(payout_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Advances (carries balance across periods)
CREATE TABLE advances (
    advance_id INT AUTO_INCREMENT PRIMARY KEY,
    tech_id INT NOT NULL,
    description TEXT NOT NULL,
    original_amount DECIMAL(10,2) NOT NULL,
    remaining_balance DECIMAL(10,2) NOT NULL,
    max_per_period DECIMAL(10,2) NULL,
    status ENUM('active', 'repaid', 'cancelled') NOT NULL DEFAULT 'active',
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    repaid_at DATETIME NULL,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Advance repayments (tracks each deduction against an advance)
CREATE TABLE advance_repayments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    advance_id INT NOT NULL,
    payout_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (advance_id) REFERENCES advances(advance_id),
    FOREIGN KEY (payout_id) REFERENCES payouts(payout_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. Payout adjustments (post-lock change detection)
CREATE TABLE payout_adjustments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payout_id INT NOT NULL,
    type VARCHAR(50) NOT NULL,
    job_id INT NULL,
    entry_id INT NULL,
    description TEXT NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    amount_diff DECIMAL(10,2) NOT NULL DEFAULT 0,
    resolution ENUM('pending', 'carried_forward', 'dismissed') NOT NULL DEFAULT 'pending',
    resolved_to_period_id INT NULL,
    resolved_by INT NULL,
    resolved_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payout_id) REFERENCES payouts(payout_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (entry_id) REFERENCES time_entries(entry_id),
    FOREIGN KEY (resolved_to_period_id) REFERENCES pay_periods(period_id),
    FOREIGN KEY (resolved_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
