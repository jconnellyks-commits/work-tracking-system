# Payout System Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core payout infrastructure — database models, pay period preferences, contractor/employee field, payroll→payout rename, payout locking with snapshots, and the period-scoped pay calculator.

**Architecture:** Additive changes to the existing Flask + SQLAlchemy app. New models in `app/models.py`, new route blueprints for payouts and advances, extracted pay calculation logic into a reusable function, and frontend updates to rename payroll→payout and add the locking UI.

**Tech Stack:** Flask, SQLAlchemy, MySQL, vanilla JavaScript SPA

**Spec:** `docs/superpowers/specs/2026-03-17-payout-system-design.md`

---

## File Map

### New Files
| File | Purpose |
|------|---------|
| `database/migrations/012_payout_system.sql` | Migration: new tables + Technician.worker_type + PayPeriod locked status |
| `app/routes/payouts.py` | Payout CRUD, lock, pay endpoints |
| `app/routes/payout_adjustments.py` | Adjustment listing and resolution |
| `app/routes/advances.py` | Advance CRUD and cancellation |
| `app/routes/my.py` | Technician self-service endpoints (stub for phase 2) |

### Modified Files
| File | Lines Affected | Change |
|------|---------------|--------|
| `app/models.py` | After line 550 | Add 6 new models: Payout, PayoutJobDetail, PayoutLineItem, Advance, AdvanceRepayment, PayoutAdjustment |
| `app/models.py` | Line 9-43 (Technician) | Add `worker_type` column |
| `app/models.py` | Line 148 (PayPeriod) | Add `locked` to status enum |
| `app/utils/pay_calculator.py` | After line 225 | Add `calculate_period_pay(period_id, tech_ids=None)` extracted from reports.py |
| `app/__init__.py` | Line ~83 | Register new blueprints |
| `app/static/js/api.js` | After line 372 | Add payouts, advances, payout-adjustments, my API methods |
| `app/static/js/app.js` | Sidebar (~line 54) | Rename "Reports" label, add "Payout" nav item |
| `app/static/js/app.js` | Navigate (~line 95) | Add 'payout' case |
| `app/static/js/app.js` | Reports section (~line 2240) | Rename payroll references |
| `app/static/js/app.js` | After reports section | Add Pages.payout() page with lock/pay UI |
| `app/routes/technicians.py` | Technician CRUD | Include worker_type in create/update/response |

---

## Chunk 1: Database Migration & Models

### Task 1: Write the database migration

**Files:**
- Create: `database/migrations/012_payout_system.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
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
```

- [ ] **Step 2: Commit migration**

```bash
git add database/migrations/012_payout_system.sql
git commit -m "feat: add payout system database migration (012)"
```

---

### Task 2: Add SQLAlchemy models

**Files:**
- Modify: `app/models.py` — add worker_type to Technician, update PayPeriod enum, add 6 new models after AuditLog

- [ ] **Step 1: Add `worker_type` to Technician model**

In `app/models.py`, add after `sms_opted_in` field (around line 17):
```python
worker_type = db.Column(db.String(20), nullable=False, default='contractor')
```

And add `'worker_type': self.worker_type` to `Technician.to_dict()`.

- [ ] **Step 2: Update PayPeriod status enum**

In `app/models.py` line 148, change:
```python
status = db.Column(db.Enum('open', 'closed', 'archived'), default='open')
```
to:
```python
status = db.Column(db.Enum('open', 'locked', 'closed', 'archived'), default='open')
```

- [ ] **Step 3: Add new model classes after AuditLog (after line 550)**

Add these models at the end of `app/models.py`:

