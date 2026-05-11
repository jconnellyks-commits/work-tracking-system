# Email Parser Status & Log Page — Design Spec

## Overview

Add an admin-only "Email Parser" page to the work tracking frontend showing live service status and a persistent activity log of all processed emails.

## Database

New table `email_parser_log`:

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INT | AUTO_INCREMENT, PK | |
| timestamp | DATETIME | NOT NULL | When the email was processed |
| platform | VARCHAR(20) | NOT NULL | 'TST', 'TechLink', 'Unknown' |
| email_type | VARCHAR(30) | NOT NULL | 'service_order', 'special_update', 'work_order', 'unrecognized' |
| ticket_number | VARCHAR(50) | NULL | Extracted ticket number |
| client_name | VARCHAR(200) | NULL | Extracted client name |
| subject | VARCHAR(500) | NOT NULL | Original email subject line |
| status | VARCHAR(20) | NOT NULL | 'success', 'failed', 'review' |
| job_id | INT | NULL, FK -> jobs.id | Set on successful import |
| error_message | TEXT | NULL | Error details if failed |
| gmail_message_id | VARCHAR(100) | NULL | Gmail message ID for reference |

Indexes: `(timestamp)`, `(platform)`, `(status)`.

Migration file: `database/migrations/NNN_email_parser_log.sql`

## API Endpoints

New route file: `app/routes/email_parser.py`, blueprint prefix `/api/email-parser`.

### GET /api/email-parser/status

Auth: admin only (JWT).

Runs `systemctl status email-parser` via subprocess on the server. Returns:

```json
{
  "running": true,
  "uptime": "2h 15m",
  "since": "2026-05-11 11:10:56",
  "restart_count": 0
}
```

Parses systemd output for Active state, start time, and restart count.

### GET /api/email-parser/logs

Auth: admin only (JWT).

Query params:
- `page` (int, default 1)
- `per_page` (int, default 25)
- `platform` (string, optional — 'TST', 'TechLink', 'Unknown')
- `status` (string, optional — 'success', 'failed', 'review')
- `date_from` (string, optional — 'YYYY-MM-DD')
- `date_to` (string, optional — 'YYYY-MM-DD')

Returns paginated log entries ordered by timestamp desc:

```json
{
  "logs": [
    {
      "id": 1,
      "timestamp": "2026-05-11 11:10:58",
      "platform": "TST",
      "email_type": "service_order",
      "ticket_number": "502861",
      "client_name": "Altoona Quarry",
      "subject": "TST 502861 for Altoona Quarry Service Order",
      "status": "success",
      "job_id": 234,
      "error_message": null,
      "gmail_message_id": "abc123"
    }
  ],
  "page": 1,
  "pages": 5,
  "total": 112
}
```

### POST /api/email-parser/logs

Auth: JWT (called by the email parser daemon using its existing API credentials).

Body:

```json
{
  "platform": "TST",
  "email_type": "service_order",
  "ticket_number": "502861",
  "client_name": "Altoona Quarry",
  "subject": "TST 502861 for Altoona Quarry Service Order",
  "status": "success",
  "job_id": 234,
  "error_message": null,
  "gmail_message_id": "abc123"
}
```

Returns `201` with the created log entry.

## SQLAlchemy Model

New `EmailParserLog` model in `app/models.py`:

```python
class EmailParserLog(db.Model):
    __tablename__ = 'email_parser_log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    platform = db.Column(db.String(20), nullable=False)
    email_type = db.Column(db.String(30), nullable=False)
    ticket_number = db.Column(db.String(50))
    client_name = db.Column(db.String(200))
    subject = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'))
    error_message = db.Column(db.Text)
    gmail_message_id = db.Column(db.String(100))
```

## Email Parser Daemon Changes

Minimal changes to the existing daemon:

### api_client.py

Add one method to `WorkTrackingClient`:

```python
def log_email_processed(self, platform, email_type, subject, status,
                        ticket_number=None, client_name=None,
                        job_id=None, error_message=None, gmail_message_id=None):
    """POST a log entry to the work tracking API."""
    payload = {
        'platform': platform,
        'email_type': email_type,
        'subject': subject,
        'status': status,
        'ticket_number': ticket_number,
        'client_name': client_name,
        'job_id': job_id,
        'error_message': error_message,
        'gmail_message_id': gmail_message_id,
    }
    return self._post('/email-parser/logs', payload)
```

### email_parser.py

After each `process_message()` outcome, call `api_client.log_email_processed(...)` with the result. This is added at each of the existing success/failure/review label points in `process_message()`.

The log call is wrapped in try/except so a logging failure doesn't prevent email processing from continuing.

## Frontend

### Sidebar

New nav item in `setupSidebar()`:

```javascript
{ id: 'email-parser', icon: 'fas fa-envelope', label: 'Email Parser', roles: ['admin'] }
```

### Router

New case in `navigate()`:

```javascript
case 'email-parser':
    await Pages.emailParser(content);
```

### Page Layout

`Pages.emailParser(content)` renders two sections:

**Status Card (top):**
- Green circle + "Running" or red circle + "Stopped"
- Uptime duration (e.g., "2h 15m")
- Running since timestamp
- Restart count
- Manual refresh button
- Auto-polls GET `/api/email-parser/status` every 30 seconds
- Polling stops when user navigates away (clearInterval on page change)

**Activity Log (bottom):**
- Filter row: Platform dropdown (All/TST/TechLink/Unknown), Status dropdown (All/Success/Failed/Review), date range inputs
- Table columns: Timestamp | Platform | Type | Ticket # | Client | Status | Job | Details
- Status column uses color-coded badges (green=success, red=failed, yellow=review)
- Job column is a clickable link (`#jobs?id=X`) when job_id is present, dash when null
- Details column shows error_message for failed entries, "Imported" for success
- Pagination controls (25 per page)
- Filters trigger immediate reload

### API Client (api.js)

Add to the API object:

```javascript
emailParser: {
    getStatus: () => fetchAPI('/email-parser/status'),
    getLogs: (params) => fetchAPI('/email-parser/logs?' + new URLSearchParams(params)),
}
```

## Blueprint Registration

Register `email_parser_bp` in `app/__init__.py` alongside existing blueprints.

## Files to Create/Modify

| File | Action | What |
|------|--------|------|
| `database/migrations/NNN_email_parser_log.sql` | Create | Migration for new table |
| `app/models.py` | Modify | Add EmailParserLog model |
| `app/routes/email_parser.py` | Create | Status + logs API endpoints |
| `app/__init__.py` | Modify | Register new blueprint |
| `app/static/js/app.js` | Modify | Add sidebar item, router case, Pages.emailParser() |
| `app/static/js/api.js` | Modify | Add emailParser API methods |
| `app/static/css/style.css` | Modify | Status card + badge styles |
| `email_parser/api_client.py` | Modify | Add log_email_processed() method |
| `email_parser/email_parser.py` | Modify | Call log method after processing |
