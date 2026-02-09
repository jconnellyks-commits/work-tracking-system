# Work Tracking System - Session History

## Session: February 9, 2026

### Summary
Fixed batch scraper WorkMarket filtering, added public pages for 10DLC campaign registration, and resolved duplicate time entry imports.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Fix batch scraper scraping WorkMarket "all" status (included unassigned tickets) | Done | local (scraper/) |
| Fix WorkMarket navigate_to_tab SPA routing (force reload when already on page) | Done | local (scraper/) |
| Privacy policy page at /privacy | Done | `921b606` |
| SMS terms page at /sms-terms | Done | `921b606` |
| Contact form page at /contact with API submission endpoint | Done | `fa27002` |
| ContactSubmission model + migration 008 | Done | `fa27002` |
| Fix domain references (worktracker → worktracking.sleepybear.tech) | Done | `fa27002` |
| Remove public email addresses, replace with contact form | Done | `fa27002` |
| Normalize time strings in source hash generation | Done | `35ae56a` |
| Add fallback duplicate detection (job_id + date_worked + hours_worked) | Done | `35ae56a` |
| Delete 37 duplicate time entries from Feb 9 re-import | Done | DB cleanup |

### Technical Notes

**Batch Scraper WorkMarket Fix (local scraper/ files)**:
- `--all` mode now excludes `active` for WorkMarket (Active tab includes Available/Applied tickets not assigned to us)
- Use `--active` explicitly to scrape WorkMarket Active tab
- `navigate_to_tab` now forces page reload when already on assignments page (SPA hash navigation fix)
- Verifies URL hash matches expected tab after navigation

**10DLC Campaign Registration**:
- Campaign was rejected with 12 codes (missing privacy policy, opt-in/out/help message issues)
- Created public pages: /privacy, /sms-terms, /contact (no auth required)
- Contact form stores submissions in `contact_submissions` table (migration 008)
- Provided corrected form values for all fields; campaign resubmitted
- Brand: SleepyBear LLC, domain: worktracking.sleepybear.tech
- $15 vetting fee per submission - registration pending

**Duplicate Time Entry Fix**:
- Root cause: source_hash used raw time strings from scraper; formatting differences between runs produced different hashes for the same entry
- Fix 1: `normalize_time_str()` cleans time strings to consistent `HH:MM AM/PM` format before hashing
- Fix 2: Fallback duplicate check on `job_id + date_worked + hours_worked` catches entries with old/missing hashes
- Fix 3: Auto-backfills source_hash on legacy entries when fallback match is found
- Cleaned 37 duplicate entries created by Feb 9 re-import
- 6 remaining "duplicates" confirmed intentional (two techs on same job)

### Files Created
- `app/templates/privacy.html` - Public privacy policy page
- `app/templates/sms_terms.html` - Public SMS terms page
- `app/templates/contact.html` - Public contact form
- `database/migrations/008_add_contact_submissions.sql`

### Files Modified
- `app/routes/frontend.py` - Added /privacy, /sms-terms, /contact routes + /api/contact endpoint
- `app/routes/imports.py` - Normalized hashing, fallback duplicate detection
- `app/models.py` - Added ContactSubmission model
- `scraper/batch_scraper.py` - Exclude WM active from --all, separate wm_statuses
- `scraper/workmarket_scraper.py` - Force reload in navigate_to_tab, URL verification
- `scraper/run_batch_scraper.bat` - Updated menu text

---

## Session: February 4, 2026 (Continued)

### Summary
Implemented job assignment system with SMS notifications via Sangoma/Apidaze API.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Database migration 007 (job_assignments, sms_notifications tables) | Done | `c2cb915` |
| JobAssignment and SMSNotification SQLAlchemy models | Done | `c2cb915` |
| SMS service with Apidaze API integration | Done | `c2cb915` |
| Assignments API routes (assign, remove, resend SMS) | Done | `c2cb915` |
| "Assign Technicians" modal with multi-select | Done | `c2cb915` |
| "Assigned Technicians" section in job details | Done | `c2cb915` |
| "My Assigned Jobs" section on technician dashboard | Done | `c2cb915` |
| SMS settings configuration in admin settings page | Done | `c2cb915` |