```python
class Payout(db.Model):
    """Payout record — one per tech per pay period, created at lock time."""
    __tablename__ = 'payouts'

    payout_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    period_id = db.Column(db.Integer, db.ForeignKey('pay_periods.period_id'), nullable=False)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=False)
    status = db.Column(db.Enum('locked', 'paid'), nullable=False, default='locked')
    total_hours = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_base_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_mileage_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_per_diem = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_personal_expenses = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_bonuses = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_deductions = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_advance_repayment = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    net_payout = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    locked_at = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime)
    paid_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    notes = db.Column(db.Text)

    # Relationships
    pay_period = db.relationship('PayPeriod', backref=db.backref('payouts', lazy='dynamic'))
    technician = db.relationship('Technician', backref=db.backref('payouts', lazy='dynamic'))
    job_details = db.relationship('PayoutJobDetail', backref='payout', lazy='dynamic', cascade='all, delete-orphan')
    line_items = db.relationship('PayoutLineItem', backref='payout', lazy='dynamic', cascade='all, delete-orphan')
    advance_repayments = db.relationship('AdvanceRepayment', backref='payout', lazy='dynamic', cascade='all, delete-orphan')
    adjustments = db.relationship('PayoutAdjustment', backref='payout', lazy='dynamic', cascade='all, delete-orphan')

    def recalculate_net(self):
        """Recalculate net_payout from component fields. Call after line item changes."""
        bonus_sum = sum(li.amount for li in self.line_items.filter_by(type='bonus').all())
        deduction_sum = sum(li.amount for li in self.line_items.filter_by(type='deduction').all())
        self.total_bonuses = bonus_sum
        self.total_deductions = deduction_sum
        self.net_payout = (
            self.total_base_pay + self.total_mileage_pay + self.total_per_diem
            + self.total_personal_expenses + self.total_bonuses
            - self.total_deductions - self.total_advance_repayment
        )

    def to_dict(self):
        return {
            'payout_id': self.payout_id,
            'period_id': self.period_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'worker_type': self.technician.worker_type if self.technician else None,
            'status': self.status,
            'total_hours': float(self.total_hours or 0),
            'total_base_pay': float(self.total_base_pay or 0),
            'total_mileage_pay': float(self.total_mileage_pay or 0),
            'total_per_diem': float(self.total_per_diem or 0),
            'total_personal_expenses': float(self.total_personal_expenses or 0),
            'total_bonuses': float(self.total_bonuses or 0),
            'total_deductions': float(self.total_deductions or 0),
            'total_advance_repayment': float(self.total_advance_repayment or 0),
            'net_payout': float(self.net_payout or 0),
            'locked_at': self.locked_at.isoformat() if self.locked_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'paid_by': self.paid_by,
            'notes': self.notes,
        }


class PayoutJobDetail(db.Model):
    """Snapshot of pay per job per tech per payout."""
    __tablename__ = 'payout_job_details'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'), nullable=False)
    hours = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    base_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    mileage_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    per_diem = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    personal_expenses = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    effective_rate = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    profit_share = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    job = db.relationship('Job', backref=db.backref('payout_details', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'payout_id': self.payout_id,
            'job_id': self.job_id,
            'job_ticket': self.job.ticket_number if self.job else None,
            'job_description': self.job.description if self.job else None,
            'job_client': self.job.client_name if self.job else None,
            'external_url': self.job.external_url if self.job else None,
            'hours': float(self.hours or 0),
            'base_pay': float(self.base_pay or 0),
            'mileage_pay': float(self.mileage_pay or 0),
            'per_diem': float(self.per_diem or 0),
            'personal_expenses': float(self.personal_expenses or 0),
            'effective_rate': float(self.effective_rate or 0),
            'profit_share': float(self.profit_share or 0),
        }


class PayoutLineItem(db.Model):
    """Bonus or deduction line item on a payout."""
    __tablename__ = 'payout_line_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.Enum('bonus', 'deduction'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'payout_id': self.payout_id,
            'type': self.type,
            'description': self.description,
            'amount': float(self.amount or 0),
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Advance(db.Model):
    """Advance given to a technician — carries balance across pay periods."""
    __tablename__ = 'advances'

    advance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    original_amount = db.Column(db.Numeric(10, 2), nullable=False)
    remaining_balance = db.Column(db.Numeric(10, 2), nullable=False)
    max_per_period = db.Column(db.Numeric(10, 2))
    status = db.Column(db.Enum('active', 'repaid', 'cancelled'), nullable=False, default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    repaid_at = db.Column(db.DateTime)

    technician = db.relationship('Technician', backref=db.backref('advances', lazy='dynamic'))
    repayments = db.relationship('AdvanceRepayment', backref='advance', lazy='dynamic')

    def to_dict(self):
        return {
            'advance_id': self.advance_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'description': self.description,
            'original_amount': float(self.original_amount or 0),
            'remaining_balance': float(self.remaining_balance or 0),
            'max_per_period': float(self.max_per_period) if self.max_per_period else None,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'repaid_at': self.repaid_at.isoformat() if self.repaid_at else None,
        }


class AdvanceRepayment(db.Model):
    """Tracks each deduction against an advance per payout period."""
    __tablename__ = 'advance_repayments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    advance_id = db.Column(db.Integer, db.ForeignKey('advances.advance_id'), nullable=False)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'advance_id': self.advance_id,
            'payout_id': self.payout_id,
            'amount': float(self.amount or 0),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PayoutAdjustment(db.Model):
    """Post-lock change detection record."""
    __tablename__ = 'payout_adjustments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'))
    entry_id = db.Column(db.Integer, db.ForeignKey('time_entries.entry_id'))
    description = db.Column(db.Text, nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    amount_diff = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    resolution = db.Column(db.Enum('pending', 'carried_forward', 'dismissed'), nullable=False, default='pending')
    resolved_to_period_id = db.Column(db.Integer, db.ForeignKey('pay_periods.period_id'))
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    job = db.relationship('Job', backref=db.backref('payout_adjustments', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'payout_id': self.payout_id,
            'type': self.type,
            'job_id': self.job_id,
            'job_ticket': self.job.ticket_number if self.job else None,
            'entry_id': self.entry_id,
            'description': self.description,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'amount_diff': float(self.amount_diff or 0),
            'resolution': self.resolution,
            'resolved_to_period_id': self.resolved_to_period_id,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
```

- [ ] **Step 4: Commit models**

```bash
git add app/models.py
git commit -m "feat: add payout system models (Payout, PayoutJobDetail, PayoutLineItem, Advance, AdvanceRepayment, PayoutAdjustment)"
```

---

### Task 3: Update Technician routes for worker_type

**Files:**
- Modify: `app/routes/technicians.py`

- [ ] **Step 1: Add worker_type to create/update endpoints**

In the create technician endpoint, add `worker_type` to the fields read from request data:
```python
worker_type = data.get('worker_type', 'contractor')
```
Set it on the new Technician object.

In the update endpoint, add:
```python
if 'worker_type' in data:
    tech.worker_type = data['worker_type']
```

- [ ] **Step 2: Verify `to_dict()` already includes worker_type**

The model's `to_dict()` was updated in Task 2. Verify the technician list/get endpoints already use `to_dict()` and will automatically include `worker_type`.

- [ ] **Step 3: Commit**

```bash
git add app/routes/technicians.py
git commit -m "feat: support worker_type (contractor/employee) in technician CRUD"
```

