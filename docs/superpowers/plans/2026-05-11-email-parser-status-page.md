# Email Parser Status & Log Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only "Email Parser" page showing live systemd service status and a persistent activity log of all processed emails, with the daemon posting log entries to the API after each email is handled.

**Architecture:** New `email_parser_log` DB table stores parsed email results. New Flask blueprint (`/api/email-parser`) exposes status (via subprocess) and CRUD for logs. The email parser daemon's `api_client.py` gets one new method to POST log entries. Frontend gets a new page with auto-refreshing status card and filterable/paginated activity log table.

**Tech Stack:** Flask + SQLAlchemy (backend), vanilla JS SPA (frontend), MySQL (database), systemd subprocess (status check)

---

### Task 1: Database Migration

**Files:**
- Create: `database/migrations/016_email_parser_log.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
CREATE TABLE IF NOT EXISTS email_parser_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    platform VARCHAR(20) NOT NULL,
    email_type VARCHAR(30) NOT NULL,
    ticket_number VARCHAR(50),
    client_name VARCHAR(200),
    subject VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL,
    job_id INT,
    error_message TEXT,
    gmail_message_id VARCHAR(100),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE SET NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_platform (platform),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Run migration on server**

```bash
# Copy migration to server
powershell -Command "scp -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' 'database\migrations\016_email_parser_log.sql' claude-code@34.27.146.58:/tmp/016_email_parser_log.sql"

