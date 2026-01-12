-- ============================================================================
-- Work Tracking System - MySQL Database Schema
-- Version: 1.0
-- Created: 2026-01-12
-- Database: work_tracking_db
-- ============================================================================
-- This schema creates all tables needed for the work tracking system.
-- Includes technicians, jobs from multiple platforms, time entries with
-- audit trails, user management, and comprehensive logging.
-- ============================================================================

-- Drop existing tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS time_entries;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS platforms;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS pay_periods;
DROP TABLE IF EXISTS technicians;

-- ============================================================================
-- TABLE: technicians
-- Description: Stores information about technicians (team members)
-- ============================================================================
CREATE TABLE technicians (
      tech_id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      email VARCHAR(100) UNIQUE,
      phone VARCHAR(20),
      hourly_rate DECIMAL(10, 2) DEFAULT 0,
      status ENUM('active', 'inactive') DEFAULT 'active',
      hire_date DATE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_status (status),
      INDEX idx_email (email)
  );

-- ============================================================================
-- TABLE: platforms
-- Description: Job platforms where work comes from
-- Examples: WorkMarket, FieldNation, TechLink, Tech Service Today, Direct, Internal
-- ============================================================================
CREATE TABLE platforms (
      platform_id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL UNIQUE,
      code VARCHAR(20) NOT NULL UNIQUE,
      description TEXT,
      api_endpoint VARCHAR(255),
      status ENUM('active', 'inactive') DEFAULT 'active',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_code (code)
  );

-- ============================================================================
-- TABLE: jobs
-- Description: Job listings with details from all platforms
-- Each job is associated with a platform and has billing information
-- ============================================================================
CREATE TABLE jobs (
      job_id INT PRIMARY KEY AUTO_INCREMENT,
      platform_id INT NOT NULL,
      platform_job_code VARCHAR(50),
      ticket_number VARCHAR(50) UNIQUE,
      description VARCHAR(255) NOT NULL,
      client_name VARCHAR(100),
      job_type VARCHAR(100),
      location VARCHAR(255),

    -- Billing Information
    billing_type ENUM('flat_rate', 'hourly', 'per_task') DEFAULT 'flat_rate',
      billing_amount DECIMAL(10, 2),
      estimated_hours DECIMAL(8, 2),

    -- Job Status
    job_status ENUM('pending', 'assigned', 'in_progress', 'completed', 'cancelled') DEFAULT 'pending',

    -- Dates
    job_date DATE,
      due_date DATE,
      completed_date DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id),
      INDEX idx_platform_id (platform_id),
      INDEX idx_ticket_number (ticket_number),
      INDEX idx_job_status (job_status),
      INDEX idx_job_date (job_date)
  );

-- ============================================================================
-- TABLE: pay_periods
-- Description: Bi-weekly pay period tracking
-- Used to organize time entries and generate payroll reports
-- ============================================================================
CREATE TABLE pay_periods (
      period_id INT PRIMARY KEY AUTO_INCREMENT,
      start_date DATE NOT NULL,
      end_date DATE NOT NULL,
      period_name VARCHAR(50),
      status ENUM('open', 'closed', 'archived') DEFAULT 'open',
      total_hours DECIMAL(10, 2),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      closed_at TIMESTAMP NULL,

    UNIQUE KEY unique_period (start_date, end_date),
      INDEX idx_status (status),
      INDEX idx_end_date (end_date)
  );

-- ============================================================================
-- TABLE: time_entries
-- Description: Time tracking entries for technicians on jobs
-- Includes actual time in/out and calculated hours
-- Includes reference to audit log for data integrity
-- ============================================================================
CREATE TABLE time_entries (
      entry_id INT PRIMARY KEY AUTO_INCREMENT,
      job_id INT NOT NULL,
      tech_id INT NOT NULL,
      period_id INT,

    -- Time Information
    date_worked DATE NOT NULL,
      time_in TIME,
      time_out TIME,
      hours_worked DECIMAL(8, 2),

    -- Entry Status
    status ENUM('draft', 'submitted', 'verified', 'billed', 'paid') DEFAULT 'draft',
      notes TEXT,

    -- Verification
    verified_by INT,
      verified_at TIMESTAMP NULL,

    created_by INT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_by INT,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
      FOREIGN KEY (tech_id) REFERENCES technicians(tech_id),
      FOREIGN KEY (period_id) REFERENCES pay_periods(period_id),
      INDEX idx_tech_id (tech_id),
      INDEX idx_job_id (job_id),
      INDEX idx_date_worked (date_worked),
      INDEX idx_status (status),
      INDEX idx_period_id (period_id)
  );