---

## Chunk 2: Period-Scoped Pay Calculator & Payout Lock Engine

### Task 4: Extract `calculate_period_pay()` from reports.py

**Files:**
- Modify: `app/utils/pay_calculator.py` — add new function
- Reference: `app/routes/reports.py` lines 124-361 (payroll_detail_report)

This is the most critical task. The existing `payroll_detail_report()` in reports.py has inline pay calculation logic that prorates by period hours ratio. We need to extract that into a reusable function.

- [ ] **Step 1: Read the full payroll_detail_report function**

Read `app/routes/reports.py` from the `payroll_detail_report` function to understand the proration logic, minimum rate enforcement, and hours ratio calculation.

- [ ] **Step 2: Write `calculate_period_pay()` in pay_calculator.py**

Add after `calculate_tech_pay_summary()` (after line 285):

```python
def calculate_period_pay(period_id=None, start_date=None, end_date=None, tech_ids=None):
    """
    Calculate pay for all technicians in a pay period or date range.

    Uses the same proration logic as payroll_detail_report:
    - hours_ratio = tech's period hours / total job hours (all time)
    - Prorated billing, expenses, commissions by hours_ratio
    - 50/50 split of (prorated_net - deductions)
    - Minimum rate enforcement

    Args:
        period_id: PayPeriod ID (uses period's start/end dates)
        start_date: Override start date (for ad-hoc reports)
        end_date: Override end date (for ad-hoc reports)
        tech_ids: Optional list of tech IDs to filter (None = all)

    Returns:
        dict: {
            'period': {...},
            'technicians': [
                {
                    'tech_id': int,
                    'tech_name': str,
                    'worker_type': str,
                    'total_hours': float,
                    'total_base_pay': float,
                    'total_mileage_pay': float,
                    'total_per_diem': float,
                    'total_personal_expenses': float,
                    'total_pay': float,
                    'jobs': [
                        {
                            'job_id': int,
                            'job': {...},
                            'hours': float,
                            'hours_ratio': float,
                            'base_pay': float,
                            'mileage_pay': float,
                            'per_diem': float,
                            'personal_expenses': float,
                            'effective_rate': float,
                            'profit_share': float,
                            'total_pay': float,
                        }
                    ]
                }
            ],
            'grand_totals': {
                'total_hours': float,
                'total_base_pay': float,
                'total_mileage_pay': float,
                'total_per_diem': float,
                'total_personal_expenses': float,
                'total_pay': float,
            }
        }
    """
```

