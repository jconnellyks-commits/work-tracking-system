# Payout System Design Spec

**Date**: 2026-03-17
**Status**: Approved
**Scope**: Upgrade payroll report to full payout system with locking, adjustments, pay stubs, bonuses/advances/deductions, contractor/employee distinction, and technician self-service.

---

## 1. Overview

Replace the current payroll reporting system with a complete payout management system. The existing payroll report layout and calculation engine are preserved — this upgrade adds pay period management, payout locking with snapshots, post-lock adjustment detection, financial line items (bonuses, deductions, advances), printable pay stubs, and technician self-service.

### Key Principles

- **Snapshot at lock**: When a payout is locked, all calculated amounts are frozen into database records. These snapshots are the source of truth for what was paid.
- **Separation of concerns**: Time entry status (draft→submitted→verified) tracks data accuracy. Payout status (locked→paid) tracks money.
- **Extensible adjustment detection**: Post-lock changes are flagged with a generic `type` field so new triggers require no schema changes.
- **Non-breaking**: Existing ad-hoc date-range reports remain available. All current functionality preserved.

### Terminology Change

"Payroll" is renamed to "Payout" throughout the UI. API routes add new paths but keep old ones as aliases.

---

## 2. Sub-projects & Build Order

| # | Sub-project | Dependencies | Scope |
|---|-------------|-------------|-------|
| 1 | Pay period preferences | None | Settings UI, auto-generation |
| 2 | Contractor vs Employee on Technician | None | New field + badge |
| 3 | Rename Payroll → Payout | None | UI, nav, route aliases |
| 4 | Payout locking & snapshots | #1 | Core payout engine |
| 5 | Post-lock adjustment detection | #4 | Event-driven change tracking |
| 6 | Bonuses, advances, deductions | #4 | Line items + advance balance |
| 7 | Pay stubs | #4, #6 | Printable per-tech view |
| 8 | Technician self-service | #7 | Dashboard + stub history |

Each sub-project gets its own implementation plan and cycle.

---

## 3. Data Model

### 3.1 New Tables

#### Payout Preferences — stored in existing `SystemSettings` table

Instead of a new singleton table, payout preferences use the existing key-value `SystemSettings` model:

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `payout_interval_days` | int | 14 | Biweekly |
| `payout_anchor_date` | date | null | End date of a known period — generates forward/back |
| `payout_auto_generate` | bool | false | Whether to auto-create upcoming periods |

Accessed via the existing `SystemSettings.get(key)` / `SystemSettings.set(key, value)` pattern.

#### `Payout` (one per tech per pay period — created at lock time)

| Column | Type | Notes |
|--------|------|-------|
| payout_id | int PK | |
| period_id | FK → PayPeriod | |
| tech_id | FK → Technician | |
| status | enum | locked / paid |
| total_hours | decimal(10,2) | Snapshot |
| total_base_pay | decimal(10,2) | Snapshot |
| total_mileage_pay | decimal(10,2) | Snapshot |
| total_per_diem | decimal(10,2) | Snapshot |
| total_personal_expenses | decimal(10,2) | Snapshot |
| total_bonuses | decimal(10,2) | Default 0, updated when line items added |
| total_deductions | decimal(10,2) | Default 0, updated when line items added |
| total_advance_repayment | decimal(10,2) | Snapshot |
| net_payout | decimal(10,2) | Recalculated when line items change while locked |
| locked_at | datetime | |
| paid_at | datetime | Nullable |
| paid_by | FK → User | Nullable |
| notes | text | Nullable |

**Status values**: Only `locked` and `paid`. No `draft` state — Payout records are created at lock time with status `locked`. There is no pre-lock payout record.

**net_payout recalculation**: When a `PayoutLineItem` is added or removed while the payout status is `locked`, `total_bonuses`, `total_deductions`, and `net_payout` are recalculated and re-snapshotted. Once status is `paid`, line items cannot be added or removed.

#### `PayoutJobDetail` (snapshot per job per tech per payout)

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| payout_id | FK → Payout | |
| job_id | FK → Job | |
| hours | decimal(10,2) | |
| base_pay | decimal(10,2) | |
| mileage_pay | decimal(10,2) | |
| per_diem | decimal(10,2) | |
| personal_expenses | decimal(10,2) | |
| effective_rate | decimal(10,2) | |
| profit_share | decimal(10,2) | |

#### `PayoutLineItem` (bonuses and deductions)

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| payout_id | FK → Payout | |
| type | enum | bonus / deduction |
| description | text | |
| amount | decimal(10,2) | Always positive, sign determined by type |
| created_by | FK → User | |
| created_at | datetime | |