### Technical Notes

**Job Assignment System**:
- Admins/managers can assign technicians to jobs
- Assignments tracked with status (invited/accepted/declined/expired/cancelled)
- Primary technician flag for multi-tech jobs
- SMS notification sent on assignment (optional)
- SMS delivery status tracked per assignment

**SMS Service (`app/utils/sms_service.py`)**:
- Integrates with Sangoma/Apidaze API
- Phone number formatting to E.164
- Message truncation to 160 chars for single SMS
- All SMS logged to `sms_notifications` table
- Configuration stored in SystemSettings

**Assignment API Endpoints**:
- `GET /api/assignments/job/<id>` - Get job's assignments
- `GET /api/assignments/technician/<id>` - Get tech's assignments
- `GET /api/assignments/my-jobs` - Current user's assigned jobs
- `POST /api/assignments/job/<id>` - Assign techs (with SMS option)
- `DELETE /api/assignments/<id>` - Remove assignment
- `POST /api/assignments/<id>/resend-sms` - Resend SMS
- `GET /api/assignments/sms-status` - Check SMS config

**Frontend Features**:
- Jobs list: "Assign" button for managers
- Job details: Shows assigned techs with remove/resend buttons
- Dashboard: "My Assigned Jobs" for technicians
- Settings: SMS configuration (API key, secret, from number)

### Files Created
- `database/migrations/007_add_job_assignments.sql`
- `app/routes/assignments.py`
- `app/utils/sms_service.py`

### Files Modified
- `app/models.py` - Added JobAssignment, SMSNotification models
- `app/__init__.py` - Registered assignments blueprint
- `app/routes/settings.py` - SMS settings endpoints
- `app/static/js/api.js` - Assignment and SMS API methods
- `app/static/js/app.js` - Assignment UI, dashboard, settings page

### Deployment Notes
- Installed `requests` module on server
- Ran migration 007 to create tables

---

## Session: February 4, 2026

### Summary
Added projected income feature to income/expense report.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Mark future jobs as projected in income/expense report | Done | `6f1b491` |

### Technical Notes

**Projected Income Feature**:
- Jobs with `job_date > today` are flagged as `is_projected`
- Projected jobs excluded from net profit calculation
- Summary shows actual counts/income with projected amounts in parentheses
- Table rows have yellow background and "PROJECTED" badge for future jobs
- Projected jobs show "-" for expenses/commissions/tech pay/profit columns
- Chart excludes projected jobs from daily profit/expense calculations

### Files Modified
- `app/routes/reports.py` - Added is_projected flag and separate projected totals
- `app/static/js/app.js` - Updated summary, table rows, and chart for projected display

---

## Session: February 3, 2026

### Summary
Built unified batch scraper for Field Nation and WorkMarket with smart completed detection.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Batch scraper script (`batch_scraper.py`) | Done | - |
| API endpoint for checking existing completed jobs | Done | `33b968a` |
| Date filter to skip jobs before Dec 25, 2025 | Done | - |
| Batch file launcher (`run_batch_scraper.bat`) | Done | - |
| Test completed scrape with both platforms | Done | - |

### Technical Notes

**Batch Scraper (`scraper/batch_scraper.py`)**:
- Unified script that runs both Field Nation and WorkMarket scrapers
- Imports scraper classes directly, no subprocess/stdin automation
- Uses same credentials file as `import_to_api.py` (JSON format)
- Connects to existing browser sessions (ports 9222/9223)

**Smart Completed Detection**:
- New endpoint: `POST /api/imports/check-existing`
- Accepts platform + list of IDs, returns which are already completed
- Only skips jobs with `job_status = 'completed'` in DB
- Jobs that exist with other statuses are still scraped (to update them)
- Prevents redundant scraping of already-processed completed work