# Run migration via dbrun.sh
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'sudo /tmp/dbrun.sh /tmp/016_email_parser_log.sql'"
```

Expected: Table created successfully.

- [ ] **Step 3: Commit**

```bash
git add database/migrations/016_email_parser_log.sql
git commit -m "feat: add email_parser_log table migration"
```

---

### Task 2: SQLAlchemy Model

**Files:**
- Modify: `app/models.py` (append after `PayoutAdjustment` class, around line 820)

- [ ] **Step 1: Add EmailParserLog model to app/models.py**

Add the following class at the end of `app/models.py`:

```python
class EmailParserLog(db.Model):
    """Log of emails processed by the email parser daemon."""
    __tablename__ = 'email_parser_log'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    platform = db.Column(db.String(20), nullable=False)
    email_type = db.Column(db.String(30), nullable=False)
    ticket_number = db.Column(db.String(50))
    client_name = db.Column(db.String(200))
    subject = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id', ondelete='SET NULL'))
    error_message = db.Column(db.Text)
    gmail_message_id = db.Column(db.String(100))

    job = db.relationship('Job', backref=db.backref('email_parser_logs', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None,
            'platform': self.platform,
            'email_type': self.email_type,
            'ticket_number': self.ticket_number,
            'client_name': self.client_name,
            'subject': self.subject,
            'status': self.status,
            'job_id': self.job_id,
            'error_message': self.error_message,
            'gmail_message_id': self.gmail_message_id,
        }
```

- [ ] **Step 2: Commit**

```bash
git add app/models.py
git commit -m "feat: add EmailParserLog model"
```

---

### Task 3: Backend API — Route File

**Files:**
- Create: `app/routes/email_parser.py`

- [ ] **Step 1: Create the email parser routes file**

Create `app/routes/email_parser.py` with the following content:

```python
"""
Email parser status and activity log endpoints.
"""

import subprocess
import re
from datetime import datetime

from flask import Blueprint, request, jsonify
from app.models import db, EmailParserLog
from app.utils.auth import jwt_required_with_user, admin_required

email_parser_bp = Blueprint('email_parser', __name__)


@email_parser_bp.route('/status', methods=['GET'])
@admin_required
def get_status():
    """Check email-parser systemd service status via subprocess."""
    try:
        result = subprocess.run(
            ['systemctl', 'show', 'email-parser',
             '--property=ActiveState,SubState,ExecMainStartTimestamp,NRestarts'],
            capture_output=True, text=True, timeout=5
        )
        props = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, val = line.split('=', 1)
                props[key.strip()] = val.strip()

        active_state = props.get('ActiveState', 'unknown')
        running = active_state == 'active'

        since_raw = props.get('ExecMainStartTimestamp', '')
        since = None
        uptime = None
        if since_raw and since_raw != 'n/a':
            # Parse systemd timestamp: "Mon 2026-05-11 11:10:56 CDT"
            # Strip day name and timezone for parsing
            ts_clean = re.sub(r'^[A-Za-z]+ ', '', since_raw)
            ts_clean = re.sub(r' [A-Z]{2,4}$', '', ts_clean)
            try:
                start_dt = datetime.strptime(ts_clean, '%Y-%m-%d %H:%M:%S')
                since = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                if running:
                    delta = datetime.now() - start_dt
                    total_seconds = int(delta.total_seconds())
                    days = total_seconds // 86400
                    hours = (total_seconds % 86400) // 3600
                    minutes = (total_seconds % 3600) // 60
                    parts = []
                    if days > 0:
                        parts.append(f"{days}d")
                    if hours > 0:
                        parts.append(f"{hours}h")
                    parts.append(f"{minutes}m")
                    uptime = ' '.join(parts)
            except ValueError:
                pass

        restart_count = int(props.get('NRestarts', 0))

        return jsonify({
            'running': running,
            'state': props.get('SubState', 'unknown'),
            'uptime': uptime,
            'since': since,
            'restart_count': restart_count,
        })

    except subprocess.TimeoutExpired:
        return jsonify({'running': False, 'state': 'timeout', 'uptime': None, 'since': None, 'restart_count': 0})
    except FileNotFoundError:
        return jsonify({'running': False, 'state': 'systemctl not found', 'uptime': None, 'since': None, 'restart_count': 0})


@email_parser_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """Return paginated, filterable activity log."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    platform = request.args.get('platform')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = EmailParserLog.query

    if platform:
        query = query.filter(EmailParserLog.platform == platform)
    if status:
        query = query.filter(EmailParserLog.status == status)
    if date_from:
        try:
            query = query.filter(EmailParserLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(EmailParserLog.timestamp <= dt_to)
        except ValueError:
            pass

    query = query.order_by(EmailParserLog.timestamp.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'logs': [log.to_dict() for log in pagination.items],
        'page': pagination.page,
        'pages': pagination.pages,
        'total': pagination.total,
    })


@email_parser_bp.route('/logs', methods=['POST'])
@jwt_required_with_user
def create_log():
    """Create a log entry (called by the email parser daemon)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['platform', 'email_type', 'subject', 'status']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    log = EmailParserLog(
        platform=data['platform'],
        email_type=data['email_type'],
        ticket_number=data.get('ticket_number'),
        client_name=data.get('client_name'),
        subject=data['subject'],
        status=data['status'],
        job_id=data.get('job_id'),
        error_message=data.get('error_message'),
        gmail_message_id=data.get('gmail_message_id'),
    )
    db.session.add(log)
    db.session.commit()

    return jsonify(log.to_dict()), 201
```

- [ ] **Step 2: Register blueprint in app/__init__.py**

In `app/__init__.py`, add the import after the existing blueprint imports (around line 76):

```python
from app.routes.email_parser import email_parser_bp
```

And add the registration after the existing blueprint registrations (around line 89):

```python
app.register_blueprint(email_parser_bp, url_prefix='/api/email-parser')
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/email_parser.py app/__init__.py
git commit -m "feat: add email parser status and logs API endpoints"
```

---

### Task 4: Email Parser Daemon — Log Method

**Files:**
- Modify: `email_parser/api_client.py` (add method after `import_techlink`, around line 77)

- [ ] **Step 1: Add log_email_processed method to WorkTrackingClient**

Add the following method at the end of the `WorkTrackingClient` class in `email_parser/api_client.py`:

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
        try:
            return self._post('/email-parser/logs', payload)
        except Exception as e:
            logger.warning(f"Failed to log email processing: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add email_parser/api_client.py
git commit -m "feat: add log_email_processed method to daemon API client"
```

---

### Task 5: Email Parser Daemon — Integrate Logging Calls

**Files:**
- Modify: `email_parser/email_parser.py` (modify `process_message` function, lines 94-171)

- [ ] **Step 1: Update process_message to accept and use api_client for logging**

Replace the entire `process_message` function (lines 94-171) in `email_parser/email_parser.py` with:

```python
def process_message(gmail_client, api_client, msg_id):
    """Fetch and process a single Gmail message."""
    try:
        msg = gmail_client.get_message(msg_id)
    except Exception as e:
        logger.error(f"Failed to fetch message {msg_id}: {e}")
        return

    subject = get_header(msg, 'Subject')
    sender_domain = get_sender_domain(msg)
    logger.info(f"Processing message {msg_id}: from=@{sender_domain} subject={subject!r}")

    # --- TST ---
    if config.TST_SENDER_DOMAIN in sender_domain:
        email_type, ticket, client = classify_tst_subject(subject)

        if email_type == 'service_order':
            job = parse_service_order(msg, ticket, client)
            if job:
                try:
                    result = api_client.import_tst([job])
                    logger.info(f"TST import result: {result}")
                    api_client.log_email_processed(
                        platform='TST', email_type='service_order', subject=subject,
                        status='success', ticket_number=ticket, client_name=client,
                        gmail_message_id=msg_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to import TST-{ticket}: {e}")
                    api_client.log_email_processed(
                        platform='TST', email_type='service_order', subject=subject,
                        status='failed', ticket_number=ticket, client_name=client,
                        error_message=str(e), gmail_message_id=msg_id,
                    )
                    gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])
                    return
            gmail_client.apply_labels(
                msg_id,
                add_label_names=[config.LABEL_TST_PROCESSED],
                remove_label_ids=['INBOX'],
            )

        elif email_type == 'special_update':
            update = parse_special_update(msg, ticket)
            if update:
                try:
                    result = api_client.import_tst([update])
                    logger.info(f"TST update result: {result}")
                    api_client.log_email_processed(
                        platform='TST', email_type='special_update', subject=subject,
                        status='success', ticket_number=ticket, gmail_message_id=msg_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to import TST update {ticket}: {e}")
                    api_client.log_email_processed(
                        platform='TST', email_type='special_update', subject=subject,
                        status='failed', ticket_number=ticket,
                        error_message=str(e), gmail_message_id=msg_id,
                    )
                    gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])
                    return
            gmail_client.apply_labels(
                msg_id,
                add_label_names=[config.LABEL_TST_PROCESSED],
                remove_label_ids=['INBOX'],
            )

        else:
            logger.info(f"TST email not recognized as SO or SU, flagging for review: {subject!r}")
            api_client.log_email_processed(
                platform='TST', email_type='unrecognized', subject=subject,
                status='review', gmail_message_id=msg_id,
            )
            gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])

    # --- TechLink ---
    elif config.TECHLINK_SENDER_DOMAIN in sender_domain:
        ticket = classify_techlink_subject(subject)

        if ticket:
            job = parse_techlink_email(msg, ticket)
            if job:
                try:
                    result = api_client.import_techlink([job])
                    logger.info(f"TechLink import result: {result}")
                    api_client.log_email_processed(
                        platform='TechLink', email_type='work_order', subject=subject,
                        status='success', ticket_number=ticket,
                        client_name=job.get('client_name'),
                        gmail_message_id=msg_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to import TL-{ticket}: {e}")
                    api_client.log_email_processed(
                        platform='TechLink', email_type='work_order', subject=subject,
                        status='failed', ticket_number=ticket,
                        error_message=str(e), gmail_message_id=msg_id,
                    )
                    gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])
                    return
            gmail_client.apply_labels(
                msg_id,
                add_label_names=[config.LABEL_TL_PROCESSED],
                remove_label_ids=['INBOX'],
            )
        else:
            logger.info(f"TechLink email not recognized as Assigned, flagging for review: {subject!r}")
            api_client.log_email_processed(
                platform='TechLink', email_type='unrecognized', subject=subject,
                status='review', gmail_message_id=msg_id,
            )
            gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])

    else:
        logger.debug(f"Message {msg_id} from unknown sender @{sender_domain}, ignoring")
```

**Note:** The import endpoints don't currently return `job_id` in their response, so `job_id` will be `None` in log entries. The ticket number is still recorded, which the frontend can use. Enhancement to include `job_id` in import responses can be done separately if needed.

- [ ] **Step 2: Commit**

```bash
git add email_parser/email_parser.py
git commit -m "feat: add logging calls to email parser process_message"
```

---

### Task 6: Frontend — API Client Methods

**Files:**
- Modify: `app/static/js/api.js` (add after the `my` object, around line 680)

- [ ] **Step 1: Add emailParser methods to api.js**

Add the following object to the `API` object in `api.js`, after the `my` section (before the closing `};` of the API object):

```javascript
    // Email parser endpoints
    emailParser: {
        async getStatus() {
            return API.request('/email-parser/status');
        },

        async getLogs(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/email-parser/logs${query ? '?' + query : ''}`);
        },
    },
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/api.js
git commit -m "feat: add email parser API client methods"
```

---

### Task 7: Frontend — Sidebar, Router, and Page Title

**Files:**
- Modify: `app/static/js/app.js`

- [ ] **Step 1: Add sidebar menu item**

In the `setupSidebar()` method, add the following entry to the `menuItems` array. Insert it after the `backups` entry (line 66) and before the closing `]`:

```javascript
            { id: 'email-parser', icon: 'fas fa-envelope', label: 'Email Parser', roles: ['admin'] }