-- ============================================================================
-- TABLE: users
-- Description: System users (login accounts)
-- Links technicians to authentication accounts
-- Includes role-based access control
-- ============================================================================
CREATE TABLE users (
      user_id INT PRIMARY KEY AUTO_INCREMENT,
      tech_id INT,
      email VARCHAR(100) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      full_name VARCHAR(100),

    -- Roles: admin, manager, technician
    role ENUM('admin', 'manager', 'technician') DEFAULT 'technician',

    -- Account Status
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',

    -- Last Login
    last_login TIMESTAMP NULL,

    -- Account Management
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      password_changed_at TIMESTAMP NULL,

    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id),
      INDEX idx_email (email),
      INDEX idx_role (role),
      INDEX idx_status (status)
  );

-- ============================================================================
-- TABLE: invoices
-- Description: Billing and invoicing information
-- Tracks invoice creation and payment status
-- ============================================================================
CREATE TABLE invoices (
      invoice_id INT PRIMARY KEY AUTO_INCREMENT,
      invoice_number VARCHAR(50) UNIQUE,
      period_id INT,

    -- Totals
    subtotal DECIMAL(10, 2),
      tax DECIMAL(10, 2),
      total_amount DECIMAL(10, 2),

    -- Payment Status
    status ENUM('draft', 'sent', 'partially_paid', 'paid', 'overdue', 'cancelled') DEFAULT 'draft',

    -- Dates
    issue_date DATE,
      due_date DATE,
      paid_date DATE,

    -- Notes
    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (period_id) REFERENCES pay_periods(period_id),
      INDEX idx_status (status),
      INDEX idx_issue_date (issue_date)
  );

-- ============================================================================
-- TABLE: audit_logs
-- Description: Comprehensive audit trail of all system actions
-- Tracks who did what, when, and what changed
-- Essential for compliance and debugging
-- ============================================================================
CREATE TABLE audit_logs (
      log_id INT PRIMARY KEY AUTO_INCREMENT,
      user_id INT,
      action_type VARCHAR(50) NOT NULL,
      entity_type VARCHAR(50),
      entity_id INT,

    -- What Changed
    old_values JSON,
      new_values JSON,

    -- Details
    description TEXT,
      ip_address VARCHAR(45),
      user_agent TEXT,

    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
      INDEX idx_action_type (action_type),
      INDEX idx_entity_type (entity_type),
      INDEX idx_entity_id (entity_id),
      INDEX idx_created_at (created_at),
      INDEX idx_user_id (user_id)
  );

-- ============================================================================
-- INITIAL DATA: Add default platforms
-- ============================================================================
INSERT INTO platforms (name, code, description) VALUES
('WorkMarket', 'workmarket', 'WorkMarket job platform'),
('FieldNation', 'fieldnation', 'FieldNation job platform'),
('TechLink', 'techlink', 'TechLink job platform'),
('Tech Service Today', 'techservicetoday', 'Tech Service Today job platform'),
('Direct Client Work', 'direct', 'Direct work from clients'),
('Internal Work', 'internal', 'Internal company work');

-- ============================================================================
-- VIEWS: Useful database views for reporting
-- ============================================================================

-- View: Tech Hours by Pay Period
CREATE VIEW v_tech_hours_by_period AS
SELECT 
    t.tech_id,
    t.name,
    pp.period_id,
    pp.period_name,
    pp.start_date,
    pp.end_date,
    COALESCE(SUM(te.hours_worked), 0) as total_hours,
    COUNT(DISTINCT te.job_id) as job_count,
    COALESCE(SUM(te.hours_worked) * t.hourly_rate, 0) as total_earnings
FROM technicians t
LEFT JOIN time_entries te ON t.tech_id = te.tech_id
LEFT JOIN pay_periods pp ON te.period_id = pp.period_id
WHERE te.status IN ('verified', 'billed', 'paid')
GROUP BY t.tech_id, t.name, pp.period_id;

-- View: Job Billing Summary
CREATE VIEW v_job_billing_summary AS
SELECT 
    j.job_id,
    j.ticket_number,
    j.description,
    p.name as platform,
    j.billing_type,
    j.billing_amount,
    COALESCE(COUNT(DISTINCT te.entry_id), 0) as time_entries_count,
    COALESCE(SUM(te.hours_worked), 0) as actual_hours,
    j.job_status,
    j.completed_date
FROM jobs j
LEFT JOIN platforms p ON j.platform_id = p.platform_id
LEFT JOIN time_entries te ON j.job_id = te.job_id AND te.status IN ('verified', 'billed', 'paid')
GROUP BY j.job_id;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
-- To initialize the database, run:
-- mysql -u username -p database_name < schema.sql
-- ============================================================================