**Date Filter**:
- Constant `MIN_JOB_DATE = date(2025, 12, 25)`
- Applied after scraping, before saving (needs detail page for date)
- Filters based on `scheduled_date` or first time entry date
- Command line options: `--min-date YYYY-MM-DD` or `--no-date-filter`

**Command Line Options**:
```
python batch_scraper.py --all              # All statuses
python batch_scraper.py --completed        # Just completed/paid
python batch_scraper.py --active --pending # Specific statuses
python batch_scraper.py --fn-only          # Field Nation only
python batch_scraper.py --wm-only          # WorkMarket only
python batch_scraper.py --dry-run          # Preview mode
```

**Status Mapping**:
| Status | Field Nation Tab | WorkMarket Tab |
|--------|-----------------|----------------|
| active | Assigned | Active |
| pending | Pending | Pending Approval |
| invoiced | (skipped) | Invoiced |
| completed | Completed | Paid |

**Test Results (Feb 3)**:
- Field Nation: 25 on Completed tab → 12 skipped (already done) → 13 scraped → 7 after date filter
- WorkMarket: 25 on Paid tab → 0 skipped → 25 scraped → 22 after date filter
- Import: All jobs were updates (existed with other status), time entries skipped as duplicates

### Files Created
- `scraper/batch_scraper.py` - Unified batch scraper
- `scraper/run_batch_scraper.bat` - Windows launcher with menu

### Files Modified
- `app/routes/imports.py` - Added `/check-existing` endpoint

### Next Steps
- Run batch scraper daily to keep completed jobs in sync
- Monitor for edge cases with date extraction

---

## Session: February 2, 2026 (Continued)

### Summary
Backup/restore system, scraper fixes, database cleanup, and multi-select filters.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Database backup/restore system from GUI | Done | (earlier) |
| Safe Mode feature (snapshot before changes) | Done | (earlier) |
| Fix backup permissions (www-data ownership) | Done | - |
| Fix MySQL binary paths for backup/restore | Done | `e1cb326` |
| Fix WorkMarket scraper scheduled date extraction | Done | - |
| Remove unused "FieldNation" platform from database | Done | - |
| Multi-select filters for status and technician | Done | `d207c20` |
| Ticket number links to external URL in job details popup | Done | `7acbf1e` |
| Source hash for import duplicate detection | Done | `efe466d` |
| Backfill existing 129 imported entries with hashes | Done | - |
| Database cleanup - remove old entries/jobs before Dec 25, 2025 | Done | - |
| Fix platform summary billing totals (was counting per time entry) | Done | `5c56af2` |
| Add daily chart to income/expense report | Done | `a5d02b0` |
| Fix Chart.js loading (CSP blocking CDN) | Done | `a9a60f8` |
| Show all days in chart, not just days with jobs | Done | `0d46c24` |
| Fix JWT token expiry (.env was overriding to 1 hour) | Done | - |

### Technical Notes

**Backup/Restore System**:
- Backups stored in `/opt/work-tracking/backups/`
- Uses mysqldump/mysql CLI tools with full paths (shutil.which + common locations)
- Directory must be owned by www-data (Gunicorn user)
- Safe Mode: creates snapshot, work freely, then commit or revert

**WorkMarket Scraper Date Fix**:
- Was incorrectly using "Confirmed on" date (job acceptance date) as scheduled date
- Now prioritizes Schedule section dates
- Looks for dates BEFORE "Checked In" section to avoid check-in/out dates
- Falls back to earliest time entry date if no schedule found
- Added Pattern 5: day-of-week date followed by time with timezone (for unconfirmed assignments)
  - Format: `Fri, 02/27/2026\n9:00 AM CST` - handles active assignments not yet confirmed

**Multi-Select Filters**:
- Status and technician filters on time entries now support multiple selections
- Custom checkbox dropdown component (`.multi-select` CSS class)
- Backend accepts comma-separated values for `status` and `tech_id` params
- Can select "Unassigned" together with specific technicians