```

- [ ] **Step 2: Add page title**

In the `navigate()` method, add to the `titles` object (around line 119, before the closing `}`):

```javascript
            'email-parser': 'Email Parser'
```

- [ ] **Step 3: Add router case**

In the `navigate()` method's switch statement, add a new case before the `default:` (around line 167):

```javascript
                case 'email-parser':
                    await Pages.emailParser(content);
                    break;
```

- [ ] **Step 4: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add email parser to sidebar, router, and page titles"
```

---

### Task 8: Frontend — Email Parser Page

**Files:**
- Modify: `app/static/js/app.js` (add new `Pages.emailParser` method)

- [ ] **Step 1: Add the emailParser page method to the Pages object**

Add the following methods to the `Pages` object in `app.js`. Find the right location — after an existing page method (e.g., after the `backups` page method or at the end of the Pages object before its closing `}`:

```javascript
    // --- Email Parser Status & Log ---
    _emailParserInterval: null,

    async emailParser(container) {
        if (App.user.role !== 'admin') {
            container.innerHTML = '<div class="alert alert-error">Access denied</div>';
            return;
        }

        // Clear any previous polling interval
        if (Pages._emailParserInterval) {
            clearInterval(Pages._emailParserInterval);
            Pages._emailParserInterval = null;
        }

        container.innerHTML = `
            <div class="card" style="margin-bottom: 1.5rem;">
                <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 class="card-title"><i class="fas fa-heartbeat"></i> Service Status</h3>
                    <button class="btn btn-sm btn-secondary" onclick="Pages.refreshEmailParserStatus()">
                        <i class="fas fa-sync"></i> Refresh
                    </button>
                </div>
                <div id="ep-status-body" style="padding: 1rem;">
                    <div class="loading"><div class="spinner"></div>Checking service status...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-list"></i> Activity Log</h3>
                </div>
                <div style="padding: 1rem; display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end;">
                    <div class="form-group" style="margin: 0;">
                        <label>Platform</label>
                        <select id="ep-filter-platform" class="form-control">
                            <option value="">All</option>
                            <option value="TST">TST</option>
                            <option value="TechLink">TechLink</option>
                            <option value="Unknown">Unknown</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>Status</label>
                        <select id="ep-filter-status" class="form-control">
                            <option value="">All</option>
                            <option value="success">Success</option>
                            <option value="failed">Failed</option>
                            <option value="review">Review</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>From</label>
                        <input type="date" id="ep-filter-from" class="form-control">
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>To</label>
                        <input type="date" id="ep-filter-to" class="form-control">
                    </div>
                    <button class="btn btn-secondary" onclick="Pages.loadEmailParserLogs()">
                        <i class="fas fa-search"></i> Filter
                    </button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Platform</th>
                                <th>Type</th>
                                <th>Ticket #</th>
                                <th>Client</th>
                                <th>Status</th>
                                <th>Job</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody id="ep-log-table">
                            <tr><td colspan="8" class="text-center">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
                <div id="ep-pagination" style="padding: 1rem; display: flex; justify-content: center; gap: 0.5rem;"></div>
            </div>
        `;

        // Attach filter listeners
        ['ep-filter-platform', 'ep-filter-status', 'ep-filter-from', 'ep-filter-to'].forEach(id => {
            document.getElementById(id).addEventListener('change', () => Pages.loadEmailParserLogs());
        });

        // Initial load
        await Pages.refreshEmailParserStatus();
        await Pages.loadEmailParserLogs();

        // Auto-refresh status every 30s
        Pages._emailParserInterval = setInterval(() => {
            if (App.currentPage !== 'email-parser') {
                clearInterval(Pages._emailParserInterval);
                Pages._emailParserInterval = null;
                return;
            }
            Pages.refreshEmailParserStatus();
        }, 30000);
    },

    async refreshEmailParserStatus() {
        const body = document.getElementById('ep-status-body');
        if (!body) return;

        try {
            const data = await API.emailParser.getStatus();
            const dot = data.running
                ? '<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#27ae60;margin-right:8px;"></span>'
                : '<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e74c3c;margin-right:8px;"></span>';
            const stateText = data.running ? 'Running' : 'Stopped';

            body.innerHTML = `
                <div style="display: flex; gap: 2rem; align-items: center; flex-wrap: wrap;">
                    <div style="font-size: 1.1rem; font-weight: 600;">
                        ${dot}${stateText}
                    </div>
                    ${data.uptime ? `<div><strong>Uptime:</strong> ${data.uptime}</div>` : ''}
                    ${data.since ? `<div><strong>Since:</strong> ${data.since}</div>` : ''}
                    <div><strong>Restarts:</strong> ${data.restart_count}</div>
                </div>
            `;
        } catch (e) {
            body.innerHTML = `<div class="alert alert-error">Failed to check status: ${e.message}</div>`;
        }
    },

    _emailParserCurrentPage: 1,

    async loadEmailParserLogs(page) {
        if (page !== undefined) Pages._emailParserCurrentPage = page;
        const currentPage = Pages._emailParserCurrentPage || 1;

        const params = { page: currentPage, per_page: 25 };
        const platform = document.getElementById('ep-filter-platform')?.value;
        const status = document.getElementById('ep-filter-status')?.value;
        const dateFrom = document.getElementById('ep-filter-from')?.value;
        const dateTo = document.getElementById('ep-filter-to')?.value;

        if (platform) params.platform = platform;
        if (status) params.status = status;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;

        const tbody = document.getElementById('ep-log-table');
        if (!tbody) return;

        try {
            const data = await API.emailParser.getLogs(params);
            const logs = data.logs || [];

            if (logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No log entries found</td></tr>';
                document.getElementById('ep-pagination').innerHTML = '';
                return;
            }

            const statusBadge = (s) => {
                const cls = { success: 'badge-success', failed: 'badge-danger', review: 'badge-warning' };
                return `<span class="badge ${cls[s] || 'badge-secondary'}">${s}</span>`;
            };

            const typeLabel = (t) => {
                const labels = {
                    service_order: 'Service Order',
                    special_update: 'Special Update',
                    work_order: 'Work Order',
                    unrecognized: 'Unrecognized',
                };
                return labels[t] || t;
            };

            tbody.innerHTML = logs.map(log => {
                const jobLink = log.job_id
                    ? `<a href="#jobs" onclick="event.preventDefault(); window.location.hash='jobs'; setTimeout(() => Pages.viewJob(${log.job_id}), 100);">#${log.job_id}</a>`
                    : '-';
                const details = log.status === 'failed' && log.error_message
                    ? `<span style="color:#e74c3c;font-size:0.85rem;" title="${log.error_message.replace(/"/g, '&quot;')}">${log.error_message.length > 50 ? log.error_message.substring(0, 50) + '...' : log.error_message}</span>`
                    : log.status === 'success' ? '<span style="color:#27ae60;font-size:0.85rem;">Imported</span>'
                    : log.status === 'review' ? '<span style="color:#f39c12;font-size:0.85rem;">Needs review</span>'
                    : '-';

                return `
                    <tr>
                        <td style="white-space:nowrap;">${log.timestamp || '-'}</td>
                        <td>${log.platform}</td>
                        <td>${typeLabel(log.email_type)}</td>
                        <td>${log.ticket_number || '-'}</td>
                        <td>${log.client_name || '-'}</td>
                        <td>${statusBadge(log.status)}</td>
                        <td>${jobLink}</td>
                        <td>${details}</td>
                    </tr>`;
            }).join('');

            // Pagination
            const pagDiv = document.getElementById('ep-pagination');
            if (data.pages > 1) {
                let html = '';
                html += `<button class="btn btn-sm btn-secondary" ${currentPage <= 1 ? 'disabled' : ''} onclick="Pages.loadEmailParserLogs(${currentPage - 1})">Prev</button>`;
                html += `<span style="padding: 0.4rem 0.8rem;">Page ${data.page} of ${data.pages} (${data.total} total)</span>`;
                html += `<button class="btn btn-sm btn-secondary" ${currentPage >= data.pages ? 'disabled' : ''} onclick="Pages.loadEmailParserLogs(${currentPage + 1})">Next</button>`;
                pagDiv.innerHTML = html;
            } else {
                pagDiv.innerHTML = data.total > 0 ? `<span style="color:#666;font-size:0.9rem;">${data.total} entries</span>` : '';
            }

        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error loading logs: ${error.message}</td></tr>`;
        }
    },
```

