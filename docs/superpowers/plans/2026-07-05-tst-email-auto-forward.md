# TST Email Auto-Forward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a technician is assigned to a TST job, automatically forward the original dispatch email to the tech's email address, with full logging and retry capability.

**Architecture:** The Flask app reads the shared Gmail OAuth token from the email parser's `token.json` to forward emails via the Gmail API. A new `email_forwards` table tracks every attempt. The assignment endpoint triggers forwarding automatically for TST jobs, and a resend endpoint allows manual retry.

**Tech Stack:** Flask, SQLAlchemy, Gmail API (`google-api-python-client`, `google-auth`, `google-auth-oauthlib`), MySQL

## Global Constraints

- Gmail OAuth scope must include `gmail.send` (currently only `gmail.modify`)
- `auth_setup.py` must be updated and re-run locally to get a new `token.json` with the added scope, then SCP'd to server
- Gmail token path is configured via `GMAIL_TOKEN_FILE` env var (default `/opt/email-parser/token.json`)
- Google API libraries must be added to main `requirements.txt` and installed in server venv
- Email parser log stores `ticket_number` WITHOUT prefix (e.g., `"502861"`); Job model stores WITH prefix (`"TST-502861"`) — lookup must strip the prefix
- All server-side changes deploy via: `git push` → SSH `git pull` + `systemctl restart work-tracking`
- Migration runs manually via the `dbrun.sh` pattern (SCP SQL to `/tmp/q.sql`, execute)

---

### Task 1: Database Migration + Model

Create the `email_forwards` table and add the `EmailForward` SQLAlchemy model.

**Files:**
- Create: `database/migrations/023_email_forwards.sql`
- Modify: `app/models.py` (append new model after `EmailParserLog` class, ~line 1001)

**Interfaces:**
- Consumes: nothing
- Produces: `EmailForward` model with columns `id`, `job_id`, `tech_id`, `assignment_id`, `gmail_message_id`, `forwarded_to`, `status`, `error_message`, `forwarded_at`. Method `to_dict()` returns all fields as JSON-serializable dict. Relationship `job` backref creates `job.email_forwards` (lazy dynamic).

- [ ] **Step 1: Create migration SQL**

Create `database/migrations/023_email_forwards.sql`:

```sql
CREATE TABLE IF NOT EXISTS email_forwards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    tech_id INT NOT NULL,
    assignment_id INT,
    gmail_message_id VARCHAR(100) NOT NULL,
    forwarded_to VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    error_message TEXT,
    forwarded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (tech_id) REFERENCES technicians(tech_id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES job_assignments(assignment_id) ON DELETE SET NULL,
    INDEX idx_job_id (job_id),
    INDEX idx_assignment_id (assignment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Add EmailForward model to `app/models.py`**

Add after the `EmailParserLog` class (after line 1000):

```python
class EmailForward(db.Model):
    __tablename__ = 'email_forwards'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id', ondelete='CASCADE'), nullable=False)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id', ondelete='CASCADE'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('job_assignments.assignment_id', ondelete='SET NULL'))
    gmail_message_id = db.Column(db.String(100), nullable=False)
    forwarded_to = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='sent')
    error_message = db.Column(db.Text)
    forwarded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    job = db.relationship('Job', backref=db.backref('email_forwards', lazy='dynamic'))
    technician = db.relationship('Technician')
    assignment = db.relationship('JobAssignment')

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'assignment_id': self.assignment_id,
            'gmail_message_id': self.gmail_message_id,
            'forwarded_to': self.forwarded_to,
            'status': self.status,
            'error_message': self.error_message,
            'forwarded_at': self.forwarded_at.isoformat() if self.forwarded_at else None,
        }
