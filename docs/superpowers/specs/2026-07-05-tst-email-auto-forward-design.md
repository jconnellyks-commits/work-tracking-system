# TST Email Auto-Forward to Assigned Technicians

**Date:** 2026-07-05
**Status:** Draft

## Problem

Tech Service Today (TST) has no technician-facing app or portal. When a TST job is created via the email parser, the manager must manually forward the original dispatch email to the assigned technician so they have the job details and sign-off sheet. This is tedious and error-prone.

## Solution

Automatically forward the original TST dispatch email to the technician's email address when they are assigned to a TST job. Log every forward attempt with confirmation status visible in the UI.

## Scope

- **TST jobs only.** TechLink has a portal URL, Field Nation and WorkMarket have their own apps.
- **Auto-forward on assignment.** No manual trigger needed for the initial forward.
- **Retry button** for failed forwards or if the tech needs the email resent.

## Architecture

### Gmail Scope Upgrade

The email parser's OAuth token currently has `gmail.modify`. Add `gmail.send` to the scopes list. Re-run `auth_setup.py` on the server once to get consent for the new scope. The updated `token.json` is shared read-only with the Flask app.

**Files changed:**
- `email_parser/config.py` — add `gmail.send` to `GMAIL_SCOPES`

### Gmail Forwarding Utility

New module `app/utils/gmail_forward.py` in the Flask app:
- Reads the shared `token.json` from a configurable path (`GMAIL_TOKEN_FILE` env var, default `/opt/email-parser/token.json`)
- Authenticates to Gmail API using the same pattern as `email_parser/gmail_client.py`
- Provides `forward_email(gmail_message_id, to_email)`:
  1. Fetches the original message via `users().messages().get()` with `format='raw'`
  2. Decodes the raw RFC 2822 message
  3. Constructs a new message: `Fwd:` subject prefix, original body preserved (including attachments), `To:` set to the tech's email, `From:` set to the admin Gmail account
  4. Sends via `users().messages().send()`
- Returns `{'success': True}` or `{'success': False, 'error': '...'}`

### Assignment Flow Integration

In `app/routes/assignments.py`, after a tech is successfully assigned to a job:
1. Check if the job's platform is TST (`platform_id` matches TST or ticket starts with `TST-`)
2. Look up the `gmail_message_id` from `EmailParserLog` where `ticket_number` matches and `status='success'` and `email_type='service_order'`, ordered by most recent
3. If found and the tech has an email address, call `forward_email()`
4. Insert a record into the `email_forwards` table with the result
5. Include forward status in the assignment response JSON

This fires automatically for every TST assignment. It does NOT depend on the `send_sms` flag.

### Email Forward Tracking

**New table: `email_forwards`**

| Column | Type | Notes |
|--------|------|-------|
| id | INT PK | auto-increment |
| job_id | INT FK → jobs | which job |
| tech_id | INT FK → technicians | who received it |
| assignment_id | INT FK → job_assignments | which assignment triggered it |
| gmail_message_id | VARCHAR(100) | original email message ID |
| forwarded_to | VARCHAR(100) | tech's email address |
| status | VARCHAR(20) | 'sent' or 'failed' |
| error_message | TEXT | error details if failed |
| forwarded_at | DATETIME | timestamp |

**New model: `EmailForward`** in `app/models.py`

**New migration:** `database/migrations/0XX_email_forwards.sql`

### API Changes

**Modified endpoint:** `POST /api/assignments/job/<id>`
- Response now includes `email_forward_results` array (parallel to existing `sms_results`)
- Each entry: `{tech_id, tech_name, success, error, forwarded_to}`

**New endpoint:** `POST /api/assignments/<id>/resend-email`
- Manager+ only
- Re-forwards the TST email for an existing assignment
- Same logic as the auto-forward but triggered manually

**New endpoint:** `GET /api/jobs/<id>/email-forwards`
- Returns all forward records for a job
- Used by the UI to show forward status

### UI Changes

**Assignment view / job detail:**
- After a TST assignment, show a small indicator next to the tech's name:
  - Green checkmark + "Email forwarded" + timestamp if successful
  - Yellow warning + "Forward failed" + "Retry" button if failed
  - Gray "No email on file" if tech has no email address
  - Gray "No source email" if no gmail_message_id found in parser log

**Retry button:** Calls `POST /api/assignments/<id>/resend-email`

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Tech has no email | Skip forward, log warning, show "No email on file" in UI |
| No gmail_message_id in parser log | Skip forward, show "No source email" in UI (manually-created TST jobs) |
| Multiple techs assigned to same job | Forward to each independently |
| Tech removed and new one assigned | Forward to the new tech; old forward stays in log |
| Gmail token expired | Attempt refresh; if refresh fails, log failure and surface in UI |
| Re-assignment (reactivated cancelled assignment) | Forward again to the tech |
| Non-TST job | No forwarding attempted |

## Dependencies

- Gmail API libraries need to be installed in the Flask app's venv (they are NOT currently installed — only in the email parser's separate venv):
  - `google-api-python-client`
  - `google-auth`
  - `google-auth-oauthlib`
- Flask app needs read access to `/opt/email-parser/token.json` (already readable by `claude-code` user which runs both services)

## One-Time Setup

1. Add `gmail.send` scope to `email_parser/config.py`
2. On the server: run `auth_setup.py` to re-consent with the new scope
3. Add `GMAIL_TOKEN_FILE=/opt/email-parser/token.json` to the Flask app's `.env`
4. Run the new database migration
