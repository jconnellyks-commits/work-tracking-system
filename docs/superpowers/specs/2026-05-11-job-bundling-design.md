# Job Bundling Design Spec

## Problem

Multiple related jobs at the same site (sometimes with multiple technicians) make pay calculation difficult because each job gets its own independent billing/expenses/commissions and tech pool. Similarly, routes of repeating jobs at different sites completed by a single tech have expenses like mileage unfairly concentrated on individual jobs rather than spread across the combined work.

## Solution

Introduce a `JobBundle` entity that groups related jobs. Bundled jobs pool their financials for pay calculation, producing fairer pay distribution. Time entries can be logged against either a specific job or the bundle directly.

## Data Model

### New Table: `job_bundles`

| Column | Type | Notes |
|--------|------|-------|
| `bundle_id` | INT PK AUTO_INCREMENT | |
| `name` | VARCHAR(255) NULL | If null, display as `"{first job description} Bundle"` |
| `status` | ENUM('active','closed') | Default 'active' |
| `created_by` | INT FK -> users.user_id | |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Modified: `jobs`

- Add `bundle_id` INT NULL FK -> `job_bundles.bundle_id`

### Modified: `time_entries`

- Add `bundle_id` INT NULL FK -> `job_bundles.bundle_id`
- Change `job_id` to nullable

### Constraints

- A time entry must have at least one of `job_id` or `bundle_id` set. Enforced at the application layer (not a DB CHECK constraint) since MySQL 5.x support varies.
- A job can belong to at most one bundle.
- If a time entry has `job_id` set and that job belongs to a bundle, the entry is implicitly part of the bundle for pay calculation.
- Existing time entries all have `job_id` set and remain valid after the migration.

## Pay Calculation

### `calculate_bundle_pay(bundle_id)`

Pools financials from all jobs in the bundle:

- `billing_amount` = sum of all jobs' billing
- `expenses` = sum of all jobs' expenses
- `commissions` = sum of all jobs' commissions
- `job_net` = pooled billing - pooled expenses - pooled commissions

Time entries gathered from:
1. All entries on jobs within the bundle (via `job_id`)
2. All entries directly on the bundle (via `bundle_id`)

Then the existing formula applies against pooled numbers:
- Total deductions = all mileage pay + per diem + personal expenses across all techs
- Tech pool = (job_net - total_deductions) / 2
- Weighted distribution by `min_pay * hours` for multi-tech
- Minimum rate enforcement per tech

### Changes to `calculate_period_pay`

When building the `job_tech_entries` map, bundled jobs get merged into a single virtual entry keyed by `bundle:<bundle_id>`. Bundle-level time entries (those with only `bundle_id`) also get folded in. The rest of the per-job loop runs unchanged -- it sees the bundle as one unit with pooled financials.

Unbundled jobs continue working exactly as they do today.

## API Endpoints

### Bundle CRUD

- `GET /api/bundles` -- list bundles (filterable by status)
- `POST /api/bundles` -- create bundle `{name?, job_ids: [...]}`
- `GET /api/bundles/<id>` -- get bundle with its jobs
- `PUT /api/bundles/<id>` -- update name/status
- `DELETE /api/bundles/<id>` -- remove bundle (unlinks jobs, doesn't delete them)

### Bundle Membership

- `POST /api/bundles/<id>/jobs` -- add jobs `{job_ids: [...]}`
- `DELETE /api/bundles/<id>/jobs/<job_id>` -- remove a job from bundle

### Bundle Pay

- `GET /api/bundles/<id>/pay` -- calculate pooled pay (mirrors `calculate_job_pay` response shape)

### Time Entry Changes

- Existing `POST /api/time-entries` gets an optional `bundle_id` field
- If `bundle_id` is set without `job_id`, that's valid (entry against the bundle)
- If `job_id` is set, `bundle_id` is optional (inferred from job's bundle membership)

## Frontend

### Jobs Page

- "Create Bundle" button opens a modal to name the bundle and select jobs (multi-select)
- Jobs that belong to a bundle show a bundle icon/badge with the bundle name
- Clicking the badge opens the bundle detail modal (member jobs, pooled financials summary)
- "Add to Bundle" action in job actions dropdown (pick existing bundle or create new)
- "Remove from Bundle" action for bundled jobs

### Time Entries

- Create/edit entry form gets a "Bundle" dropdown alongside the existing "Job" dropdown
- Selecting a bundle clears the job requirement; selecting a job clears the bundle (or both can be set)
- Time entries logged against a bundle (no specific job) show the bundle name in the list

### Reports (Payroll, Income/Expense)

- Individual job rows still appear for bundled jobs
- Bundled jobs get a visual indicator (indented under a bundle header row showing bundle name and pooled totals)
- Bundle-level time entries appear under the bundle header

### Bundle Management

- No separate page -- managed from the jobs page via modals and job actions menu
- Bundle detail modal shows: name, member jobs with financials, pooled totals, "Calculate Pay" breakdown

## Migration

Single migration file adding:
1. `job_bundles` table
2. `bundle_id` column on `jobs`
3. `bundle_id` column on `time_entries`
4. Make `job_id` nullable on `time_entries`