```

- [ ] **Step 3: Run migration on server**

SCP the migration file to the server and run it:

```bash
# From local machine:
scp -i ~/.ssh/gcp_work_tracking database/migrations/023_email_forwards.sql claude-code@34.27.146.58:/tmp/q.sql
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "sudo /tmp/dbrun.sh"
```

Expected: table created successfully.

- [ ] **Step 4: Commit**

```bash
git add database/migrations/023_email_forwards.sql app/models.py
git commit -m "feat: add email_forwards table and EmailForward model"
```

---

### Task 2: Gmail Forwarding Utility

Build the utility that fetches an original email by Gmail message ID and forwards it to a recipient.

**Files:**
- Modify: `requirements.txt` (add Google API libraries)
- Modify: `email_parser/config.py` (add `gmail.send` scope)
- Modify: `email_parser/auth_setup.py` (update scopes to match config)
- Create: `app/utils/gmail_forward.py`

**Interfaces:**
- Consumes: nothing (standalone utility)
- Produces: `forward_email(gmail_message_id: str, to_email: str) -> dict` — returns `{'success': True, 'message_id': str}` or `{'success': False, 'error': str}`. Also `is_available() -> bool` to check if Gmail credentials are configured.

- [ ] **Step 1: Add Google API libs to `requirements.txt`**

Add to end of `requirements.txt`:

```
# Gmail API (for forwarding TST job emails)
google-api-python-client>=2.0
google-auth>=2.0
google-auth-oauthlib>=1.0
```

- [ ] **Step 2: Update Gmail scopes in `email_parser/config.py`**

Change line 44-46 from:

```python
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # read + label + archive
]
```

to:

```python
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # read + label + archive
    'https://www.googleapis.com/auth/gmail.send',    # send/forward emails
]
```

- [ ] **Step 3: Update scopes in `email_parser/auth_setup.py`**

Change line 14 from:

```python
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
```

to:

```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
]
```

- [ ] **Step 4: Create `app/utils/gmail_forward.py`**

```python
import base64
import email
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GMAIL_TOKEN_FILE = os.environ.get('GMAIL_TOKEN_FILE', '/opt/email-parser/token.json')
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
]

_service = None


def _get_service():
    global _service
    if _service is not None:
        return _service

    if not os.path.exists(GMAIL_TOKEN_FILE):
        logger.warning(f"Gmail token file not found: {GMAIL_TOKEN_FILE}")
        return None

    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.error("Gmail credentials invalid and no refresh token available")
            return None

    _service = build('gmail', 'v1', credentials=creds)
    return _service


def is_available():
    return os.path.exists(GMAIL_TOKEN_FILE)