The implementation should be extracted from the logic in `payroll_detail_report()`. Key steps:
1. Get period date range: if `period_id` given, resolve to `period.start_date`/`period.end_date`. Always filter entries by `TimeEntry.date_worked BETWEEN start_date AND end_date` (NOT by `TimeEntry.period_id` FK — this matches existing report behavior).
2. Query time entries in the date range, optionally filtered by tech_ids
3. Group entries by tech, then by job
4. For each tech+job combination:
   - Get ALL entries for that job (not just period) to calculate total job hours
   - `hours_ratio = period_hours / total_job_hours`
   - Prorate: `billing * ratio`, `expenses * ratio`, `commissions * ratio`
   - Calculate `entry_net = prorated_billing - prorated_expenses - prorated_commissions`
   - Sum deductions: mileage_pay + per_diem + personal_expenses (for this tech's period entries)
   - `tech_pool = (entry_net - deductions) / 2`
   - Apply minimum rate: `max(tech_pool / hours, tech.hourly_rate) * hours`
   - Calculate profit_share
5. Aggregate per-tech and grand totals

- [ ] **Step 3: Update `payroll_detail_report()` to use `calculate_period_pay()`**

Replace the inline calculation logic in `payroll_detail_report()` with a call to `calculate_period_pay()`, reformatting the return data to match the existing API response shape. This ensures the existing payroll report still works identically.

- [ ] **Step 4: Test by running the existing payroll report**

Deploy and verify the existing payroll report produces identical results.

- [ ] **Step 5: Commit**

```bash
git add app/utils/pay_calculator.py app/routes/reports.py
git commit -m "refactor: extract calculate_period_pay() from payroll_detail_report"
```

---

### Task 5: Create payout routes — lock and pay endpoints

**Files:**
- Create: `app/routes/payouts.py`
- Modify: `app/__init__.py` — register blueprint

- [ ] **Step 1: Create `app/routes/payouts.py`**

```python
"""Payout management routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify
from app import db
from app.models import (
    Payout, PayoutJobDetail, PayoutLineItem, PayPeriod,
    Advance, AdvanceRepayment, Technician
)
from app.utils.auth import manager_required
from app.utils.pay_calculator import calculate_period_pay

payouts_bp = Blueprint('payouts', __name__)


@payouts_bp.route('/', methods=['GET'])
@manager_required
def list_payouts():
    """List payouts for a period."""
    period_id = request.args.get('period_id', type=int)
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    payouts = Payout.query.filter_by(period_id=period_id).all()
    return jsonify({
        'payouts': [p.to_dict() for p in payouts]
    })


@payouts_bp.route('/<int:payout_id>', methods=['GET'])
@manager_required
def get_payout(payout_id):
    """Get single payout with job details and line items."""
    payout = Payout.query.get_or_404(payout_id)
    data = payout.to_dict()
    data['job_details'] = [jd.to_dict() for jd in payout.job_details.all()]
    data['line_items'] = [li.to_dict() for li in payout.line_items.all()]
    data['advance_repayments'] = [ar.to_dict() for ar in payout.advance_repayments.all()]
    return jsonify(data)


@payouts_bp.route('/lock', methods=['POST'])
@manager_required
def lock_payouts():
    """Lock all payouts for a period — creates snapshot records."""
    data = request.get_json()
    period_id = data.get('period_id')
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    period = PayPeriod.query.get_or_404(period_id)
    if period.status != 'open':
        return jsonify({'error': f'Period is {period.status}, must be open to lock'}), 400

    # Check no existing payouts
    existing = Payout.query.filter_by(period_id=period_id).first()
    if existing:
        return jsonify({'error': 'Payouts already exist for this period'}), 400

    # Calculate period pay
    pay_data = calculate_period_pay(period_id=period_id)
    if not pay_data or not pay_data['technicians']:
        return jsonify({'error': 'No technician pay data found for this period'}), 400

    now = datetime.utcnow()
    payouts_created = []

    for tech_data in pay_data['technicians']:
        tech_id = tech_data['tech_id']

        # Create payout record
        payout = Payout(
            period_id=period_id,
            tech_id=tech_id,
            status='locked',
            total_hours=tech_data['total_hours'],
            total_base_pay=tech_data['total_base_pay'],
            total_mileage_pay=tech_data['total_mileage_pay'],
            total_per_diem=tech_data['total_per_diem'],
            total_personal_expenses=tech_data['total_personal_expenses'],
            total_bonuses=0,
            total_deductions=0,
            total_advance_repayment=0,
            locked_at=now,
        )

        # Calculate net before advances
        net_before_advances = (
            payout.total_base_pay + payout.total_mileage_pay
            + payout.total_per_diem + payout.total_personal_expenses
        )

        # Process advance repayments (oldest first)
        total_advance_repayment = 0
        active_advances = Advance.query.filter_by(
            tech_id=tech_id, status='active'
        ).order_by(Advance.created_at.asc()).all()

        available = float(net_before_advances)
        for advance in active_advances:
            if available <= 0:
                break
            cap = float(advance.max_per_period or advance.remaining_balance)
            repay = min(cap, float(advance.remaining_balance), available)
            if repay > 0:
                db.session.add(payout)  # Need payout in session for FK
                db.session.flush()  # Get payout_id

                repayment = AdvanceRepayment(
                    advance_id=advance.advance_id,
                    payout_id=payout.payout_id,
                    amount=repay,
                )
                db.session.add(repayment)
                advance.remaining_balance = float(advance.remaining_balance) - repay
                if advance.remaining_balance <= 0:
                    advance.remaining_balance = 0
                    advance.status = 'repaid'
                    advance.repaid_at = now
                total_advance_repayment += repay
                available -= repay

        payout.total_advance_repayment = total_advance_repayment
        db.session.add(payout)
        db.session.flush()
        payout.recalculate_net()  # Uses canonical formula from model
        db.session.flush()

        # Create job detail snapshots
        for job_data in tech_data['jobs']:
            detail = PayoutJobDetail(
                payout_id=payout.payout_id,
                job_id=job_data['job_id'],
                hours=job_data['hours'],
                base_pay=job_data['base_pay'],
                mileage_pay=job_data['mileage_pay'],
                per_diem=job_data['per_diem'],
                personal_expenses=job_data['personal_expenses'],
                effective_rate=job_data['effective_rate'],
                profit_share=job_data.get('profit_share', 0),
            )
            db.session.add(detail)

        payouts_created.append(payout)

    # Lock the period
    period.status = 'locked'
    db.session.commit()

    return jsonify({
        'message': f'Locked {len(payouts_created)} payouts',
        'payouts': [p.to_dict() for p in payouts_created]
    })


@payouts_bp.route('/<int:payout_id>/pay', methods=['POST'])
@manager_required
def pay_payout(payout_id):
    """Mark a single payout as paid."""
    from flask import g
    payout = Payout.query.get_or_404(payout_id)
    if payout.status != 'locked':
        return jsonify({'error': 'Payout must be locked to mark as paid'}), 400

    payout.status = 'paid'
    payout.paid_at = datetime.utcnow()
    payout.paid_by = g.user_id

    # Check if all payouts for this period are now paid
    period = PayPeriod.query.get(payout.period_id)
    unpaid = Payout.query.filter_by(period_id=payout.period_id).filter(Payout.status != 'paid').count()
    if unpaid <= 1:  # This one is about to be paid
        period.status = 'closed'
        period.closed_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'message': 'Payout marked as paid', 'payout': payout.to_dict()})


@payouts_bp.route('/pay-all', methods=['POST'])
@manager_required
def pay_all_payouts():
    """Mark all locked payouts for a period as paid."""
    from flask import g
    data = request.get_json()
    period_id = data.get('period_id')
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    payouts = Payout.query.filter_by(period_id=period_id, status='locked').all()
    if not payouts:
        return jsonify({'error': 'No locked payouts found'}), 400

    now = datetime.utcnow()
    for payout in payouts:
        payout.status = 'paid'
        payout.paid_at = now
        payout.paid_by = g.user_id

    # Close the period
    period = PayPeriod.query.get(period_id)
    period.status = 'closed'
    period.closed_at = now

    db.session.commit()
    return jsonify({'message': f'Marked {len(payouts)} payouts as paid'})


@payouts_bp.route('/<int:payout_id>/line-items', methods=['POST'])
@manager_required
def add_line_item(payout_id):
    """Add a bonus or deduction to a locked payout."""
    from flask import g
    payout = Payout.query.get_or_404(payout_id)
    if payout.status != 'locked':
        return jsonify({'error': 'Can only add line items to locked payouts'}), 400

    data = request.get_json()
    item_type = data.get('type')
    if item_type not in ('bonus', 'deduction'):
        return jsonify({'error': 'type must be bonus or deduction'}), 400

    li = PayoutLineItem(
        payout_id=payout_id,
        type=item_type,
        description=data.get('description', ''),
        amount=data.get('amount', 0),
        created_by=g.user_id,
    )
    db.session.add(li)
    db.session.flush()
    payout.recalculate_net()
    db.session.commit()
    return jsonify({'message': 'Line item added', 'line_item': li.to_dict(), 'payout': payout.to_dict()})


@payouts_bp.route('/line-items/<int:item_id>', methods=['DELETE'])
@manager_required
def remove_line_item(item_id):
    """Remove a line item from a locked payout."""
    li = PayoutLineItem.query.get_or_404(item_id)
    payout = Payout.query.get(li.payout_id)
    if payout.status != 'locked':
        return jsonify({'error': 'Can only remove line items from locked payouts'}), 400

    db.session.delete(li)
    db.session.flush()
    payout.recalculate_net()
    db.session.commit()
    return jsonify({'message': 'Line item removed', 'payout': payout.to_dict()})


@payouts_bp.route('/<int:payout_id>/stub', methods=['GET'])
@manager_required
def get_stub(payout_id):
    """Get full pay stub data for a payout."""
    payout = Payout.query.get_or_404(payout_id)
    data = payout.to_dict()
    data['period'] = payout.pay_period.to_dict()
    data['job_details'] = [jd.to_dict() for jd in payout.job_details.all()]
    data['line_items'] = [li.to_dict() for li in payout.line_items.all()]
    data['advance_repayments'] = [ar.to_dict() for ar in payout.advance_repayments.all()]
    return jsonify(data)
```

- [ ] **Step 2: Create `app/routes/advances.py`**

```python
"""Advance management routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import Advance
from app.utils.auth import manager_required

advances_bp = Blueprint('advances', __name__)


@advances_bp.route('/', methods=['GET'])
@manager_required
def list_advances():
    """List advances, optionally filtered by tech and status."""
    query = Advance.query
    tech_id = request.args.get('tech_id', type=int)
    status = request.args.get('status')
    if tech_id:
        query = query.filter_by(tech_id=tech_id)
    if status:
        query = query.filter_by(status=status)
    advances = query.order_by(Advance.created_at.desc()).all()
    return jsonify({'advances': [a.to_dict() for a in advances]})


@advances_bp.route('/', methods=['POST'])
@manager_required
def create_advance():
    """Create a new advance for a technician."""
    data = request.get_json()
    tech_id = data.get('tech_id')
    amount = float(data.get('original_amount', 0))
    if not tech_id or amount <= 0:
        return jsonify({'error': 'tech_id and positive original_amount required'}), 400

    advance = Advance(
        tech_id=tech_id,
        description=data.get('description', ''),
        original_amount=amount,
        remaining_balance=amount,
        max_per_period=data.get('max_per_period'),
        created_by=g.user_id,
    )
    db.session.add(advance)
    db.session.commit()
    return jsonify({'message': 'Advance created', 'advance': advance.to_dict()}), 201


@advances_bp.route('/<int:advance_id>', methods=['PUT'])
@manager_required
def update_advance(advance_id):
    """Update an advance (e.g. change max_per_period)."""
    advance = Advance.query.get_or_404(advance_id)
    if advance.status != 'active':
        return jsonify({'error': 'Can only update active advances'}), 400

    data = request.get_json()
    if 'max_per_period' in data:
        advance.max_per_period = data['max_per_period']
    if 'description' in data:
        advance.description = data['description']

    db.session.commit()
    return jsonify({'message': 'Advance updated', 'advance': advance.to_dict()})


@advances_bp.route('/<int:advance_id>/cancel', methods=['POST'])
@manager_required
def cancel_advance(advance_id):
    """Cancel an active advance."""
    advance = Advance.query.get_or_404(advance_id)
    if advance.status != 'active':
        return jsonify({'error': 'Can only cancel active advances'}), 400

    advance.status = 'cancelled'
    db.session.commit()
    return jsonify({'message': 'Advance cancelled', 'advance': advance.to_dict()})
```

- [ ] **Step 3: Create `app/routes/payout_adjustments.py`**

```python
"""Payout adjustment routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import PayoutAdjustment, Payout, PayoutLineItem, PayPeriod
from app.utils.auth import manager_required

payout_adjustments_bp = Blueprint('payout_adjustments', __name__)


@payout_adjustments_bp.route('/', methods=['GET'])
@manager_required
def list_adjustments():
    """List adjustments, filtered by period and/or resolution status."""
    query = PayoutAdjustment.query
    period_id = request.args.get('period_id', type=int)
    resolution = request.args.get('resolution')
    if period_id:
        query = query.join(Payout).filter(Payout.period_id == period_id)
    if resolution:
        query = query.filter_by(resolution=resolution)
    adjustments = query.order_by(PayoutAdjustment.created_at.desc()).all()
    return jsonify({'adjustments': [a.to_dict() for a in adjustments]})


@payout_adjustments_bp.route('/<int:adj_id>/resolve', methods=['POST'])
@manager_required
def resolve_adjustment(adj_id):
    """Resolve an adjustment — carry forward or dismiss."""
    adj = PayoutAdjustment.query.get_or_404(adj_id)
    if adj.resolution != 'pending':
        return jsonify({'error': 'Adjustment already resolved'}), 400

    data = request.get_json()
    resolution = data.get('resolution')
    if resolution not in ('carried_forward', 'dismissed'):
        return jsonify({'error': 'resolution must be carried_forward or dismissed'}), 400

    adj.resolution = resolution
    adj.resolved_by = g.user_id
    adj.resolved_at = datetime.utcnow()

    if resolution == 'carried_forward':
        # Find the tech's next open payout period
        payout = Payout.query.get(adj.payout_id)
        next_period = PayPeriod.query.filter(
            PayPeriod.status == 'open',
            PayPeriod.start_date > payout.pay_period.end_date
        ).order_by(PayPeriod.start_date.asc()).first()

        if not next_period:
            return jsonify({'error': 'No open future pay period found to carry forward to'}), 400

        adj.resolved_to_period_id = next_period.period_id

        # If the next period already has a locked payout for this tech, add a line item now
        payout = Payout.query.get(adj.payout_id)
        next_payout = Payout.query.filter_by(
            period_id=next_period.period_id, tech_id=payout.tech_id
        ).first()

        if next_payout and next_payout.status == 'locked':
            # Add as bonus (positive diff) or deduction (negative diff)
            li_type = 'bonus' if float(adj.amount_diff) >= 0 else 'deduction'
            li = PayoutLineItem(
                payout_id=next_payout.payout_id,
                type=li_type,
                description=f'Carried forward: {adj.description}',
                amount=abs(float(adj.amount_diff)),
                created_by=g.user_id,
            )
            db.session.add(li)
            db.session.flush()
            next_payout.recalculate_net()
        # If next period is still open, the lock engine will pick up pending
        # carried-forward adjustments when it locks that period

    db.session.commit()
    return jsonify({'message': f'Adjustment {resolution}', 'adjustment': adj.to_dict()})
```

- [ ] **Step 4: Create `app/routes/my.py`** (stub for tech self-service)

```python
"""Technician self-service routes."""
from flask import Blueprint, jsonify, g
from app.models import Payout, PayPeriod, User
from app.utils.auth import jwt_required_with_user
from decimal import Decimal
from datetime import date

my_bp = Blueprint('my', __name__)


@my_bp.route('/dashboard', methods=['GET'])
@jwt_required_with_user
def my_dashboard():
    """Tech dashboard — YTD earnings, last payout, next period."""
    user = User.query.get(g.user_id)
    if not user or not user.tech_id:
        return jsonify({'error': 'No technician profile linked'}), 400

    tech_id = user.tech_id
    current_year = date.today().year

    # YTD earnings — sum of net_payout for paid payouts this year
    paid_payouts = Payout.query.filter_by(
        tech_id=tech_id, status='paid'
    ).join(PayPeriod).filter(
        PayPeriod.end_date >= date(current_year, 1, 1)
    ).all()

    ytd_earnings = sum(float(p.net_payout or 0) for p in paid_payouts)

    # Last payout
    last_payout = Payout.query.filter_by(
        tech_id=tech_id, status='paid'
    ).order_by(Payout.paid_at.desc()).first()

    # Next period end date
    next_period = PayPeriod.query.filter(
        PayPeriod.status.in_(['open', 'locked']),
        PayPeriod.end_date >= date.today()
    ).order_by(PayPeriod.end_date.asc()).first()

    return jsonify({
        'ytd_earnings': ytd_earnings,
        'last_payout': {
            'amount': float(last_payout.net_payout or 0),
            'paid_at': last_payout.paid_at.isoformat() if last_payout and last_payout.paid_at else None,
            'period_name': last_payout.pay_period.period_name if last_payout else None,
        } if last_payout else None,
        'next_period_end': next_period.end_date.isoformat() if next_period else None,
    })


@my_bp.route('/payouts', methods=['GET'])
@jwt_required_with_user
def my_payouts():
    """List tech's paid payouts."""
    user = User.query.get(g.user_id)
    if not user or not user.tech_id:
        return jsonify({'error': 'No technician profile linked'}), 400

    payouts = Payout.query.filter_by(
        tech_id=user.tech_id, status='paid'
    ).join(PayPeriod).order_by(PayPeriod.end_date.desc()).all()

    return jsonify({
        'payouts': [{
            **p.to_dict(),
            'period': p.pay_period.to_dict()
        } for p in payouts]
    })


@my_bp.route('/payouts/<int:payout_id>/stub', methods=['GET'])
@jwt_required_with_user
def my_stub(payout_id):
    """View own pay stub — must be paid and belong to this tech."""
    user = User.query.get(g.user_id)
    if not user or not user.tech_id:
        return jsonify({'error': 'No technician profile linked'}), 400

    payout = Payout.query.get_or_404(payout_id)
    if payout.tech_id != user.tech_id:
        return jsonify({'error': 'Not your payout'}), 403
    if payout.status != 'paid':
        return jsonify({'error': 'Stub not available yet'}), 403

    data = payout.to_dict()
    data['period'] = payout.pay_period.to_dict()
    data['job_details'] = [jd.to_dict() for jd in payout.job_details.all()]
    data['line_items'] = [li.to_dict() for li in payout.line_items.all()]
    data['advance_repayments'] = [ar.to_dict() for ar in payout.advance_repayments.all()]
    return jsonify(data)
```

- [ ] **Step 5: Update deprecated `close_pay_period` in reports.py**

In `app/routes/reports.py`, find the `close_pay_period` function. Update the status guard:

```python
# Change: if period.status != 'open':
# To:
if period.status not in ('open', 'locked'):
    return jsonify({'error': 'Period is not open or locked'}), 400

import logging
logging.getLogger(__name__).warning(
    f'Deprecated: close_pay_period called for period {period_id}. '
    'Use the payout workflow (lock → pay) instead.'
)
```

This ensures locked periods can still be manually closed via the legacy endpoint while logging a deprecation warning.

- [ ] **Step 6: Register blueprints in `app/__init__.py`**

Add after the existing blueprint registrations (around line 83):
```python
from app.routes.payouts import payouts_bp
from app.routes.advances import advances_bp
from app.routes.payout_adjustments import payout_adjustments_bp
from app.routes.my import my_bp

app.register_blueprint(payouts_bp, url_prefix='/api/payouts')
app.register_blueprint(advances_bp, url_prefix='/api/advances')
app.register_blueprint(payout_adjustments_bp, url_prefix='/api/payout-adjustments')
app.register_blueprint(my_bp, url_prefix='/api/my')
```

- [ ] **Step 7: Commit backend**

```bash
git add app/routes/payouts.py app/routes/advances.py app/routes/payout_adjustments.py app/routes/my.py app/__init__.py app/routes/reports.py
git commit -m "feat: add payout, advance, adjustment, and self-service API routes"
```

---

## Chunk 3: Frontend — API Client, Rename, and Payout Page

### Task 6: Add payout API methods to api.js

**Files:**
- Modify: `app/static/js/api.js` — add new API method groups

- [ ] **Step 1: Add payout, advance, adjustment, and self-service API methods**

Add after the existing `sms` object (end of API object, before closing `}`):

```javascript
payouts: {
    list(params) {
        const query = new URLSearchParams(params).toString();
        return API.request(`/payouts/?${query}`);
    },
    get(id) {
        return API.request(`/payouts/${id}`);
    },
    lock(data) {
        return API.request('/payouts/lock', { method: 'POST', body: JSON.stringify(data) });
    },
    pay(id) {
        return API.request(`/payouts/${id}/pay`, { method: 'POST' });
    },
    payAll(data) {
        return API.request('/payouts/pay-all', { method: 'POST', body: JSON.stringify(data) });
    },
    addLineItem(payoutId, data) {
        return API.request(`/payouts/${payoutId}/line-items`, { method: 'POST', body: JSON.stringify(data) });
    },
    removeLineItem(itemId) {
        return API.request(`/payouts/line-items/${itemId}`, { method: 'DELETE' });
    },
    getStub(id) {
        return API.request(`/payouts/${id}/stub`);
    },
},

advances: {
    list(params) {
        const query = new URLSearchParams(params).toString();
        return API.request(`/advances/?${query}`);
    },
    create(data) {
        return API.request('/advances/', { method: 'POST', body: JSON.stringify(data) });
    },
    update(id, data) {
        return API.request(`/advances/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    cancel(id) {
        return API.request(`/advances/${id}/cancel`, { method: 'POST' });
    },
},

