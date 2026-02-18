# Work Tracking System - Session History

## Session: February 18, 2026

### Summary
Fixed WorkMarket pay extraction for assigned jobs ("Total budget") and added case-insensitive matching for all WM pay patterns.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Fix WM "Total budget" pay extraction for assigned jobs | Done | Was matching "Total" only; added "Total budget" pattern with `re.IGNORECASE` |

### Technical Notes

**WM Pay Extraction**:
- Assigned/in-progress jobs show `Total budget $277.25` (lowercase b) in Pricing Details
- Old code only matched `Total $XXX` and `Flat Fee $XXX`
- New priority order: `Total` → `Total budget` → `Flat Fee`, all with `re.IGNORECASE`

### Files Modified
- `scraper/workmarket_scraper.py` — pay extraction patterns

---

## Session: February 17, 2026

### Summary
Fixed batch scraper WorkMarket invitation filtering, added pagination support, improved page load timing for detail scraping, added rolling date cutoff, and fixed Field Nation "Total Estimate" pay extraction.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Tighten WM `get_assignment_ids_from_list()` selector | Done | CSS selector targets `#assignment_list_results .results-row` only |
| Add pagination support to WM list scanning | Done | Handles multi-page results via `.wm-pagination` |
| Add list-level date filtering with early cutoff | Done | Skips old assignments before scraping details; stops paginating when all items on page are old |
| Improve WM invitation detection | Done | Visibility checks on buttons, text-based fallback phrases |
| Fix WM detail page load timing | Done | Text stabilization polling replaces static 4s wait |
| Rolling 45-day date cutoff | Done | `SCRAPER_CUTOFF_DAYS` env var in `.bat` file |
| Fix FN "Total Estimate" pay extraction | Done | Regex now matches both "Total" and "Total Estimate" |
| Full batch scrape + import test | Done | All statuses, both platforms, successful import |

### Technical Notes

**WM Invitation Filtering (root cause)**:
- `get_assignment_ids_from_list()` used broad XPath `//a[contains(@href, '/assignments/details/')]` that grabbed ALL links on page
- Fixed with targeted CSS selector: `#assignment_list_results .results-row a[href*='/assignments/details/']`
- Fallback chain: `.assignmentId` divs → `.assignments-content` scoped search
- Accept/Apply button detection improved but was secondary — tighter selector was the real fix

**WM Pagination**:
- Refactored into `_get_ids_from_current_page()` and `get_assignment_ids_from_list()`
- Reads `.wm-pagination[data-max]` to know total pages
- Clicks `.wm-pagination--next` arrow to advance

**List-Level Date Filtering**:
- `_parse_list_date()` parses list page dates like "Jan 26 09:15 AM CST" (infers year)
- Each `.results-row .date` element checked against `min_date`
- Stops paginating when entire page is before cutoff (paid assignments are reverse chronological)

**Page Load Timing Fix**:
- Old: Sequential waits for Schedule (5s) → Checked In (5s) → static 4s sleep
- New: document.readyState → assignment ID in text → content section indicators → text stabilization polling (0.5s intervals until text length stable for 1s)
- Fixed 86% failure rate on WM detail page scraping in batch mode

**Rolling Date Cutoff**:
- Default: `today - 45 days` (was fixed `2025-12-25`)
- Configurable via `SCRAPER_CUTOFF_DAYS` env var in `run_batch_scraper.bat`
- `--min-date` CLI arg still overrides, `--no-date-filter` disables

**FN Pay Extraction**:
- Regex changed from `Total\s*\$?` to `Total(?:\s+Estimate)?\s*\$?`
- Matches "Total $250" (completed) and "Total Estimate $250" (assigned/in-progress)

### Files Modified
- `scraper/workmarket_scraper.py` — selector fix, pagination, date filtering, invitation detection, page load timing
- `scraper/batch_scraper.py` — rolling cutoff, passes min_date to WM scanner
- `scraper/run_batch_scraper.bat` — `SCRAPER_CUTOFF_DAYS` config
- `scraper/fieldnation_scraper.py` — "Total Estimate" pay regex

### Status
- All fixes tested and working
- Full batch scrape + import completed successfully

---

## Session: February 13, 2026

### Summary
Fixed payroll report double-pay bug with entry-level pay calculation, added technician multi-select filter to payroll UI, cleaned up 15 phantom WorkMarket jobs, and started fixing batch scraper invitation detection.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Entry-level pay calculation in payroll report (fixes double-pay across periods) | Done | `cd59ae2` |
| Multi-tech filter for payroll report (backend + frontend) | Done | `cd59ae2` |
| Rename "Job Profit" column to "Profit" | Done | `cd59ae2` |
| Delete 15 phantom WM jobs (invited, not assigned) from database | Done | DB cleanup |
| Add invitation detection to workmarket_scraper.py | Done | local (scraper/) |
| Add invitation filtering to batch_scraper.py | Done | local (scraper/) |

### Technical Notes