def forward_email(gmail_message_id, to_email):
    service = _get_service()
    if not service:
        return {'success': False, 'error': 'Gmail service not available'}

    try:
        original = service.users().messages().get(
            userId='me', id=gmail_message_id, format='raw'
        ).execute()

        raw_bytes = base64.urlsafe_b64decode(original['raw'])
        orig_msg = email.message_from_bytes(raw_bytes)

        orig_subject = orig_msg.get('Subject', '(no subject)')
        fwd_subject = orig_subject if orig_subject.startswith('Fwd:') else f"Fwd: {orig_subject}"

        fwd_msg = MIMEMultipart('mixed')
        fwd_msg['To'] = to_email
        fwd_msg['Subject'] = fwd_subject

        body_text = ''
        attachments = []

        if orig_msg.is_multipart():
            for part in orig_msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))

                if 'attachment' in content_disposition:
                    attachments.append(part)
                elif content_type == 'text/plain' and not body_text:
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
                elif content_type == 'text/html' and not body_text:
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
        else:
            body_text = orig_msg.get_payload(decode=True).decode('utf-8', errors='replace')

        fwd_msg.attach(MIMEText(body_text, 'plain'))

        for att in attachments:
            fwd_msg.attach(att)

        encoded = base64.urlsafe_b64encode(fwd_msg.as_bytes()).decode('ascii')
        result = service.users().messages().send(
            userId='me',
            body={'raw': encoded}
        ).execute()

        logger.info(f"Forwarded email {gmail_message_id} to {to_email}, new msg id: {result['id']}")
        return {'success': True, 'message_id': result['id']}

    except Exception as e:
        logger.error(f"Failed to forward email {gmail_message_id} to {to_email}: {e}")
        return {'success': False, 'error': str(e)}
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt email_parser/config.py email_parser/auth_setup.py app/utils/gmail_forward.py
git commit -m "feat: add Gmail forwarding utility and update scopes"
```

---

### Task 3: Assignment Flow Integration + Resend Endpoint

Wire auto-forwarding into the assignment endpoint for TST jobs, add a resend endpoint, and add a job email-forwards query endpoint.

**Files:**
- Modify: `app/routes/assignments.py` (add forwarding logic to `assign_technicians_to_job`, add `resend_email` route, add `get_job_email_forwards` route)

**Interfaces:**
- Consumes: `EmailForward` model (Task 1), `forward_email()` and `is_available()` from `app/utils/gmail_forward` (Task 2)
- Produces:
  - Modified `POST /api/assignments/job/<id>` — response includes `email_forward_results: [{tech_id, tech_name, success, error, forwarded_to}]` for TST jobs (null for non-TST)
  - `POST /api/assignments/<id>/resend-email` — manager+, returns `{message, forward}` on success
  - `GET /api/assignments/job/<id>/email-forwards` — manager+, returns `{forwards: [...], total: int}`

- [ ] **Step 1: Add imports to `app/routes/assignments.py`**

Add to the existing import block at the top of `app/routes/assignments.py`:

```python
from app.models import Job, JobAssignment, Technician, User, SMSNotification, EmailParserLog, EmailForward
from app.utils import gmail_forward
```

(Replace the existing `from app.models import Job, JobAssignment, Technician, User, SMSNotification` line.)

- [ ] **Step 2: Create helper function for TST email forwarding**

Add this helper function after the imports, before the first route:

```python
def _forward_tst_email_for_assignment(job, assignment, technician):
    """Forward the original TST dispatch email to the assigned technician.
    Returns a result dict or None if not applicable."""
    if not job.ticket_number or not job.ticket_number.startswith('TST-'):
        return None

    if not technician.email:
        return {
            'tech_id': technician.tech_id,
            'tech_name': technician.name,
            'success': False,
            'error': 'No email on file',
            'forwarded_to': None,
        }

    if not gmail_forward.is_available():
        return {
            'tech_id': technician.tech_id,
            'tech_name': technician.name,
            'success': False,
            'error': 'Gmail service not configured',
            'forwarded_to': technician.email,
        }

    raw_ticket = job.ticket_number.replace('TST-', '', 1)
    log_entry = EmailParserLog.query.filter_by(
        platform='TST',
        email_type='service_order',
        ticket_number=raw_ticket,
        status='success',
    ).order_by(EmailParserLog.timestamp.desc()).first()

    if not log_entry or not log_entry.gmail_message_id:
        return {
            'tech_id': technician.tech_id,
            'tech_name': technician.name,
            'success': False,
            'error': 'No source email found',
            'forwarded_to': technician.email,
        }

    result = gmail_forward.forward_email(log_entry.gmail_message_id, technician.email)

    forward_record = EmailForward(
        job_id=job.job_id,
        tech_id=technician.tech_id,
        assignment_id=assignment.assignment_id,
        gmail_message_id=log_entry.gmail_message_id,
        forwarded_to=technician.email,
        status='sent' if result['success'] else 'failed',
        error_message=result.get('error'),
    )
    db.session.add(forward_record)

    return {
        'tech_id': technician.tech_id,
        'tech_name': technician.name,
        'success': result['success'],
        'error': result.get('error'),
        'forwarded_to': technician.email,
    }
```

- [ ] **Step 3: Integrate into `assign_technicians_to_job`**

In the `assign_technicians_to_job` function, add email forwarding after the SMS block. Find the line `created_assignments.append(assignment)` (line ~222) and the SMS block below it. After the SMS if-block (after line ~233), add:

```python
        # Auto-forward TST dispatch email
        fwd_result = _forward_tst_email_for_assignment(job, assignment, technician)
        if fwd_result:
            email_forward_results.append(fwd_result)