- [ ] **Step 2: Clear the polling interval when navigating away**

In the `navigate()` method, add the following at the top of the method body (after `this.currentPage = page;` on line 98):

```javascript
        // Stop email parser polling when navigating away
        if (Pages._emailParserInterval) {
            clearInterval(Pages._emailParserInterval);
            Pages._emailParserInterval = null;
        }
```

- [ ] **Step 3: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add email parser status page with auto-refresh and activity log"
```

---

### Task 9: Deploy and Test

**Files:** None (deployment and verification)

- [ ] **Step 1: Deploy to server**

```bash
git push origin main
```

Then deploy:

```bash
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'cd /opt/work-tracking && sudo git pull origin main && sudo systemctl restart work-tracking'"
```

- [ ] **Step 2: Copy updated email parser files to /opt/email-parser**

```bash
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'cd /opt/work-tracking && sudo cp email_parser/email_parser.py email_parser/api_client.py /opt/email-parser/ && sudo systemctl restart email-parser'"
```

- [ ] **Step 3: Verify service status endpoint**

Open `https://worktracking.sleepybear.tech` in a browser, log in as admin, and navigate to the Email Parser page. Verify:
- Status card shows green dot + "Running"
- Uptime and since timestamp are shown
- Restart count shows a number

- [ ] **Step 4: Verify activity log**

The log table will initially be empty since no emails have been processed with the new logging code. To verify the POST endpoint works, check the server logs:

```bash
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'sudo journalctl -u email-parser --no-pager -n 20'"
```

Confirm the email parser service is running without errors.

- [ ] **Step 5: Verify auto-refresh**

Stay on the Email Parser page for 30+ seconds and confirm the status card refreshes without a full page reload (check the browser dev console for periodic `/api/email-parser/status` requests).
