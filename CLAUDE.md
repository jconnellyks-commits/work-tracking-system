# Work Tracking System - Project Context

## TODO - Next Session
- [ ] Apply Period 12 payout adjustments (exact deltas need recalculation — see memory)
- [ ] SMS notifications for technicians  ← NEXT
- [x] Hourly billing auto-calculation + reimbursable line items (Apr 18, 2026)
- [x] Fix multi-tech pay calculation — shared-pool weighted formula (Apr 14, 2026)
- [x] Per-entry rows in payroll report/payout views (Apr 14, 2026)
- [x] Calendar view for assigned jobs
- [x] Scheduled start time on jobs (scrapers extract it, shows on calendar chips + job modal)
- [x] Update scraper batch files to use worktracking.sleepybear.tech + SSL=true
- [x] Automate entry for TechLink (email parser service — deployed, needs live test)
- [x] Automate entry for Tech Service Today (email parser service — deployed, needs live test)
- [x] Fix timezone bug — reports/dashboard showing wrong day after 6 PM (uses configurable timezone now)
- [ ] Time entries interface adjustments
- [ ] Audit code

## Future Enhancements to Review
- **Job Dropdown Performance**: Current implementation filters completed jobs by default in time entry forms (editEntry, copyEntry). As job count grows, may need to switch to server-side pagination/search for the job dropdown. Monitor performance when job count exceeds ~500.

## Overview
Flask-based work tracking and timesheet system for managing technician time entries, job billing, and payroll calculations.

## Tech Stack
- **Backend**: Flask + SQLAlchemy
- **Database**: MySQL (`work_tracking_db`)
- **Frontend**: Vanilla JavaScript (single-page app)
- **Server**: GCP Compute Engine with Gunicorn + systemd

## Server Access
- **URL**: https://worktracking.sleepybear.tech (SSL cert, valid domain)
- **IP**: 34.27.146.58
- **SSH Key**: `~/.ssh/gcp_work_tracking`
- **SSH Command**: `ssh -i "$HOME/.ssh/gcp_work_tracking" claude-code@34.27.146.58`
- **App Directory**: `/opt/work-tracking`
- **Service**: `work-tracking` (systemd)
- **Restart**: `sudo systemctl restart work-tracking`

## Deployment
```bash
# From local Windows machine:
git push origin main
ssh -i "$HOME/.ssh/gcp_work_tracking" claude-code@34.27.146.58 "cd /opt/work-tracking && sudo git pull && sudo systemctl restart work-tracking"
```

## Database
- **User**: `work_tracking`
- **Password**: stored in `/opt/work-tracking/.env` on server
- **Migrations**: `database/migrations/` directory (run manually with mysql client)

## Key Directories
```
app/
  routes/          # API endpoints
    auth.py        # Authentication, user management
    jobs.py        # Job CRUD
    time_entries.py # Time entry CRUD, submit/verify workflow
    technicians.py # Technician management
    reports.py     # Payroll, income/expense, dashboard reports
    settings.py    # System settings, mileage rates
  models.py        # SQLAlchemy models
  static/
    js/
      app.js       # Main frontend application
      api.js       # API client
    css/
      style.css    # All styles
  templates/       # HTML templates (login.html, index.html)
  utils/
    pay_calculator.py  # Pay calculation logic
    auth.py            # JWT auth utilities
    logging.py         # Logging and audit utilities
```

## Pay Calculation System
- 50% tech pool formula: `(billing - expenses - commissions) * 0.5`
- Weighted distribution by hours worked
- Minimum pay rate per technician (stored as `hourly_rate` on technician)
- Uses higher of: calculated rate vs minimum rate
- Adds: mileage pay, per diem, personal expenses

## Key Features
- **Time Entries**: Draft -> Submitted -> Verified -> Billed -> Paid workflow
- **Jobs**: Track billing, expenses, commissions, external platform URLs
- **Payroll Report**: Per-technician breakdown with job details, pay calculation, profit share
- **Income/Expense Report**: Job profitability analysis
- **Profit Share**: Proportional to technician's hours vs total job hours
- **Technician Management**: Create technicians, link to user accounts
- **Mileage Rate History**: Track IRS rates over time