payoutAdjustments: {
    list(params) {
        const query = new URLSearchParams(params).toString();
        return API.request(`/payout-adjustments/?${query}`);
    },
    resolve(id, data) {
        return API.request(`/payout-adjustments/${id}/resolve`, { method: 'POST', body: JSON.stringify(data) });
    },
},

my: {
    dashboard() {
        return API.request('/my/dashboard');
    },
    payouts() {
        return API.request('/my/payouts');
    },
    stub(id) {
        return API.request(`/my/payouts/${id}/stub`);
    },
},
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/api.js
git commit -m "feat: add payout, advance, adjustment, and self-service API client methods"
```

---

### Task 7: Rename Payroll → Payout in sidebar and navigation

**Files:**
- Modify: `app/static/js/app.js`

- [ ] **Step 1: Add 'payout' to sidebar navigation**

In `setupSidebar()` (around line 54), change the reports menu item and add payout:

Replace the `reports` entry:
```javascript
{ id: 'reports', icon: 'fas fa-chart-bar', label: 'Reports', roles: ['admin', 'manager'] },
```
Keep it as-is (reports page stays for income/expense, etc.), but add a new payout entry after it:
```javascript
{ id: 'payout', icon: 'fas fa-money-bill-wave', label: 'Payout', roles: ['admin', 'manager'] },
```

Also add a tech self-service entry:
```javascript
{ id: 'my-payouts', icon: 'fas fa-file-invoice-dollar', label: 'My Payouts', roles: ['technician'] },
```

- [ ] **Step 2: Add navigation cases**

In `navigate()` (around line 95), add to the titles object:
```javascript
'payout': 'Payout',
'my-payouts': 'My Payouts',
```

Add switch cases:
```javascript
case 'payout':
    await Pages.payout(content);
    break;