```

Also add `email_forward_results = []` next to the existing `sms_results = []` declaration (around line 164):

```python
    email_forward_results = []
```

Update the return jsonify at the end of the function to include forward results. Change:

```python
    return jsonify({
        'message': f'Created {len(created_assignments)} assignment(s)',
        'assignments': [a.to_dict() for a in created_assignments],
        'errors': errors,
        'sms_results': sms_results if send_sms else None,
        'job': job.to_dict()
    }), 201 if created_assignments else 400
```

to:

```python
    return jsonify({
        'message': f'Created {len(created_assignments)} assignment(s)',
        'assignments': [a.to_dict() for a in created_assignments],
        'errors': errors,
        'sms_results': sms_results if send_sms else None,
        'email_forward_results': email_forward_results if email_forward_results else None,
        'job': job.to_dict()
    }), 201 if created_assignments else 400
```

- [ ] **Step 4: Add resend-email endpoint**

Add after the existing `resend_sms_notification` route:

```python
@assignments_bp.route('/<int:assignment_id>/resend-email', methods=['POST'])
@manager_required
def resend_email_forward(assignment_id):
    """Resend TST dispatch email for an assignment. Manager+ only."""
    user = g.current_user
    assignment = JobAssignment.query.get_or_404(assignment_id)
    job = assignment.job
    technician = assignment.technician

    if not job or not technician:
        return jsonify({'error': 'Invalid assignment'}), 400

    result = _forward_tst_email_for_assignment(job, assignment, technician)
    if not result:
        return jsonify({'error': 'Not a TST job'}), 400

    db.session.commit()

    if result['success']:
        audit_logger.log(
            action_type='email_resent',
            entity_type='job_assignment',
            entity_id=assignment_id,
            new_values={'forwarded_to': result['forwarded_to']},
            description=f"Resent TST email for assignment {assignment_id}",
            user_id=user.user_id,
        )
        return jsonify({'message': 'Email forwarded successfully', 'forward': result}), 200
    else:
        return jsonify({'error': result.get('error', 'Failed to forward email'), 'forward': result}), 500
```

- [ ] **Step 5: Add job email-forwards list endpoint**

Add after the resend endpoint:

```python
@assignments_bp.route('/job/<int:job_id>/email-forwards', methods=['GET'])
@manager_required
def get_job_email_forwards(job_id):
    """Get all email forward records for a job. Manager+ only."""
    Job.query.get_or_404(job_id)
    forwards = EmailForward.query.filter_by(job_id=job_id)\
        .order_by(EmailForward.forwarded_at.desc()).all()
    return jsonify({
        'forwards': [f.to_dict() for f in forwards],
        'total': len(forwards),
    }), 200
```

- [ ] **Step 6: Commit**

```bash
git add app/routes/assignments.py
git commit -m "feat: auto-forward TST emails on tech assignment with resend endpoint"
```

---

### Task 4: Frontend — API Client + Assignment UI

Add the API methods and display email forward status in the job assignment table with a resend button.

**Files:**
- Modify: `app/static/js/api.js` (~line 640, after `resendAssignmentSms`)
- Modify: `app/static/js/app.js` (~line 1242-1270, assignment table in `jobModal`; ~line 1995, `saveJobAssignments` result handling)

**Interfaces:**
- Consumes: `POST /api/assignments/<id>/resend-email` (Task 3), `GET /api/assignments/job/<id>/email-forwards` (Task 3), `email_forward_results` in assignment response (Task 3)
- Produces: UI display of forward status badges, resend button, `Pages.resendJobEmail(assignmentId, jobId)` function

- [ ] **Step 1: Add API methods in `api.js`**

In `api.js`, add after the `resendAssignmentSms` method (after line 640):

```javascript
        async resendJobEmail(assignmentId) {
            return API.request(`/assignments/${assignmentId}/resend-email`, {
                method: 'POST'
            });
        },

        async getJobEmailForwards(jobId) {
            return API.request(`/assignments/job/${jobId}/email-forwards`);
        },