## Recent Work (Jan 2026)
1. Added financial fields (mileage, per_diem, personal_expenses for entries; expenses, commissions for jobs)
2. Built pay calculation system with 50% tech pool formula
3. Added mileage rate history tracking
4. Rebuilt payroll reports with per-technician job breakdowns
5. Added external URL field to jobs for linking to platform pages
6. Added print and CSV export to payroll report
7. Replaced job billing report with income/expense report
8. Added profit column showing each tech's proportional share based on hours ratio
9. Added total profit share to technician totals row
10. Made tech_id nullable for imported/scraped time entries
11. Built Field Nation scraper (Selenium) with browser automation
12. Created import API endpoint with status mapping and job updates
13. Import now updates existing jobs (status, billing) on re-import
14. Added job_ticket, job_title, job_client to TimeEntry.to_dict()
15. Added "Group by Job" view for time entries with collapsible job cards
16. Frontend time entries table now shows job ticket and client instead of just ID
17. Added persistent browser session for scraper (no repeated logins)
18. Added debug mode to scraper for troubleshooting extraction issues
19. Fixed time entry extraction - timezone suffix handling `(CST)`, `(EST)`
20. Fixed "Time Log" vs "Time Logged" section matching bug
21. Added multiple extraction patterns for different Field Nation page formats
22. Added datetime range with arrow pattern for side-by-side time display
23. Fixed tab navigation - robust selectors, waits for content to load
24. Changed "In Progress" to "Pending" (correct Field Nation tab name)
25. Added browser reconnection via Chrome remote debugging port 9222
26. Fast socket check (2s) to detect existing browser before connection attempt
27. Security hardening (Jan 23, 2026):
    - Removed CLAUDE.md from git (local only now, added to .gitignore)
    - Made scraper API_URL required (no hardcoded fallback)
    - Made SSL verification configurable in scraper (defaults to enabled)
    - Added configurable CORS origins (defaults to same-origin only)
    - Added rate limiting to sensitive auth endpoints (refresh, register, password reset)
    - Added security headers: X-Frame-Options, X-Content-Type-Options, CSP, HSTS, etc.
    - CSP allows 'unsafe-inline' for scripts/styles (required for vanilla JS frontend)
28. WorkMarket scraper implementation (Jan 28, 2026):
    - Created `workmarket_recon.py` for capturing page structure
    - Created `workmarket_scraper.py` with persistent session (port 9223)
    - Added WorkMarket import endpoints to API (`/api/imports/workmarket`)
    - Updated `import_to_api.py` to support both Field Nation and WorkMarket
    - Added status mapping for WorkMarket statuses
    - Separate Chrome profile to run both scrapers simultaneously
29. Batch scraper enhancements (Feb 2026):
    - Added WorkMarket "In Progress" tab (`inprogress` URL hash)
    - Added auto-import after scraping (uses `import_single_file` from import_to_api.py)
    - `--no-import` flag to skip auto-import
    - `--in-progress` flag for WM In Progress tab
    - Moved `sys.exit(1)` API_URL check from module-level to `main()` in import_to_api.py

## Unassigned Time Entries
- Time entries can now be created without a technician (for scraped/imported data)
- Managers can filter by "Unassigned" in the time entries list
- "Assign" button appears for unassigned entries
- Submission blocked until technician is assigned
- Workflow: Import -> Review -> Assign Technician -> Submit -> Verify

## Field Nation Scraper
The `scraper/` folder (gitignored) contains tools for scraping Field Nation:
- `fieldnation_scraper.py` - Selenium-based scraper with persistent session
- `import_to_api.py` - Imports scraped JSON to the work tracking API (handles both FN and WM)
- `import.bat` - Windows batch file to run the importer (handles both platforms)
- `run_scraper.bat` - Windows batch file to run the scraper
- `chrome_profile/` - Persistent Chrome profile (cookies/session saved here)

**Importer Features**:
- Auto-detects source from filename (`workmarket_*` → WorkMarket, else → Field Nation)
- Saves credentials to `.importer_credentials` for reuse
- Moves imported files to `output/completed-imports/` after success
- Accepts 'y' or 'yes' for confirmations

