# Hourly Billing Calculation & Job Reimbursables

**Date:** 2026-04-18
**Status:** Approved

## Problem

All scraped jobs come in as flat-rate, which works fine. But manually entered hourly jobs have no formula calculating billing — the billing amount must be manually updated after every time entry. Additionally, there's no way to track reimbursable items (travel, parts) on a job.

## Scope

1. Add `billing_rate` field to jobs for hourly rate storage
2. Auto-calculate `billing_amount` (rate x hours) when time entries change on hourly jobs
3. Add reimbursable line items table and UI for tracking per-job expenses that get reimbursed to techs

## Data Changes

### New column: `jobs.billing_rate`

- Type: `DECIMAL(10,2)`, nullable
- Purpose: Stores the hourly rate when `billing_type = 'hourly'`
- Ignored for `flat_rate` and `per_task` jobs
- Existing job `NV-04142601` gets `billing_rate = 65.00` (currently $4680 / 72 hours)

### New table: `job_reimbursables`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INT | PK, AUTO_INCREMENT |
| job_id | INT | FK -> jobs.job_id, NOT NULL |
| description | VARCHAR(255) | NOT NULL |
| amount | DECIMAL(10,2) | NOT NULL |
| category | ENUM('travel','parts','misc') | NOT NULL, DEFAULT 'misc' |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

## Billing Calculation Logic

When `billing_type = 'hourly'`:
- `billing_amount = billing_rate * SUM(time_entries.hours_worked)` for that job
- Recalculate on time entry **create**, **update** (hours changed), and **delete**
- If no time entries exist, `billing_amount = 0`
- If `billing_rate` is null/zero, `billing_amount = 0`

When `billing_type = 'flat_rate'` or `'per_task'`:
- No automatic calculation, `billing_amount` is set manually (current behavior)

### Recalculation function

Add a helper function (in `app/models.py` or a utility):

```python
def recalculate_hourly_billing(job):
    if job.billing_type != 'hourly' or not job.billing_rate:
        return
    total_hours = db.session.query(
        func.coalesce(func.sum(TimeEntry.hours_worked), 0)
    ).filter_by(job_id=job.job_id).scalar()
    job.billing_amount = job.billing_rate * total_hours
```

Call this after any time entry create/update/delete in `app/routes/time_entries.py`.

## Pay Calculation Impact

### Tech pool (unchanged)

The existing formula stays the same:
```
tech_pool = (billing_amount - expenses - commissions) * 0.5
```

`billing_amount` is always the total for the job (auto-calculated for hourly, manual for flat rate). No changes to `pay_calculator.py` for the core formula.

### Reimbursables

- Reimbursable items are added to each tech's total pay as a separate line
- Distribution: sum of reimbursables for the job, split by hours ratio (same as profit share)
- Shows as a separate row in the payroll report (like mileage pay, per diem)
- Does NOT reduce the tech pool — these are pass-through costs reimbursed to techs

## API Changes

### Jobs endpoints

**GET /api/jobs/<id>** — response adds:
- `billing_rate` field
- `reimbursables` array with line items
- `reimbursables_total` computed sum

**POST /api/jobs** and **PUT /api/jobs/<id>** — accept:
- `billing_rate` field
- For hourly jobs, `billing_amount` in request body is ignored (auto-calculated)

### New reimbursables endpoints

All manager-only:

- **POST /api/jobs/<job_id>/reimbursables** — add a line item
  - Body: `{ "description": "Hotel", "amount": 150.00, "category": "travel" }`
- **DELETE /api/jobs/<job_id>/reimbursables/<id>** — remove a line item

### Time entries side effects

After create/update/delete in `time_entries.py`, call `recalculate_hourly_billing(job)` if the job is hourly.

## Frontend Changes

### Job form (create/edit modal)

When billing type dropdown changes to "hourly":
- Show "Billing Rate" input field ($/hr)
- Show "Billing Amount" as read-only display (calculated total)
- Label: "Billing Amount (calculated)" or similar

When billing type is "flat_rate" or "per_task":
- Hide "Billing Rate" field
- Show "Billing Amount" as editable input (current behavior)

### Job detail view (non-editing mode)

For hourly jobs, display:
```
Billing: hourly @ $65.00/hr = $4,680.00 (72.00 hrs)
```

### Reimbursables section on job detail

- Appears below billing info
- Table with columns: Description, Category, Amount, Actions (delete button)
- "Add Reimbursable" button opens inline form or small modal
- Category dropdown: Travel, Parts, Misc
- Running total at bottom of table
- Manager-only: add/delete buttons hidden for non-managers

## Migration

File: `database/migrations/015_add_billing_rate_and_reimbursables.sql`

```sql
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

-- Set billing_rate for existing hourly job
UPDATE jobs SET billing_rate = 65.00 WHERE ticket_number = 'NV-04142601';
```

## Files to modify

- `database/migrations/007_add_billing_rate_and_reimbursables.sql` — new migration
- `app/models.py` — add `billing_rate` column, `JobReimbursable` model, `recalculate_hourly_billing()` helper
- `app/routes/jobs.py` — handle `billing_rate` in create/update, add reimbursables CRUD endpoints, include reimbursables in job detail response
- `app/routes/time_entries.py` — call recalculate after create/update/delete
- `app/utils/pay_calculator.py` — add reimbursables to tech pay output
- `app/static/js/app.js` — billing type toggle, rate field, read-only amount, reimbursables section
- `app/static/css/style.css` — styling for reimbursables section (if needed)

## What stays the same

- Scraper and import code — all scraped jobs are flat_rate, no changes needed
- Report queries that read `billing_amount` — value is always the total
- Core pay pool formula — unchanged
- `per_task` billing type — no changes (treated like flat_rate)