**Source Hash Duplicate Detection**:
- New `source_hash` column on time_entries (migration 006)
- Hash format: `{platform}:{external_id}:{date}:{time_in}:{time_out}` (SHA256, 32 chars)
- Prevents duplicate imports even when hours are split between technicians
- Backfill endpoint at `POST /api/imports/backfill-hashes`
- 129 existing imported entries backfilled with hashes

**Database Cleanup**:
- Removed 58 time entries before Dec 25, 2025
- Removed 28 jobs before Dec 25, 2025 with no recent entries

**Platform Summary Fix**:
- Billing was being summed once per time entry instead of once per job
- Fixed by using subqueries to aggregate jobs and hours separately
- Totals now match income/expense report

**Income/Expense Chart**:
- Added Chart.js via CDN (jsdelivr)
- Updated CSP to allow cdn.jsdelivr.net and cdnjs.cloudflare.com
- Daily bar chart: income (green), expenses (red), profit (blue line)
- Shows all days in date range, not just days with jobs

**JWT Token Fix**:
- Server .env had `JWT_ACCESS_TOKEN_EXPIRES=3600` (1 hour) overriding the 3-day default
- Changed to `JWT_ACCESS_TOKEN_EXPIRES=259200` (3 days)
- This was causing frequent logouts

### Files Modified
- `app/__init__.py` - CSP updated to allow Chart.js CDN
- `app/routes/settings.py` - MySQL binary path detection
- `app/routes/time_entries.py` - Multi-value status/tech_id filtering
- `app/routes/reports.py` - Platform summary fix (subqueries)
- `app/routes/imports.py` - Source hash generation and duplicate detection
- `app/models.py` - Added source_hash field to TimeEntry
- `app/static/js/app.js` - Multi-select, chart, ticket link in job popup
- `app/static/css/style.css` - Multi-select dropdown styles
- `app/templates/index.html` - Added Chart.js script
- `scraper/workmarket_scraper.py` - Scheduled date extraction fix
- `database/migrations/006_add_source_hash.sql` - New migration
- Server `.env` - Fixed JWT_ACCESS_TOKEN_EXPIRES (1hr → 3 days)

---

## Session: February 2, 2026