**Importer Configuration** (in `import.bat`):
```batch
set API_URL=https://your-server/api      # Required - no default
set API_VERIFY_SSL=false                  # Set to 'false' for self-signed certs only
```

**Persistent Session & Browser Reconnection:**
- Browser profile saved in `scraper/chrome_profile/`
- First run: Log in and complete 2FA manually
- Subsequent runs: Automatically logged in (session restored)
- No need to re-authenticate each time!
- **Browser stays open** (option 6): Uses Chrome remote debugging on port 9222
- **Reconnection**: If browser is still open from previous run, script connects to it instead of opening a new window
- Fast 2-second socket check detects if browser is running before attempting connection

**Scraper Menu:**
```
1. Scrape Completed work orders
2. Scrape Assigned work orders
3. Scrape Pending work orders
4. Scrape a specific work order by ID
5. Debug a single work order (verbose output)
6. Exit (browser stays open)
7. Exit and close browser
```

**Workflow:**
1. Run `run_scraper.bat` - browser opens with saved session
2. If first run, log in manually (session saved for next time)
3. Choose what to scrape from menu (can do multiple in one session)
4. JSON saved to `scraper/output/` with timestamps
5. Run `import_to_api.bat` to push data to work tracking system
6. Imported entries appear as "Unassigned" for technician assignment

**Tab Navigation:**
- Scraper navigates between Field Nation tabs: Completed, Assigned, Pending
- Note: Field Nation uses "Pending" not "In Progress" for the tab name
- Tab clicking uses multiple XPath selectors for robustness
- Waits for content to actually change after clicking (up to 15 seconds)
- Tracks work order IDs before/after to detect when new tab content loads
- Falls back to JavaScript click if normal click fails

**Debug Mode (Option 5):**
- Scrapes a single work order with verbose output
- Saves page text to `scraper/output/debug_{wo_id}.txt`
- Shows exactly what patterns are matching/failing
- Use this when time entries aren't being extracted correctly

**Time Entry Extraction Patterns:**
The scraper uses multiple patterns to extract time entries from Field Nation pages:

1. **Pattern 1 - Arrow format with hours prefix:**
   `3.83 hours 1/7/2026 at 2:56 PM → 1/7/2026 at 6:46 PM`

2. **Pattern 2 - Time Log section (most common):**
   - Looks for "Time Log\n" section (NOT "Time Logged" which appears elsewhere)
   - First tries datetime range with arrow: `10/27/2025 at 9:02 AM (CST) → 10/27/2025 at 12:02 PM (CST)`
   - Falls back to separate datetime pairs on individual lines
   - Handles timezone suffixes like `(CST)`, `(EST)`

3. **Pattern 3 - Check-in/Check-out from Tasks:**
   Extracts times from "Check in" and "Check out" task completions

4. **Pattern 4 - Fallback:**
   Uses any datetime pairs found and pairs with hours mentions

**Key Extraction Lessons:**
- "Time Log\n" (with newline) is the actual section header
- "Time Logged" appears elsewhere on the page - don't match it!
- Timezone format varies: `3:15 PM(CST)` or `3:15 PM (CST)` (with/without space)
- Visual layout differs from extracted text (arrows may appear on same line visually but separate lines in text)

**Status Mapping (Field Nation → Internal):**
- Published, Routed, Requested → `pending`
- Assigned, Confirmed, Scheduled → `assigned`
- Pending, On My Way, Checked In, Work Done → `in_progress`
- Approved, Paid → `completed`
- Cancelled → `cancelled`

**Field Nation Tab Names:**
- Completed, Assigned, Pending (not "In Progress")

**Re-import Behavior:**
- Jobs matched by external_url or ticket_number containing work order ID
- Existing jobs: status and billing_amount are UPDATED (not skipped)
- Time entries: duplicates detected by job_id + date_worked + hours_worked
- New time entries added to existing jobs (incremental import supported)

**API Endpoints:**
- `POST /api/imports/fieldnation` - Import scraped data (creates/updates jobs, adds time entries)
- `POST /api/imports/fieldnation/preview` - Preview without importing