case 'my-payouts':
    await Pages.myPayouts(content);
    break;
```

- [ ] **Step 3: Rename "Payroll Report" card on Reports page**

In `Pages.reports()` (around line 2243), change:
```javascript
<div class="stat-label">Payroll Report</div>
```
to:
```javascript
<div class="stat-label">Payout Report (Legacy)</div>
```

And update the onclick to note it's the ad-hoc report:
```javascript
onclick="Pages.showPayrollReport()"
```
(Keep the function name — it's the ad-hoc date-range report that still works.)

- [ ] **Step 4: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add payout nav item, rename payroll references"
```

---

### Task 8: Build the Payout page UI

**Files:**
- Modify: `app/static/js/app.js` — add `Pages.payout()` method

This is the main payout management page. It shows:
- Period selector dropdown
- Summary cards
- Per-tech payout cards with job detail tables
- Lock / Pay All buttons
- Per-tech actions (Pay, Add Bonus, Add Deduction, View Stub)

- [ ] **Step 1: Add `Pages.payout()` method**

Add after the existing payroll methods in app.js. This is a large method — the key sections are:

1. **Period selector** — dropdown of pay periods from `API.reports.payPeriods()`
2. **When period selected** — if period is `open`, show live calculations from `API.reports.payrollDetail()` with a "Lock Payouts" button. If `locked` or `closed`, show snapshot data from `API.payouts.list()`.
3. **Per-tech cards** — same layout as current payroll report but with additional action buttons.
4. **Lock button** — calls `API.payouts.lock({period_id})`, refreshes page.
5. **Pay All button** — calls `API.payouts.payAll({period_id})`, refreshes page.
6. **Per-tech Pay button** — calls `API.payouts.pay(payout_id)`.
7. **Add Bonus/Deduction modals** — simple form: description + amount, calls `API.payouts.addLineItem()`.
8. **View Stub** — opens modal with full stub data from `API.payouts.getStub()`.

