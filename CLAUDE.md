# Work Tracking System - Project Context

## Overview
Flask-based work tracking and timesheet system for managing technician time entries, job billing, and payroll calculations.

## Tech Stack
- **Backend**: Flask + SQLAlchemy
- **Database**: MySQL (`work_tracking_db`)
- **Frontend**: Vanilla JavaScript (single-page app)
- **Server**: GCP Compute Engine with Gunicorn + systemd

## Server Access
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

## Unassigned Time Entries
- Time entries can now be created without a technician (for scraped/imported data)
- Managers can filter by "Unassigned" in the time entries list
- "Assign" button appears for unassigned entries
- Submission blocked until technician is assigned
- Workflow: Import -> Review -> Assign Technician -> Submit -> Verify

## Field Nation Scraper
The `scraper/` folder (gitignored) contains tools for scraping Field Nation:
- `fieldnation_scraper.py` - Selenium-based scraper with persistent session
- `import_to_api.py` - Imports scraped JSON to the work tracking API (uses HTTPS)
- `import_to_api.bat` - Windows batch file to run the importer
- `run_scraper.bat` - Windows batch file to run the scraper
- `chrome_profile/` - Persistent Chrome profile (cookies/session saved here)

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

**Run Field Nation import:**
```bash
cd scraper
import_to_api.bat
# Select JSON file, enter credentials, confirm import
```

## Environment Notes
- **Local dev**: Windows machine at `C:\Users\Jeremiah\projects\timesheets\work-tracking-system`
- **Server**: Ubuntu on GCP, app at `/opt/work-tracking`
- **API URL**: `https://34.27.146.58/api` (HTTPS required, self-signed cert)
- **Git remote**: `https://github.com/jconnellyks-commits/work-tracking-system.git`