## WorkMarket Scraper
The `scraper/` folder also contains tools for scraping WorkMarket:
- `workmarket_recon.py` - Recon tool to capture page structure
- `workmarket_scraper.py` - Selenium-based scraper with persistent session
- `run_workmarket_recon.bat` - Windows batch file to run recon tool
- `run_workmarket_scraper.bat` - Windows batch file to run the scraper
- `chrome_profile_workmarket/` - Separate Chrome profile for WorkMarket (port 9223)
- Use `import.bat` to import (same as Field Nation - auto-detects from filename)

**WorkMarket URL Patterns:**
- List pages: `https://www.workmarket.com/assignments#status/{status}/managing`
- Detail pages: `https://www.workmarket.com/assignments/details/{assignment_id}`
- Status values: `paid`, `paymentPending` (Invoiced), `complete` (Pending Approval), `active` (Assigned), `inprogress` (In Progress), `available`, `applied`

**WorkMarket vs Field Nation:**
- Uses separate Chrome profile (`chrome_profile_workmarket/`)
- Uses different debugger port (9223 vs 9222)
- Both scrapers can run simultaneously with separate browser sessions

**Scraper Menu:**
```
1. Scrape Paid assignments
2. Scrape Invoiced assignments
3. Scrape Pending Approval assignments
4. Scrape a specific assignment by ID
5. Debug a single assignment (verbose output)
6. Exit (browser stays open)
7. Exit and close browser
```

**Time Entry Extraction:**
- Primary: "Checked In Checked Out" section
- Format: `01/02/2026 at 03:40pm CST 01/02/2026 at 05:47pm CST`
- Fallback: "Estimated Time Spent: 0d 2h 6m"
- Hours calculated from check-in/out times

**Status Mapping (WorkMarket → Internal):**
- Available, Applied → `pending`
- Active, Assigned, Confirmed → `assigned`
- In Progress, On Site → `in_progress`
- Completed, PaymentPending, Invoiced, Approved, Paid, Late → `completed`
- Cancelled, Declined, Rejected → `cancelled`

**API Endpoints:**
- `POST /api/imports/workmarket` - Import scraped data (creates/updates jobs, adds time entries)
- `POST /api/imports/workmarket/preview` - Preview without importing

**Import Behavior:**
- Jobs created with "WM-" prefix (e.g., "WM-6946469146")
- Platform set to "WorkMarket" (code: "WM")
- Time entries appear as unassigned for technician assignment
- Re-import updates existing jobs matched by external_url or ticket_number

## Batch Scraper
Unified scraper that runs both Field Nation and WorkMarket in one session, then auto-imports results.
- `batch_scraper.py` - Main script
- `run_batch_scraper.bat` - Windows batch file with menu

**Features:**
- Scrapes both platforms in a single session
- For completed/paid: checks API to skip already-imported jobs
- Auto-imports scraped data after scraping (uses `import_single_file`)
- Date filter: skips jobs before `MIN_JOB_DATE` (default 2025-12-25)

**Batch Scraper Menu (`run_batch_scraper.bat`):**
```
1. Scrape ALL statuses (both platforms)
2. Scrape active/assigned only
3. Scrape in-progress only (WorkMarket)
4. Scrape pending only
5. Scrape invoiced only (WorkMarket)
6. Scrape completed/paid only (smart - skips existing)
7. Field Nation only - all statuses
8. WorkMarket only - all statuses
9. Dry run (show what would be scraped)
S. Scrape only (no auto-import)
0. Exit
```

**CLI Flags:**
- `--all`, `--active`, `--in-progress`, `--pending`, `--invoiced`, `--completed`
- `--fn-only`, `--wm-only`
- `--dry-run`, `--no-import`
- `--min-date YYYY-MM-DD`, `--no-date-filter`

## Database Migrations Run
- 001: Initial schema
- 002: Financial fields (mileage, per_diem, personal_expenses, expenses, commissions)
- 003: Mileage rate history table
- 004: External URL field on jobs
- 005: Make tech_id nullable on time_entries

## User Roles
- **admin**: Full access
- **manager**: Can verify entries, view all reports, manage jobs
- **technician**: Can create/submit own time entries, view own data