```

- [ ] **Step 2: Update assignment table in `jobModal` to show email forward status**

In `app.js`, find the assignment table header row (~line 1244-1249). Change:

```javascript
                                            <tr>
                                                <th>Technician</th>
                                                <th>Phone</th>
                                                <th>Status</th>
                                                <th>SMS</th>
                                                <th>Actions</th>
                                            </tr>
```

to:

```javascript
                                            <tr>
                                                <th>Technician</th>
                                                <th>Phone</th>
                                                <th>Status</th>
                                                <th>SMS</th>
                                                <th>Email</th>
                                                <th>Actions</th>
                                            </tr>
```

Then in the assignment row rendering (~line 1253-1269), find the existing row template. After the SMS `<td>` (after line ~1264) and before the Actions `<td>`, add an Email forward status column. Also update the Actions column to include a resend-email button.

Replace the entire `${assignments.map(a => {` block with:

```javascript
                                            ${assignments.map(a => {
                                                const smsStatusBadge = a.sms_sent_at
                                                    ? (a.sms_status === 'delivered' ? '<span class="badge badge-success">Delivered</span>'
                                                        : a.sms_status === 'failed' ? '<span class="badge badge-danger">Failed</span>'
                                                        : '<span class="badge badge-warning">Sent</span>')
                                                    : '<span class="badge badge-secondary">Not Sent</span>';

                                                const isTst = (job.ticket_number || '').startsWith('TST-');
                                                const fwd = (emailForwards || []).find(f => f.assignment_id === a.assignment_id);
                                                let emailBadge = '';
                                                if (isTst) {
                                                    if (fwd && fwd.status === 'sent') {
                                                        emailBadge = `<span class="badge badge-success" title="Forwarded ${fwd.forwarded_at || ''}">Sent</span>`;
                                                    } else if (fwd && fwd.status === 'failed') {
                                                        emailBadge = `<span class="badge badge-danger" title="${fwd.error_message || 'Failed'}">Failed</span>`;
                                                    } else {
                                                        emailBadge = '<span class="badge badge-secondary">Not Sent</span>';
                                                    }
                                                } else {
                                                    emailBadge = '<span class="text-muted">-</span>';
                                                }

                                                return `
                                                <tr>
                                                    <td>${a.tech_name}</td>
                                                    <td>${a.tech_phone || '-'}</td>
                                                    <td>${App.getStatusBadge(a.status)}</td>
                                                    <td>${smsStatusBadge}</td>
                                                    <td>${emailBadge}</td>
                                                    <td>
                                                        ${a.sms_status === 'failed' || !a.sms_sent_at ? `<button class="btn btn-sm btn-warning" onclick="Pages.resendAssignmentSms(${a.assignment_id}, ${jobId})">Resend SMS</button>` : ''}
                                                        ${isTst && (!fwd || fwd.status === 'failed') ? `<button class="btn btn-sm btn-info" onclick="Pages.resendJobEmail(${a.assignment_id}, ${jobId})">Send Email</button>` : ''}
                                                        <button class="btn btn-sm btn-danger" onclick="Pages.removeAssignment(${a.assignment_id}, ${jobId})">Remove</button>
                                                    </td>
                                                </tr>
                                            `}).join('')}
```

- [ ] **Step 3: Fetch email forwards when loading job modal**

In the `jobModal` function, after the assignments fetch block (~line 1231), add a fetch for email forwards. Find:

```javascript
                    const assignmentsData = await API.assignments.getJobAssignments(jobId);
                    const assignments = assignmentsData.assignments || [];
```

Add after it:

```javascript
                    let emailForwards = [];
                    if ((job.ticket_number || '').startsWith('TST-')) {
                        try {
                            const fwdData = await API.assignments.getJobEmailForwards(jobId);
                            emailForwards = fwdData.forwards || [];
                        } catch (e) {
                            console.error('Failed to load email forwards:', e);
                        }
                    }
```

- [ ] **Step 4: Add `resendJobEmail` function**

Add after the `resendAssignmentSms` function in `app.js`:

```javascript
    async resendJobEmail(assignmentId, jobId) {
        try {
            await API.assignments.resendJobEmail(assignmentId);
            App.showAlert('Job email forwarded successfully', 'success');
            App.hideModal();
            await Pages.viewJob(jobId);
        } catch (error) {
            App.showAlert(error.message || 'Failed to forward email');
        }
    },
```

- [ ] **Step 5: Show forward results after assignment**

In `saveJobAssignments` (~line 1995), after the success alert, add display of email forward results. Change:

```javascript
            const result = await API.assignments.assignTechnicians(jobId, techIds, sendSms, notes);
            App.showAlert(`Assigned ${result.assignments.length} technician(s)`, 'success');
```

to:

```javascript
            const result = await API.assignments.assignTechnicians(jobId, techIds, sendSms, notes);
            let alertMsg = `Assigned ${result.assignments.length} technician(s)`;
            if (result.email_forward_results) {
                const sent = result.email_forward_results.filter(r => r.success).length;
                const failed = result.email_forward_results.filter(r => !r.success).length;
                if (sent > 0) alertMsg += `, ${sent} email(s) forwarded`;
                if (failed > 0) alertMsg += `, ${failed} email forward(s) failed`;
            }
            App.showAlert(alertMsg, 'success');
```

- [ ] **Step 6: Commit**

```bash
git add app/static/js/api.js app/static/js/app.js
git commit -m "ui: show email forward status in job assignments with resend button"
```

---

### Task 5: Server Deployment + Gmail Re-Auth

Install dependencies on the server, re-auth Gmail with new scope, run migration, and deploy.

**Files:**
- No code files — server operations only

**Interfaces:**
- Consumes: All changes from Tasks 1-4
- Produces: Working auto-forward feature in production

- [ ] **Step 1: Push all changes to git**

```bash
git push origin main
```

- [ ] **Step 2: Deploy code to server**

```bash
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "cd /opt/work-tracking && sudo git pull origin main"
```

- [ ] **Step 3: Install Google API libraries in Flask app venv**

```bash
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "sudo /opt/work-tracking/venv/bin/pip install google-api-python-client google-auth google-auth-oauthlib"
```

Expected: packages install successfully.

- [ ] **Step 4: Run database migration**

```bash
scp -i ~/.ssh/gcp_work_tracking database/migrations/023_email_forwards.sql claude-code@34.27.146.58:/tmp/q.sql
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "sudo /tmp/dbrun.sh"
```

Expected: `email_forwards` table created.

- [ ] **Step 5: Re-auth Gmail with send scope (local)**

Run locally with `credentials.json` available:

```bash
cd email_parser
python auth_setup.py
```

This opens a browser for Google consent with the added `gmail.send` scope. Approve and save the new `token.json`.

- [ ] **Step 6: Upload new token to server**

```bash
scp -i ~/.ssh/gcp_work_tracking email_parser/token.json claude-code@34.27.146.58:/opt/email-parser/token.json
```

- [ ] **Step 7: Add GMAIL_TOKEN_FILE to Flask .env**

```bash
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "echo 'GMAIL_TOKEN_FILE=/opt/email-parser/token.json' | sudo tee -a /opt/work-tracking/.env"
```

- [ ] **Step 8: Restart both services**

```bash
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "sudo systemctl restart work-tracking && sudo systemctl restart email-parser"
```

- [ ] **Step 9: Verify services are running**

```bash
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58 "sudo systemctl status work-tracking --no-pager && sudo systemctl status email-parser --no-pager"
```

Expected: Both services active (running).

- [ ] **Step 10: Test end-to-end**

1. Open https://worktracking.sleepybear.tech
2. Find a TST job (ticket starts with `TST-`)
3. Assign a technician who has an email address
4. Verify the assignment response shows email forward results
5. Check the tech's email inbox for the forwarded dispatch email
6. In the job modal, verify the Email column shows "Sent" badge
7. Test the "Send Email" resend button on a failed or unsent forward