**Payroll Report Entry-Level Pay Calculation** (`cd59ae2`):
- **Problem**: `payroll_detail_report()` called `calculate_job_pay(job_id)` which queries ALL time entries for a job regardless of date. If a job spans two pay periods, full pay appeared in BOTH reports.
- **Fix**: Replaced with inline entry-level calculation scoped to the pay period date range:
  - Precomputes `total_job_hours` per job (ALL entries, all time) for ratio calculation
  - `hours_ratio = period_hours / total_job_hours`
  - Prorates billing/expenses/commissions by hours_ratio
  - Applies 50/50 split formula per entry: `tech_pool = max(0, (entry_net - deductions) / 2)`
  - Minimum rate guarantee still applied
  - `calculate_job_pay()` left intact — still used by income/expense report
- **Multi-tech filter**: `tech_id` param now accepts comma-separated IDs (e.g., `tech_id=1,3,5`)
- Frontend adds multi-select dropdown using existing `getTechnicianCheckboxes()`/`initMultiSelect()` pattern

**Database Cleanup**:
- Deleted 15 WM jobs: all had `assigned` or `in_progress` status with 0 time entries
- These were invitation/available assignments picked up by batch scraper
- Job IDs: 139, 146, 104, 105, 140, 137, 131, 113, 135, 141, 143, 145, 147, 142, 144

**Batch Scraper Invitation Fix** (local scraper/ files, NOT YET TESTED):
- Root cause: `get_assignment_ids_from_list()` grabs ALL `/assignments/details/` links on the page, including sidebar/recommended assignments
- Additionally, `scrape_assignment_detail()` with `tab_status` param overrides the actual page status, masking invited jobs as "Active" or "In Progress"
- Fix in `workmarket_scraper.py`:
  - Detects actual page status independently (stored as `page_status`)
  - Checks for Accept/Apply buttons on the detail page (`is_invitation` flag)
  - Prints warning when invitation detected
- Fix in `batch_scraper.py`:
  - After scraping each assignment, checks `is_invitation` flag
  - Skips invitations with log message and count

### Files Modified
- `app/routes/reports.py` - Entry-level pay calculation, multi-tech filter, MileageRateHistory import
- `app/static/js/app.js` - Tech multi-select filter on payroll, renamed Profit column
- `scraper/workmarket_scraper.py` - Invitation detection (Accept/Apply button check, page_status field)
- `scraper/batch_scraper.py` - Skip invitations during scrape

### Status
- Payroll fix deployed and running (`cd59ae2`)
- Batch scraper invitation fix needs testing — user will test next session
- Individual WM scraper confirmed working correctly for Active tab

### Next Steps
- Test batch scraper invitation detection
- If Accept/Apply button detection doesn't work reliably, may need alternative approach (e.g., tightening the link selector in `get_assignment_ids_from_list()`)

---

## Session: February 11, 2026

### Summary
Added WorkMarket "In Progress" tab support, and auto-import to the batch scraper so it imports scraped data automatically without needing a separate `import.bat` run.

### Completed Tasks

| Task | Status | Commit |
|------|--------|--------|
| Add WM "In Progress" tab to workmarket_scraper.py TAB_STATUSES | Done | local (scraper/) |
| Add `--in-progress` CLI arg to batch_scraper.py | Done | local (scraper/) |
| Add `in_progress` to batch scraper WM status_map | Done | local (scraper/) |
| Remove old active-exclusion docstring from scrape_workmarket | Done | local (scraper/) |
| Add auto-import after scraping (reuses import_single_file) | Done | local (scraper/) |
| Add `--no-import` flag to skip auto-import | Done | local (scraper/) |
| Move API_URL check from module-level to main() in import_to_api.py | Done | local (scraper/) |
| Update run_batch_scraper.bat menu with new options | Done | local (scraper/) |

### Technical Notes

**WorkMarket "In Progress" Tab**:
- URL hash: `#status/inprogress/managing`
- Tab text on site says "Assigned" but URL uses `active`; "In Progress" uses `inprogress`
- Both tabs hidden if empty (no assignments in that status)

**Batch Scraper Auto-Import**:
- Imports `import_single_file` from `import_to_api.py`
- Auth now happens for both completed-check and auto-import (not just completed)
- After all scraping, iterates `all_results` and imports each file with `skip_preview=True`
- Files moved to `completed-imports/` on success (existing behavior from import_single_file)
- `--no-import` flag skips auto-import; also skipped if auth fails
- Had to move `sys.exit(1)` API_URL check from module-level to `main()` in import_to_api.py to prevent crash on import

**run_batch_scraper.bat Menu (updated)**:
- Options 1-6: status filters (added 3 for in-progress)
- Options 7-8: platform filters
- Option 9: dry run
- Option S: scrape only (no auto-import)
- Option 0: exit

### Status
- All changes in local `scraper/` directory (gitignored)
- **Needs testing** - user will test tomorrow

### Files Modified
- `scraper/workmarket_scraper.py` - Added 'In Progress' tab
- `scraper/batch_scraper.py` - In-progress support, auto-import, --no-import flag
- `scraper/import_to_api.py` - Moved API_URL guard to main()
- `scraper/run_batch_scraper.bat` - Updated menu

---

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