#### `Advance` (carries balance across periods)

| Column | Type | Notes |
|--------|------|-------|
| advance_id | int PK | |
| tech_id | FK → Technician | |
| description | text | |
| original_amount | decimal(10,2) | |
| remaining_balance | decimal(10,2) | |
| max_per_period | decimal(10,2) | Nullable — null = deduct full balance |
| status | enum | active / repaid / cancelled |
| created_by | FK → User | |
| created_at | datetime | |
| repaid_at | datetime | Nullable |

#### `AdvanceRepayment` (tracks each deduction against an advance)

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| advance_id | FK → Advance | |
| payout_id | FK → Payout | |
| amount | decimal(10,2) | |
| created_at | datetime | |

#### `PayoutAdjustment` (post-lock change detection)

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| payout_id | FK → Payout | |
| type | varchar(50) | Extensible: `billing_changed`, `expense_changed`, `commission_changed`, `entry_added`, `entry_modified`, `entry_deleted` |
| job_id | FK → Job | Nullable |
| entry_id | FK → TimeEntry | Nullable |
| description | text | Human-readable explanation |
| old_value | text | JSON |
| new_value | text | JSON |
| amount_diff | decimal(10,2) | Net dollar impact |
| resolution | enum | pending / carried_forward / dismissed |
| resolved_to_period_id | FK → PayPeriod | Nullable |
| resolved_by | FK → User | Nullable |
| resolved_at | datetime | Nullable |
| created_at | datetime | |

### 3.2 Modified Tables

#### `Technician` — add column:

| Column | Type | Notes |
|--------|------|-------|
| worker_type | varchar(20) | 'employee' / 'contractor', default 'contractor' |

#### `PayPeriod` — add `locked` status to enum

Current status values: `open`, `closed`, `archived`.
New status values: `open`, `locked`, `closed`, `archived`.

**Status transitions**:
- `open` → `locked`: When "Lock Payouts" is clicked (creates Payout snapshots)
- `locked` → `closed`: When all Payout records for the period are `paid`
- `closed` → `archived`: Manual archival (future)

**Deprecation**: The existing `close_pay_period` endpoint (`POST /api/reports/pay-periods/<id>/close`) is deprecated. Closing now happens automatically when all payouts are marked paid. The endpoint remains functional but must be updated to accept both `open` and `locked` as valid input statuses (the existing guard only accepts `open`). It should also log a deprecation warning recommending the new payout workflow instead.

---

## 4. Payout Workflow

### 4.1 Pay Period Lifecycle

```
Configure Preferences (biweekly, anchor date)
        |
Auto-generate periods (or manual create)
        |
Period is "open" — entries flow in, calculations are live
        |
Manager clicks "Lock Payouts"
  - Period status: open → locked
        |
System snapshots all tech pay into Payout + PayoutJobDetail records
  - Calculates advance repayments automatically
  - Payout status: locked
  - total_bonuses and total_deductions start at 0
        |
Manager reviews, adds bonuses/deductions
  - net_payout recalculated on each line item change
        |
Manager clicks "Mark Paid" (per tech or bulk)
  - Payout status: paid → tech can now see their stub
        |
Period auto-closes when ALL payouts are paid
  - Period status: locked → closed
```

### 4.2 Lock Process — Period-Scoped Pay Calculation

When manager clicks "Lock Payouts" on a period:

**Important**: The lock engine must use period-scoped calculations, not `calculate_job_pay()` directly. The existing `payroll_detail_report()` in `reports.py` implements the correct period-scoped proration logic (hours_ratio = tech's period hours / total job hours across all time), including the minimum-rate guarantee floor. The full proration block — from entry grouping through hours ratio calculation, 50/50 split, minimum rate enforcement, and total pay summation — must be extracted into a reusable `calculate_period_pay(period_id)` function in `pay_calculator.py` before the lock engine can use it.

Steps:
1. Extract `calculate_period_pay(period_id)` from the inline logic in `payroll_detail_report()`.
2. For each tech with time entries in the period:
   a. Get their period-scoped pay from `calculate_period_pay()` (already prorated by hours ratio)
   b. Create `Payout` record with snapshot totals, `total_bonuses=0`, `total_deductions=0`
   c. Create `PayoutJobDetail` for each job
   d. Calculate advance repayment:
      - For each active advance for this tech (ordered by `created_at`, oldest first):
      - `repay_amount = min(remaining_balance, max_per_period or remaining_balance)`
      - Cap so net payout doesn't go negative
      - Create `AdvanceRepayment`, update `Advance.remaining_balance`
      - If balance hits zero, set `Advance.status = 'repaid'`
   e. Compute `net_payout` using the canonical formula (see below)
3. Set all payouts to status `locked`
4. Set period status to `locked`

**Canonical `net_payout` formula** (used at lock time and when line items are added/removed):
```
net_payout = total_base_pay + total_mileage_pay + total_per_diem + total_personal_expenses
             + total_bonuses - total_deductions - total_advance_repayment
```
At lock time, `total_bonuses` and `total_deductions` are 0. When a `PayoutLineItem` is added or removed while the payout is `locked`, recalculate `total_bonuses`, `total_deductions`, and `net_payout` using this same formula. This formula is the single source of truth — both the lock engine and the line-item mutation path must use it.

**Advance repayment priority**: Oldest first (`created_at` ascending). This is a known limitation — there is no override mechanism for priority. If urgency is needed, the workaround is to cancel the lower-priority advance and recreate it after the urgent one is repaid.

### 4.3 Post-Lock Adjustment Detection

Triggered when a job or time entry is saved/deleted and the affected period has locked payouts:

1. Identify which `Payout` and `PayoutJobDetail` records are affected
2. Compare changed fields against snapshot values
3. Create `PayoutAdjustment` record with:
   - `type`: what changed (extensible string)
   - `old_value` / `new_value`: JSON of before/after
   - `amount_diff`: calculated dollar impact
   - `resolution`: pending

Detection triggers are hooks in the Job and TimeEntry save/delete paths. New adjustment types are added by adding a new type string — no schema changes needed.

### 4.4 Adjustment Resolution

Manager reviews pending adjustments and for each:

- **Carry forward**: System creates a `PayoutLineItem` (bonus if positive, deduction if negative) on the tech's next open payout period. Links `resolved_to_period_id`.
- **Dismiss**: Sets `resolution = 'dismissed'`, no financial action.

### 4.5 Ad-hoc Reports

The existing date-range payroll report remains available as "Custom Report" — pick any from/to dates and get live calculations without touching the payout system. Useful for one-off contractors or previewing before locking.

---

## 5. API Endpoints

### 5.1 Payout Preferences

- `GET /api/settings/payout-preferences` — get current preferences
- `PUT /api/settings/payout-preferences` — update preferences

These use the existing settings blueprint (`/api/settings/`).

### 5.2 Payouts — new `payouts` blueprint mounted at `/api/payouts/`

Routes are registered with literal paths before parameterized paths to avoid Flask routing conflicts.

- `GET /api/payouts/` — list payouts for a period `?period_id=X`
- `POST /api/payouts/lock` — lock all payouts for a period `{period_id}`
- `POST /api/payouts/pay-all` — mark all locked payouts for a period as paid `{period_id}`
- `GET /api/payouts/<int:id>` — single payout with job details and line items
- `POST /api/payouts/<int:id>/pay` — mark single payout as paid

Note: Using `<int:id>` converter ensures Flask won't match literal paths like `/lock` or `/pay-all` as the `id` parameter.

### 5.3 Line Items

- `POST /api/payouts/<int:id>/line-items` — add bonus or deduction `{type, description, amount}`
- `DELETE /api/payouts/line-items/<int:id>` — remove line item (only if payout is locked, not paid)

Adding/removing a line item triggers recalculation of the parent Payout's `total_bonuses`, `total_deductions`, and `net_payout`.

### 5.4 Advances

- `GET /api/advances/` — list advances `?tech_id=X&status=active`
- `POST /api/advances/` — create advance `{tech_id, description, original_amount, max_per_period}`
- `PUT /api/advances/<int:id>` — update advance (e.g. change max_per_period)
- `POST /api/advances/<int:id>/cancel` — cancel advance

New `advances` blueprint mounted at `/api/advances/`.

### 5.5 Adjustments

- `GET /api/payout-adjustments/` — list adjustments `?period_id=X&resolution=pending`
- `POST /api/payout-adjustments/<int:id>/resolve` — resolve `{resolution, resolved_to_period_id}`

New `payout_adjustments` blueprint mounted at `/api/payout-adjustments/`. Separate from `/api/payouts/` to avoid Flask routing conflicts.

### 5.6 Pay Stubs & Tech Self-Service

- `GET /api/payouts/<int:id>/stub` — full pay stub data for rendering/printing (manager)
- `GET /api/my/payouts` — tech self-service: list their paid payouts
- `GET /api/my/payouts/<int:id>/stub` — tech self-service: view own stub (must be status=paid and belong to the tech)
- `GET /api/my/dashboard` — tech self-service: YTD earnings, last payout, next period

New `my` blueprint mounted at `/api/my/`.

### 5.7 Legacy Aliases

- `GET /api/reports/payroll-detail` — kept on existing `reports` blueprint, unchanged. Works for ad-hoc date-range reports.
- `POST /api/reports/pay-periods/<id>/close` — deprecated, logs warning, still functional.

---

## 6. UI Design

### 6.1 Navigation Rename

- Sidebar: "Payroll" → "Payout"
- All page titles, button labels, headers updated

### 6.2 Payout Preferences (Settings Page)

Added to existing settings page:
- Interval display: "Biweekly (14 days)"
- Anchor date picker
- "Generate Periods" button with count forward/back inputs

### 6.3 Payout Page (replaces Payroll page)

**Top bar:**
- Period selector dropdown (list of pay periods + "Custom Date Range" option)
- Status indicator (open / locked / closed)
- Summary cards: total payout amount, total hours, tech count, pending adjustments count

**Main content (when period selected):**
- Per-tech rows with expandable job detail (same layout as current payroll report)
- Additional columns in tech totals: bonuses, deductions, advance repayment, net payout
- Worker type badge next to tech name

**Action buttons (period level):**
- Lock Payouts (when open)
- Mark All Paid (when locked)

**Action buttons (per tech, when locked):**
- Mark Paid
- Add Bonus
- Add Deduction
- View Stub

**Adjustments tab:**
- List of pending adjustments with: type, job, description, dollar impact
- Carry Forward / Dismiss buttons per adjustment

**Custom Date Range mode:**
- Same as current payroll report — live calculations, no locking

### 6.4 Pay Stub (Printable)

- Header: company info, tech name, worker type badge, period dates
- Job-by-job breakdown table (hours, rate, base pay, mileage, per diem, expenses, total)
- Line items section: bonuses, deductions, advance repayments with descriptions
- Summary: gross pay, total deductions, net payout
- Print-friendly CSS (hide nav, clean margins)

### 6.5 Technician Self-Service

**Dashboard widget (always visible when tech logs in):**
- YTD earnings total
- Last payout amount and date
- Next period end date

**Payout History (new nav item for tech role):**
- Table of paid payouts: period dates, net amount, "View Stub" button
- Only shows payouts with status = "paid"
- Stub view is the same printable layout as the manager sees

### 6.6 Advances Management

Accessible from Settings or Payout page:
- List of advances per tech: original amount, remaining balance, max per period, status
- Create / edit / cancel actions
- Repayment history expandable per advance

---

## 7. Adjustment Detection — Extensible Triggers

Initial trigger types:

| Type | Trigger | Detection |
|------|---------|-----------|
| `billing_changed` | Job.billing_amount updated | Compare against sum of PayoutJobDetail for that job |
| `expense_changed` | Job.expenses updated | Compare against snapshot |
| `commission_changed` | Job.commissions updated | Compare against snapshot |
| `entry_added` | New TimeEntry for a job in locked period | No matching snapshot row |
| `entry_modified` | TimeEntry hours/mileage/etc changed | Compare against snapshot |
| `entry_deleted` | TimeEntry deleted that was in snapshot | Snapshot row with no matching entry |

New types are added by:
1. Adding a detection check in the save/delete hook
2. Using a new type string in `PayoutAdjustment.type`
3. No migration needed

---

## 8. Advance Repayment Logic

When locking payouts for a period:

```
for each active advance for this tech (ordered by created_at, oldest first):
    available = net_payout_before_advances  # don't let it go negative
    cap = advance.max_per_period or advance.remaining_balance
    repay = min(cap, advance.remaining_balance, available)
    if repay > 0:
        create AdvanceRepayment(advance, payout, repay)
        advance.remaining_balance -= repay
        available -= repay
        if advance.remaining_balance == 0:
            advance.status = 'repaid'
            advance.repaid_at = now
```

Default behavior: deduct full remaining balance (up to net pay available).
Override: set `max_per_period` on the advance to cap per-period deductions.
Priority: oldest advance first. No override mechanism — cancel and recreate if urgency changes.

---

## 9. Migration Strategy

- All new tables are additive
- `Technician`: add `worker_type` column with default 'contractor'
- `PayPeriod`: add `locked` to status enum (open/locked/closed/archived)
- Existing `payroll-detail` endpoint preserved unchanged on `reports` blueprint
- Existing `close_pay_period` endpoint deprecated but functional
- Frontend rename is cosmetic — hash routes change but old bookmarks can redirect
- Migrations numbered sequentially after existing 005
- Payout preferences stored in existing `SystemSettings` table (no new table)