## API Authentication
- JWT tokens stored in localStorage
- Access token + refresh token pattern
- Token refresh handled automatically in api.js

## Security Features
**Rate Limiting** (in `app/utils/auth.py`):
- Login: Default rate limit on failed attempts
- Token refresh: 20 attempts per 60 seconds per IP
- User registration: 10 attempts per 5 minutes per IP
- Password change: 5 attempts per 5 minutes per user+IP
- Admin password reset: 10 attempts per 5 minutes per IP

**Security Headers** (in `app/__init__.py`):
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-XSS-Protection: 1; mode=block` - Legacy XSS protection
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` - Restricts geolocation, microphone, camera
- `Content-Security-Policy` - Restricts resource loading (allows unsafe-inline for vanilla JS)
- `Strict-Transport-Security` - HSTS enabled in production only

**CORS Configuration**:
- Set `CORS_ORIGINS` in `.env` for allowed origins (comma-separated)
- Empty = same-origin only (default, secure)
- Frontend and API served from same origin, so CORS not needed

**Scraper Security**:
- `API_URL` environment variable required (no hardcoded fallback)
- `API_VERIFY_SSL` defaults to true, set to 'false' only for self-signed certs in dev

## Time Entries Features
**List View:**
- Shows job ticket, client name, technician, times, hours, status
- Filter by: status, technician (managers), date range, unassigned
- Bulk submit/verify actions with checkboxes

**Grouped by Job View:**
- Toggle with "Group by Job" button
- Entries organized under collapsible job cards
- Each card shows: ticket, client, entry count, total hours, billing amount
- Per-job select-all checkbox for bulk actions
- Endpoint: `GET /api/time-entries/grouped-by-job`

**TimeEntry.to_dict() includes:**
- `job_ticket`, `job_title`, `job_client` (from related Job)
- `tech_name` (from related Technician)

## Frontend Architecture
- **Type**: Vanilla JavaScript SPA with hash-based routing
- **No build tools** - served directly from `/app/static/`
- **Templates**: Jinja2 (`app/templates/`)
- **Main files**:
  - `app/static/js/app.js` (~1200 lines) - All page rendering and logic
  - `app/static/js/api.js` - API client with auth handling
  - `app/static/css/style.css` - All styles with CSS variables

**Routing**: Hash-based (`#dashboard`, `#jobs`, `#time-entries`, etc.)

**Key Pages object methods in app.js:**
- `Pages.dashboard()` - Dashboard with stats
- `Pages.jobs()` - Jobs list with filtering
- `Pages.timeEntries()` - Time entries with list/grouped views
- `Pages.editEntry()` - Modal for create/edit entry
- `Pages.payroll()` - Payroll report
- `Pages.technicians()` - Technician management
- `Pages.settings()` - System settings

## Models Overview
**Job**: ticket_number, description, client_name, job_date, job_status, billing_amount, expenses, commissions, external_url, platform_id, platform_job_code

**TimeEntry**: job_id, tech_id (nullable), date_worked, time_in, time_out, hours_worked, mileage, per_diem, personal_expenses, status, notes

**Technician**: name, email, phone, hourly_rate (minimum rate), status

**Platform**: name, code (e.g., "Field Nation", "FN")

**User**: email, password_hash, role, tech_id (links to technician)

## Common Tasks

**Deploy changes:**
```bash
git add -A && git commit -m "message" && git push origin main
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "cd /opt/work-tracking && sudo git pull origin main && sudo systemctl restart work-tracking"
```

**Check server logs:**
```bash
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "sudo journalctl -u work-tracking -f"
```

**Run data import (Field Nation or WorkMarket):**
```bash
cd scraper
import.bat
# Select JSON file, credentials saved after first use, confirm import
# File moves to completed-imports/ after success
```

## Environment Notes
- **Local dev**: Windows machine at `C:\Users\Jeremiah\projects\timesheets\work-tracking-system`
- **Server**: Ubuntu on GCP, app at `/opt/work-tracking`
- **API URL**: `https://worktracking.sleepybear.tech/api` (SSL cert, also accessible via IP `34.27.146.58`)
- **Git remote**: `https://github.com/jconnellyks-commits/work-tracking-system.git`
