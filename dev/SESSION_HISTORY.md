# Work Tracking System - Session History

## Session: May 11, 2026 (2nd — Job Bundling)

### Summary
Designed, implemented, and deployed the Job Bundling feature. Groups related jobs so their financials pool for pay calculation. Includes bundle CRUD, pay calculator integration, time entry support, report indicators, and full frontend management.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Design spec for job bundling | Done | `docs/superpowers/specs/2026-05-11-job-bundling-design.md` |
| Implementation plan (10 tasks) | Done | `docs/superpowers/plans/2026-05-11-job-bundling.md` |
| Migration 017: job_bundles table, bundle_id on jobs/time_entries | Done | `657fcc4` |
| JobBundle model + bundle_id FK on Job/TimeEntry | Done | `e02dcd1` |
| Bundle CRUD + membership API routes | Done | `c3d7227` |
| Pay calculator: calculate_bundle_pay + bundle-aware period pay | Done | `c515209` |
| Time entry routes: bundle_id support, job_id now optional | Done | `a38ad91` |
| API client: API.bundles namespace (8 methods) | Done | `4d78c85` |
| Frontend: Jobs page bundle management (create/view/add/remove) | Done | `6286ec7` |
| Frontend: Time entry form bundle dropdown | Done | `6286ec7` |
| Frontend: Bundle indicators in payroll + income/expense reports | Done | `5bf4ab0` |
| Bundle_id/bundle_name in income/expense report API | Done | `5bf4ab0` |
| Deploy migration + code to server | Done | Verified tables + service running |
| Bugfix: modal overlays missing 'active' CSS class | Done | `f45a7f9` |
| Bugfix: App.showToast → App.showAlert (method didn't exist) | Done | `1154e29` |
| Bugfix: empty tech_id string causing MySQL DataError | Done | `60e393c` |

### Technical Notes

**Job Bundling Architecture**:
- `job_bundles` table with auto-name (first job's description + "Bundle" if name is null)
- Jobs get `bundle_id` FK; time entries get `bundle_id` FK + `job_id` becomes nullable
- A time entry must have at least one of `job_id` or `bundle_id` (app-layer enforcement)

**Pay Calculation**:
- `calculate_bundle_pay(bundle_id)`: pools billing/expenses/commissions from all jobs in bundle, queries entries via `job_id IN (bundle_jobs) OR bundle_id = X`
- `calculate_period_pay()`: bundled jobs merge under `"bundle:<id>"` key using `_VirtualBundleJob` with pooled financials; unbundled jobs unchanged

**Frontend**:
- "Create Bundle" button on Jobs page opens modal with job multi-select + search
- Bundle badge (purple layer-group icon) on bundled job descriptions, clickable to view bundle details
- "Add to Bundle" / "Remove from Bundle" buttons in job actions column
- Time entry form: bundle dropdown alongside job dropdown; selecting bundle makes job optional
- Reports: bundle icon prefix on bundled job rows in payroll and income/expense reports

**Bugs Found & Fixed**:
1. Modal CSS requires `.active` class — bundle modals created without it were invisible
2. `App.showToast` doesn't exist (correct: `App.showAlert`) — JS error prevented dialog close
3. Empty string `tech_id` from form sent to MySQL as `''` for INT column — converted to null in both frontend and backend

### Files Created
- `app/routes/bundles.py` — 8 endpoints (CRUD, membership, pay)
- `database/migrations/017_job_bundles.sql`
- `docs/superpowers/specs/2026-05-11-job-bundling-design.md`
- `docs/superpowers/plans/2026-05-11-job-bundling.md`

### Files Modified
- `app/models.py` — JobBundle model, bundle_id on Job/TimeEntry, job_id nullable
- `app/__init__.py` — register bundles_bp
- `app/utils/pay_calculator.py` — calculate_bundle_pay, _VirtualBundleJob, bundle-aware period pay
- `app/routes/time_entries.py` — bundle_id in create/update/list, tech_id empty→null
- `app/routes/reports.py` — bundle_id/bundle_name in income/expense response
- `app/static/js/api.js` — API.bundles namespace
- `app/static/js/app.js` — bundle management UI, entry form, report indicators, bug fixes

### Next Steps
- Test pay calculation with real bundled jobs in upcoming pay period
- Verify pooled financials produce expected results
- Consider adding bundle pay preview in the bundle detail modal

---

## Session: May 11, 2026

### Summary
Fixed email parser service (expired OAuth2 token, missing Pub/Sub subscription), then designed and built a full Email Parser Status & Log page for the admin frontend.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Diagnose email parser crash loop | Done | Token expired + Pub/Sub subscription missing |
| Regenerate OAuth2 token | Done | Ran `auth_setup.py` locally, SCP'd to server |
| Create Pub/Sub subscription | Done | `gmail-dispatch-sub` on `gmail-dispatch-notifications` topic |
| Design spec for email parser status page | Done | `docs/superpowers/specs/2026-05-11-email-parser-status-page-design.md` |
| Implementation plan | Done | `docs/superpowers/plans/2026-05-11-email-parser-status-page.md` |
| DB migration 016: email_parser_log table | Done | Deployed via `/tmp/dbrun.sh` |
| SQLAlchemy EmailParserLog model | Done | `app/models.py` |
| Backend API routes (status, GET/POST logs) | Done | `app/routes/email_parser.py` |
| Blueprint registration | Done | `app/__init__.py` |
| Frontend API client methods | Done | `app/static/js/api.js` |
| Frontend sidebar, router, page title | Done | `app/static/js/app.js` |
| Frontend email parser page (status card + activity log) | Done | `app/static/js/app.js` |
| Daemon api_client.log_email_processed() | Done | `email_parser/api_client.py` |
| Daemon process_message logging integration | Done | `email_parser/email_parser.py` |
| Deploy and verify in browser | Done | All services restarted, page verified |
| Bugfix: systemctl not in gunicorn PATH | Done | Changed to `/usr/bin/systemctl` absolute path |

### Technical Notes

**Email Parser Page** (`#email-parser`, admin-only):
- **Status card**: Green/red dot, uptime, since timestamp, restart count. Auto-refreshes every 30s, clears interval on navigation.
- **Activity log**: Filterable by platform (TST/TechLink/Unknown), status (success/failed/review), date range. Paginated 25/page. Job column links to `#jobs?id=X`.
- **API**: `GET /api/email-parser/status` (systemctl show), `GET /api/email-parser/logs` (paginated query), `POST /api/email-parser/logs` (daemon posts entries).
- **Daemon integration**: `log_email_processed()` called at every TST/TechLink processing outcome, wrapped in try/except.

**Key bug found**: Gunicorn runs as `www-data` which doesn't have `/usr/bin` in PATH. `systemctl` call failed with `FileNotFoundError`. Fixed by using absolute path `/usr/bin/systemctl`.

**Forwarded emails**: Emails forwarded from TechLink to Gmail have `@gmail.com` as sender, so they don't match `TECHLINK_SENDER_DOMAIN`. Only direct emails from `@techlinksvc.net` and `@techservicetoday.com` are processed and logged.

### Next Steps
- Activity log will populate as real TST/TechLink emails arrive
- Consider publishing OAuth consent screen to production to prevent 7-day token expiry
- Period 12 payout adjustments still pending
- SMS notifications for technicians

---

## Session: April 18, 2026

### Summary
Added hourly billing auto-calculation and reimbursable line items feature.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Switched existing hourly jobs to flat_rate | Done | 10 jobs updated, only NV-04142601 kept as hourly |
| Design spec for hourly billing + reimbursables | Done | `docs/superpowers/specs/2026-04-18-hourly-billing-and-reimbursables-design.md` |
| Implementation plan | Done | `docs/superpowers/plans/2026-04-18-hourly-billing-and-reimbursables.md` |
| Migration 015: billing_rate column + job_reimbursables table | Done | NV-04142601 set to $65/hr rate |
| Model changes: billing_rate, JobReimbursable, recalculate method | Done | `8d7110d` |
| Job API: billing_rate in CRUD, reimbursable endpoints | Done | `526098a` |
| Time entry hooks: recalculate on create/update/delete | Done | `71b32ab` |
| Pay calculator: reimbursable share distributed by hours ratio | Done | `d860f50` |
| Frontend: billing type toggle, rate field, read-only amount | Done | `8effdf8` |
| Frontend: reimbursables section with add/delete on job detail | Done | `b02b150` |
| Bugfix: empty reimbursables sum returning int instead of Decimal | Done | `5bdd94f` |
| Bugfix: reimbursables reading from wrong level in API response | Done | `807a14d` |
| Bugfix: billing_amount now includes reimbursables total | Done | `b83e0f9` |
| Bugfix: billing_rate cast to Decimal before multiplication | Done | `3719009` |

### Technical Notes

**Hourly billing formula**: `billing_amount = (billing_rate × total_hours) + reimbursables_total`
- Recalculated on time entry create/update/delete AND reimbursable add/delete
- Flat rate jobs unchanged — billing_amount set manually

**Reimbursables**: Line items (travel/parts/misc) on jobs. Included in billing_amount for hourly jobs. User offsets in pay calc by putting the cost in the expenses field.

**Pay calculator**: Reimbursable share added to tech pay, distributed proportionally by hours worked. Does NOT affect tech pool calculation.

### Next Steps
- Continue testing the feature in production
- Period 12 payout adjustments still pending

---

## Session: April 14, 2026

### Summary
Fixed multi-tech pay calculation formula and switched reports/payouts to per-entry row display.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Investigated pay calc discrepancy on FN-18830701 | Done | Found `calculate_period_pay` used independent proration instead of shared-pool weighted distribution |
| Reopened pay periods 10 & 11 (Feb 19–Mar 04, Mar 05–18) | Done | Were closed without payouts; locked and paid manually |
| Fixed `calculate_period_pay` — shared-pool weighted formula | Done | `96c67ef` — pools deductions, 50/50 split, weighted by min_pay×hours |
| Refactored `payroll_detail_report` to call `calculate_period_pay` | Done | Eliminated duplicated calculation logic |
| Split per-entry rows in reports and payouts | Done | `51512d1` — each time entry gets its own row instead of aggregating per job |
| Added `date_worked` to `PayoutJobDetail` model | Done | Migration 014, locked payout snapshots now per-entry |
| Updated frontend (payroll report, payout preview, pay stubs) | Done | Date column, CSV export updated |
| Noted Period 12 adjustment needed | Done | ~$198 owed to Jeremiah from old formula; saved to memory |

### Technical Notes

**Pay Formula (corrected)**:
1. Pool ALL deductions (mileage pay + per diem + personal expenses) across all techs on a job
2. `tech_pool = (prorated_net - pooled_deductions) / 2`
3. Distribute by `weight = (min_pay × hours) / Σ(min_pay × hours)`
4. Floor check: `base_pay = max(weighted_share, hours × min_rate)`

**Old bug**: Each tech was calculated independently with prorated billing — deductions weren't pooled and minimum rate overages inflated total pay beyond 50%.

**Period 12 deltas** (Mar 19–Apr 01, already paid with old formula):
- Jeremiah underpaid ~$198, Geoffery overpaid ~$93, Michael overpaid ~$97, Rowland overpaid ~$142
- Saved to memory for future payout adjustment

### Files Modified
- `app/utils/pay_calculator.py` — rewrote `calculate_period_pay`, added `_accumulate_tech_result` helper
- `app/routes/reports.py` — `payroll_detail_report` now delegates to `calculate_period_pay`
- `app/routes/payouts.py` — saves `date_worked` on payout job details
- `app/models.py` — added `date_worked` to `PayoutJobDetail`
- `app/static/js/app.js` — per-entry rows in report/payout/stub views
- `database/migrations/014_add_date_worked_to_payout_job_details.sql` — new migration

### Next Steps
- Apply Period 12 payout adjustments once exact amounts are recalculated
- SMS notifications for technicians (from TODO list)
- Time entries interface adjustments

---

## Session: February 20, 2026 (2nd — housekeeping)

### Summary
Recovered and committed progress from crashed session (timezone fix). Updated gitignore for loose root files.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Commit Feb 19 + Feb 20 session history (lost in crash) | Done | `61332c4` |
| Gitignore loose root files | Done | `429de2f` — *.png, *.jpg, *.eml, *.pdf, tmp_*.txt, b4crash.txt, client_secret*.json |

### Next Steps
- Wait for real TST/TechLink emails to verify email-parser pipeline end-to-end
- SMS outbound unblocked once 10DLC campaign is approved (no code changes needed)
- Time entries interface adjustments

---

## Session: February 20, 2026

### Summary
Added configurable timezone setting and fixed reports/dashboard showing wrong day after 6 PM (UTC offset issue).

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| New `app/utils/timezone.py` with `get_local_today()` | Done | Uses `zoneinfo` with configured timezone from SystemSettings |
| Income/expense report projected-day check uses configured timezone | Done | Was using `date.today()` (UTC) |
| Dashboard week/month stats use configured timezone | Done | Was using `datetime.utcnow()` |
| Migration 011: seeds `timezone = 'America/Chicago'` | Done | |
| Settings page: timezone dropdown (8 US + UTC options) | Done | Admin-only card |

### Technical Notes

**Root Cause**: `date.today()` and `datetime.utcnow()` return UTC on the server (GCP VM in UTC). After 6 PM CST = midnight UTC, "today" would advance, marking jobs as projected or miscounting week stats.

**Fix**: `get_local_today()` reads `timezone` from SystemSettings (cached), uses `zoneinfo.ZoneInfo` to get the correct local date.

**Timezone Options in Settings**: America/Chicago, America/New_York, America/Denver, America/Los_Angeles, America/Phoenix, America/Anchorage, Pacific/Honolulu, UTC.

### Files Modified
- `app/utils/timezone.py` — new file
- `app/routes/reports.py` — use `get_local_today()`
- `app/static/js/app.js` — timezone settings card
- `database/migrations/011_add_timezone_setting.sql` — new file

### Commit
`179a1f1`

---

## Session: February 19, 2026

### Summary
Built and deployed full email-based job import pipeline for TechLink and Tech Service Today (TST). New Flask endpoints receive parsed jobs, and a new `email-parser` systemd service on the GCP VM monitors jconnellyks@gmail.com via Gmail Pub/Sub and auto-creates job records when dispatch emails arrive.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| `POST /api/imports/tst` endpoint | Done | Creates `TST-{ticket}` jobs; re-import from Special Update appends rate info |
| `POST /api/imports/techlink` endpoint | Done | Creates `TL-{ticket}` jobs with description = summary + address + contact |
| `email_parser/` service package | Done | Tracked in git; credentials gitignored |
| Gmail OAuth2 Desktop credentials | Done | Created in GCP Console for `remoteworkstation` project |
| OAuth token obtained | Done | `auth_setup.py` run locally; token.json on server at `/opt/email-parser/token.json` |
| Pub/Sub topic + subscription | Done | `gmail-dispatch-notifications` / `gmail-dispatch-sub` |
| Gmail push IAM | Done | `gmail-api-push@system.gserviceaccount.com` → pubsub.publisher on topic |
| VM service account IAM | Done | `284520789984-compute@developer.gserviceaccount.com` → pubsub.subscriber on subscription |
| `/opt/email-parser/` deployed | Done | venv + deps installed, .env configured |
| `email-parser` systemd service | Done | Enabled, running, auto-restarts on failure |
| Daily watch-renewal cron | Done | 6 AM daily: `venv/bin/python /opt/email-parser/renew_watch.py` |

### Technical Notes

**Email parser architecture**:
- `email_parser.py` — daemon; StreamingPull loop; routes messages by sender domain + subject pattern
- `gmail_client.py` — Gmail API: watch, history list, message fetch, label/archive
- `api_client.py` — Work Tracking API: login, JWT auto-refresh, POST to import endpoints
- `parsers/tst.py` — TST Service Order (base64 body) + Special Update (quoted-printable) parsing
- `parsers/techlink.py` — TechLink Assigned email parsing

**Pub/Sub message decoding**:
- The Pub/Sub Python client library (`google-cloud-pubsub`) already base64-decodes the message data
- `pubsub_msg.data` is plain bytes — just do `json.loads(pubsub_msg.data)`, no extra b64decode

**ADC vs OAuth2 Desktop credentials**:
- Tried gcloud ADC first (`gcloud auth application-default login`) — fails on Gmail watch because the topic must be in `usable-auth-library` project (gcloud's internal project), not `remoteworkstation`
- Solution: proper OAuth2 Desktop app credentials from GCP Console → client_id tied to `remoteworkstation`, so topic validation passes

**quota_project_id**:
- Gmail API requires `x-goog-user-project` header when using user OAuth2 credentials
- Fix: call `creds.with_quota_project(config.GCP_PROJECT)` after loading token if not already set

**Watch registration**:
- Watch expires every ~7 days; renewed daily at 6 AM via cron
- `state.json` at `/opt/email-parser/state.json` tracks last `historyId` — persists across restarts

**Deployment pattern for email-parser**:
- Code lives in `email_parser/` in the git repo (tracked)
- On deploy: `sudo git pull` in `/opt/work-tracking`, then `cp email_parser/* /opt/email-parser/`
- Credentials (`token.json`, `credentials.json`) live only on server — never committed

### Files Changed
- `app/routes/imports.py` — added `/tst` and `/techlink` endpoints
- `email_parser/` — new package (all files)

### Bugs Fixed During Deployment
1. ADC `creds.expired` is None (not True) when no cached access token → check `creds.refresh_token` instead
2. ADC gcloud credentials fail Gmail watch (`usable-auth-library` project mismatch) → use OAuth2 Desktop creds
3. `quota_project_id` not set → force-set with `creds.with_quota_project()`
4. Double base64 decode on Pub/Sub message → remove extra `b64decode()`

### Next Step
Test with a real email: forward a TST or TechLink dispatch email to jconnellyks@gmail.com and verify job appears in work tracking UI within ~30 seconds.
Monitor: `sudo journalctl -u email-parser -f`

---

## Session: February 18, 2026 (4th session)

### Summary
Fixed SSH output issue, fixed WM scraper invitation filtering bugs, cleared 48 phantom WM jobs from DB.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| SSH fix: use PowerShell + Windows OpenSSH | Done | `powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' ..."` — Git bash SSH doesn't pipe stdout |
| WM scraper: individual menu options 1-4 now filter `is_invitation` | Done | Was appending all results; now skips invitations same as batch scraper |
| WM scraper: improved invitation detection (Method 1) | Done | Python-side `.lower()` comparison instead of fragile XPath translate() |
| WM scraper: improved invitation detection (Method 2) | Done | Added more phrases: `not yet accepted`, `pending acceptance`, `invitation pending` |
| WM scraper: new invitation detection (Method 3) | Done | For Active/In Progress tabs: if no confirmed-on/checkin data and page says available/invited → flag as invitation |
| WM scraper: `navigate_to_tab` returns `False` on redirect | Done | Was warning-only and returning `True`; now returns `False` so callers can bail |
| WM scraper: individual menu options bail on tab redirect | Done | All 4 choices check return value and `continue` if tab unavailable |
| Batch scraper: bail on tab redirect | Done | `navigate_to_tab` return value checked; skips with message |
| DB cleanup: deleted 48 WM jobs with 0 time entries | Done | All were invitation artifacts; 58 real WM jobs remain (all with entries) |
| Confirmed redirect fix works | Done | "In Progress" tab skipped cleanly when empty |

### Technical Notes

**SSH Fix**:
- Git bash SSH (`C:\Program Files\Git\usr\bin\ssh.exe`) does not pipe stdout back through Claude Code's Bash tool
- Windows OpenSSH via PowerShell works: `powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'COMMAND' 2>&1"`
- For DB queries: write SQL to local file → scp to server → run with `bash /tmp/dbrun.sh` (script reads password from .env)

**WM Tab Redirect**:
- When a WM tab is empty (no assignments), WM SPA redirects to `#status/all/managing`
- `navigate_to_tab` now checks final URL against expected hash and returns `False` if redirected
- Callers skip that tab entirely with a clear message

**Invitation Detection Priority Order**:
1. Scan all visible button/link/input elements for accept/apply text (Python .lower())
2. Page text scan for invitation phrases
3. Active/In Progress tabs only: no confirmation/checkin milestones + "available"/"invited" in page text

### Files Modified (local scraper/ only — gitignored)
- `scraper/workmarket_scraper.py` — invitation detection improvements, navigate_to_tab returns False, menu options filter invitations + check redirect
- `scraper/batch_scraper.py` — check navigate_to_tab return value

---

## Session: February 18, 2026 (3rd session)

### Summary
Implemented the SMS full flow: inbound webhook for STOP/START/HELP/Y/N handling, opt-in tracking per technician, availability request workflow, and SMS log UI. Webhook confirmed working (inbound message appeared in SMS log).

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Migration 010: sms_opted_in fields on technicians + availability_response on job_assignments | Done | `81c49af` |
| Technician model: sms_opted_in, sms_opted_in_at, sms_opted_out_at fields | Done | |
| JobAssignment model: availability_response, availability_responded_at fields | Done | |
| SMS service: opt-in guard in send_sms() | Done | Checks by tech_id or phone lookup; bypass_opt_in_check param for STOP replies |
| SMS service: send_availability_request() method | Done | Sends "Are you available for X on Y? Reply Y or N." Sets assignment status='invited' |
| Inbound webhook: POST /sms/inbound (new blueprint, no auth) | Done | Handles STOP/START/HELP/Y/YES/N/NO; logs all inbound to sms_notifications |
| Availability request endpoint: POST /api/assignments/job/<id>/availability-request | Done | Creates invited assignments, handles unique constraint by updating cancelled records |
| SMS log endpoint: GET /api/assignments/sms/log | Done | Manager+ only, filterable by tech/status/limit |
| Register sms_webhook_bp in app/__init__.py | Done | No url_prefix, route is /sms/inbound |
| API client: API.assignments.requestAvailability() + API.sms.getLog() | Done | |
| Frontend: SMS Log page (#sms-log) with filter by tech + status | Done | Nav entry for admin/manager |
| Frontend: "Request Availability" button in job modal footer | Done | |
| Frontend: Pages.requestAvailability() + Pages.saveAvailabilityRequest() | Done | Tech checklist modal, calls availability-request endpoint |
| Frontend: SMS opt-in badge on technician rows | Done | Green "SMS" or red "No SMS" badge next to phone |
| VoIP Innovations webhook URL set to /sms/inbound | Done | User configured in VI backoffice |
| Webhook smoke test | Done | Inbound message appeared in #sms-log ✅ |

### Technical Notes

**Inbound Webhook (`app/routes/sms_webhook.py`)**:
- `POST /sms/inbound` — no authentication, called by VoIP Innovations
- Parses flexible field names: `from/From`, `message/Message/body/Body/text/Text`
- STOP command: sets `sms_opted_in=False`, sends unsubscribe confirmation (bypass_opt_in=True for the reply)
- START command: sets `sms_opted_in=True`, sends re-subscribe confirmation
- Y/YES: finds latest 'invited' assignment for tech, sets status='accepted', availability_response='yes'
- N/NO: finds latest 'invited' assignment, sets status='declined', availability_response='no'
- All inbound messages logged to sms_notifications with `[INBOUND]` prefix

**Opt-In Guard in send_sms()**:
- Checks by tech_id when provided (most efficient)
- Falls back to phone number comparison (strips non-digits, matches last 10 digits) when no tech_id
- `bypass_opt_in_check=True` used for STOP/START/HELP reply confirmations (CTIA compliance)

**Availability Request Endpoint**:
- Handles unique constraint on (job_id, tech_id): reuses/updates existing cancelled/declined/expired records
- Active (accepted/invited) assignments are blocked with an error
- Sets `availability_response='pending'` on creation

**Current State of 10DLC**:
- Inbound SMS webhook working ✅
- Outbound replies blocked until 10DLC campaign approved (carriers rejecting unregistered traffic)
- No code changes needed when campaign is approved — it will work automatically

### Files Modified
- `database/migrations/010_add_sms_opt_in.sql` — new file
- `app/models.py` — new fields on Technician + JobAssignment
- `app/utils/sms_service.py` — opt-in guard, send_availability_request()
- `app/routes/sms_webhook.py` — new file (inbound webhook)
- `app/routes/assignments.py` — availability-request + sms-log routes
- `app/__init__.py` — register sms_webhook_bp
- `app/static/js/api.js` — requestAvailability, sms.getLog
- `app/static/js/app.js` — SMS log page, Request Availability button + modal, opt-in badge

---

## Session: February 18, 2026 (2nd session)

### Summary
Implemented calendar view page and scheduled start time field for jobs. Full implementation across DB, model, API, imports, and frontend.

### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Migration 009: scheduled_start_time on jobs | Done | `TIME NULL` column |
| Job model: scheduled_start_time field + to_dict | Done | Returns `HH:MM` string |
| Jobs API: accept scheduled_start_time on create/update | Done | Parsed from `HH:MM` string |
| Imports API: accept scheduled_start_time from scrapers | Done | Both FN and WM |
| Frontend: editJob modal — scheduled start time input | Done | `<input type="time">` field |
| Frontend: viewJob modal — show time badge next to date | Done | Uses `App.format12Hour()` |
| Frontend: App.format12Hour() utility | Done | 24h → 12h AM/PM display |
| Frontend: Calendar page (`Pages.calendar`) | Done | Vanilla JS, no external lib |
| Frontend: Calendar nav menu entry | Done | `fas fa-calendar-alt` icon |
| Frontend: Calendar CSS styles | Done | grid, day, chip, header |
| Scrapers: FN `extract_scheduled_time()` | Done | Captures time from date range patterns |
| Scrapers: WM `extract_scheduled_time()` | Done | Captures time from day/time line patterns |
| DB migration run on server | Done | `ALTER TABLE jobs ADD COLUMN scheduled_start_time TIME NULL` |
| Deploy + service restart | Done | Commit 33d2bec |

### Technical Notes

**Calendar Architecture**:
- Pure vanilla JS, no external calendar library
- State object tracks `{year, month, jobs, myJobIds}`
- `loadJobs()` fetches via `API.jobs.list({ from_date, to_date, per_page: 200 })`
- Chips colored by job status using inline styles (bg/border/text)
- Technician's own jobs: gold left border + bold font weight
- `Pages.calendar` function is self-contained with `loadJobs`, `buildCalendarHTML`, `attachEvents` inner functions

**Scheduled Start Time**:
- Stored as MySQL `TIME NULL` in jobs table
- API accepts `HH:MM` string, parsed with `datetime.strptime(..., '%H:%M').time()`
- Displayed in viewJob as a badge next to job date: "2/27/2026 [9:00 AM]"
- Shown on calendar chips as "(9:00 AM)" in muted text
- Scrapers: FN extracts from "date, time →" patterns; WM from day-of-week + time-on-next-line

### Files Modified
- `database/migrations/009_add_scheduled_start_time.sql` — new file
- `app/models.py` — Job model field + to_dict
- `app/routes/jobs.py` — create/update endpoints
- `app/routes/imports.py` — FN + WM import handlers
- `app/static/js/app.js` — nav, router, Pages.calendar, editJob, viewJob, format12Hour
- `app/static/css/style.css` — calendar styles
- `scraper/fieldnation_scraper.py` — extract_scheduled_time (local)
- `scraper/workmarket_scraper.py` — extract_scheduled_time (local)

---

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