### Summary
UI improvements for time entries, authentication/error handling fixes, pay periods management, and report enhancements.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Add mileage column to time entries list and grouped views | Done | `57a452a` |
| Add job search filter to time entries screen | Done | `eb6ae85` |
| Auto-calculate hours when editing time entries | Done | `a4ead8e` |
| Show average rate in payroll report technician totals | Done | `97c8f78` |
| Increase auth token timeout to 3 days | Done | `94b961b` |
| Fix auth timeout - redirect to login on any 401 | Done | `94b961b` |
| Keep forms open on save errors with inline error display | Done | `94b961b` |
| Pay periods management page (#pay-periods) | Done | `8b06c1e` |
| Payroll report quick-fill buttons for last 2 pay periods | Done | `8b06c1e` |
| Generate recurring pay periods endpoint | Done | `8b06c1e` |
| Platform summary date range filter | Done | `9113e4c` |
| Platform summary totals row | Done | `0fe3e89` |

### Technical Notes

**Time Entries Improvements**:
- Mileage column added to both list view and grouped-by-job view
- Job search filter searches by ticket number or client name
- Works in both list and grouped views with debounced input

**Hours Auto-Calculation**:
- Frontend: calculates hours when time_in or time_out changes
- Backend: calculates hours if hours_worked is empty but times provided
- Handles overnight shifts (e.g., 10 PM to 6 AM)

**Auth & Error Handling**:
- Token expiry increased from 1 hour to 3 days (internal app)
- Any 401 error now clears tokens and redirects to login
- New `App.showFormError()` displays errors inline in modals
- Forms stay open on errors so users can fix and retry

**Pay Periods**:
- New page at #pay-periods for managing pay periods
- Generate recurring periods with configurable anchor date and length
- Default: bi-weekly (14 days), starts Thursday, ends Wednesday
- Anchor date: January 21, 2026
- Auto-assigns time entries to matching periods on generation
- Quick-fill buttons on payroll report for last 2 periods
- Periods can be closed (prevents edits) or deleted

**Platform Summary**:
- Added date range filter (defaults to current month)
- "All Time" button to show without date filter
- Totals row showing sum of jobs, billing, and hours

### Files Modified
- `app/static/js/app.js` - All UI changes
- `app/static/js/api.js` - Auth handling, pay period API methods
- `app/routes/time_entries.py` - job_search param, hours calc fix
- `app/routes/reports.py` - Generate/delete pay periods endpoints
- `app/config.py` - Token timeout to 3 days

---

## Session: January 29, 2026 (Continued)

### Summary
Continued from previous session that ran out of context. Completed job dropdown filter feature and various bug fixes.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Job dropdown filter - show only open jobs by default | Done | `2d0403e` |
| Delete buttons for time entries (managers any, techs draft only) | Done | `684345c` |
| Delete buttons for jobs (managers only) | Done | `684345c` |
| Sortable columns on time entries (date, hours, status) | Done | `684345c` |
| Fix delete/copy buttons in grouped time entries view | Done | `d77be2e`, `c1e6000` |
| Fix timezone bug - dates showing one day off | Done | `5614710` |
| Update job_date on re-import (was only updating status/billing) | Done | `ad28047` |

### Earlier Session Work (Jan 29, 2026)

| Task | Status |
|------|--------|
| WorkMarket scraper - scheduled date extraction | Done |
| WorkMarket scraper - fix Invoiced/Pending Approval tab mappings (were reversed) | Done |
| WorkMarket scraper - handle `(edit)` text in check-in/out times | Done |
| Field Nation scraper - add debug mode (option 5) | Done |
| Field Nation scraper - scheduled date extraction (multiple formats) | Done |
| Field Nation scraper - fix false time entries (exclude file upload timestamps, estimated duration) | Done |

### Technical Notes

**Job Dropdown Filter Implementation**:
- Applied to both `editEntry` and `copyEntry` functions in `app.js`
- Default shows: pending, assigned, in_progress jobs
- Checkbox toggles visibility of completed jobs
- Current job always visible when editing/copying
- Completed jobs tagged with `[Completed]` when shown
- Future consideration: server-side search when job count exceeds ~500

**Timezone Fix**:
- `formatDate()` was parsing `YYYY-MM-DD` as UTC, causing dates to shift back one day
- Fixed by explicitly parsing as local date: `new Date(year, month - 1, day)`

**Scraper Date Extraction Patterns**:
- WorkMarket: `Tue, 02/3/2026 to Tue, 02/3/2026` with time on separate line
- Field Nation: Multiple formats including `Tue, Feb 24, 2026`, `1/30/2026, 9:00 AM → 5:00 PM`, arrival window format

### Files Modified
- `app/static/js/app.js` - Job dropdown filter, delete buttons, sorting, timezone fix
- `app/routes/time_entries.py` - Sort parameters
- `app/routes/imports.py` - job_date update on re-import
- `scraper/workmarket_scraper.py` - Date extraction, time entry parsing fixes
- `scraper/fieldnation_scraper.py` - Debug mode, date extraction, false entry fixes

### Next Steps
- Test job dropdown filter in production
- Monitor for any edge cases with scraper date extraction
- Consider server-side job search if performance degrades with large job counts

---

## Previous Sessions

### January 28, 2026
- WorkMarket scraper implementation
- WorkMarket import endpoints
- Separate Chrome profile for WorkMarket (port 9223)

### January 23, 2026
- Security hardening (rate limiting, security headers, CORS)
- Removed CLAUDE.md from git (local only)

### Earlier January 2026
- Field Nation scraper with persistent browser session
- Import API with status mapping
- Unassigned time entries workflow
- Grouped by job view for time entries
- Pay calculation system with 50% tech pool formula