Implementation notes:
- Reuse the same table layout/styles as the current `loadPayrollReport()` for consistency.
- The period selector should default to the most recent open or locked period.
- Worker type badge appears next to tech name: `<span class="badge badge-info">Contractor</span>` or `<span class="badge badge-primary">Employee</span>`.

- [ ] **Step 2: Add `Pages.myPayouts()` method for tech self-service**

Simple page showing:
- Dashboard cards (YTD, last payout, next period) from `API.my.dashboard()`
- Table of paid payouts from `API.my.payouts()` with View Stub button
- Stub modal using `API.my.stub(id)`

- [ ] **Step 3: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add payout management page and tech self-service payouts page"
```

---

### Task 9: Add payout preferences to Settings page

**Files:**
- Modify: `app/static/js/app.js` — settings page
- Modify: `app/routes/settings.py` — payout preferences endpoints

- [ ] **Step 1: Add payout preferences API endpoints to settings.py**

Add to `app/routes/settings.py`:

```python
@settings_bp.route('/payout-preferences', methods=['GET'])
@admin_required
def get_payout_preferences():
    """Get payout configuration."""
    return jsonify({
        'interval_days': int(SystemSettings.get_value('payout_interval_days', '14')),
        'anchor_date': SystemSettings.get_value('payout_anchor_date'),
        'auto_generate': SystemSettings.get_value('payout_auto_generate', 'false') == 'true',
    })


