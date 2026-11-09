-- Dated expense line items on a job bundle (materials, lodging, etc. spread
-- over several days of bundled work). Their total pools into the bundle's
-- expenses, deducted from billing before the tech pool split.
CREATE TABLE IF NOT EXISTS bundle_expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bundle_id INT NOT NULL,
    expense_date DATE NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    category ENUM('materials', 'equipment', 'lodging', 'meals', 'travel', 'other') NOT NULL DEFAULT 'other',
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_bundle_expenses_bundle (bundle_id),
    INDEX idx_bundle_expenses_date (expense_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