@settings_bp.route('/payout-preferences', methods=['PUT'])
@admin_required
def update_payout_preferences():
    """Update payout configuration."""
    data = request.get_json()

    for key in ['payout_interval_days', 'payout_anchor_date', 'payout_auto_generate']:
        short_key = key.replace('payout_', '')
        if short_key in data:
            value = str(data[short_key]).lower() if isinstance(data[short_key], bool) else str(data[short_key])
            setting = SystemSettings.query.filter_by(setting_key=key).first()
            if setting:
                setting.setting_value = value
            else:
                setting = SystemSettings(setting_key=key, setting_value=value, description=f'Payout preference: {short_key}')
                db.session.add(setting)

    db.session.commit()
    return jsonify({'message': 'Payout preferences updated'})
```

- [ ] **Step 2: Add payout preferences section to Settings UI**

In the settings page rendering in app.js, add a "Payout Configuration" card with:
- Interval display (readonly "Biweekly — 14 days")
- Anchor date picker
- Generate Periods button (reuses existing generate modal, pre-filled from preferences)

- [ ] **Step 3: Commit**

```bash
git add app/routes/settings.py app/static/js/app.js
git commit -m "feat: add payout preferences to settings page"
```

---

### Task 10: Run migration and deploy

- [ ] **Step 1: Run migration on server**

Use the established pattern from MEMORY.md — SCP to server, run via dbrun.sh:
```bash
# SCP migration to server
powershell -Command "scp -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' database/migrations/012_payout_system.sql claude-code@34.27.146.58:/tmp/q.sql"

# SSH and run via dbrun.sh
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 '/tmp/dbrun.sh' 2>&1"
```

- [ ] **Step 2: Push and deploy**

```bash
git push origin main
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "cd /opt/work-tracking && sudo git pull origin main && sudo systemctl restart work-tracking"
```

- [ ] **Step 3: Verify**

- Open https://worktracking.sleepybear.tech
- Check "Payout" appears in sidebar
- Open Payout page, select a period
- Test Lock → review snapshots → Mark Paid flow
- Check tech self-service view

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Database migration | `database/migrations/012_payout_system.sql` |
| 2 | SQLAlchemy models | `app/models.py` |
| 3 | Technician worker_type | `app/routes/technicians.py` |
| 4 | Period-scoped pay calculator | `app/utils/pay_calculator.py`, `app/routes/reports.py` |
| 5 | Payout/advance/adjustment routes | `app/routes/payouts.py`, `advances.py`, `payout_adjustments.py`, `my.py`, `app/__init__.py` |
| 6 | API client methods | `app/static/js/api.js` |
| 7 | Sidebar & nav rename | `app/static/js/app.js` |
| 8 | Payout page UI | `app/static/js/app.js` |
| 9 | Payout preferences | `app/routes/settings.py`, `app/static/js/app.js` |
| 10 | Migration & deploy | Server ops |
