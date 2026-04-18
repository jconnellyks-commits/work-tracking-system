# Hourly Billing & Job Reimbursables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-calculate billing for hourly jobs (rate x hours) and add reimbursable line items to jobs.

**Architecture:** Add `billing_rate` column to jobs and a `job_reimbursables` table. Recalculate `billing_amount` on hourly jobs whenever time entries change. Reimbursables are CRUD line items on jobs, added to tech pay as a separate line in the pay calculator (distributed by hours ratio).

**Tech Stack:** Flask + SQLAlchemy, MySQL, vanilla JS frontend

---

### Task 1: Database Migration

**Files:**
- Create: `database/migrations/015_add_billing_rate_and_reimbursables.sql`

- [ ] **Step 1: Create migration file**

```sql
-- 015: Add billing_rate to jobs, create job_reimbursables table

ALTER TABLE jobs ADD COLUMN billing_rate DECIMAL(10,2) DEFAULT NULL AFTER billing_type;

CREATE TABLE job_reimbursables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    category ENUM('travel','parts','misc') NOT NULL DEFAULT 'misc',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Set billing_rate for existing hourly job NV-04142601 ($4680 / 72 hrs = $65/hr)
UPDATE jobs SET billing_rate = 65.00 WHERE ticket_number = 'NV-04142601';
```

- [ ] **Step 2: Run migration on server**

```bash
# Copy migration to server and run
powershell -Command "scp -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' database/migrations/015_add_billing_rate_and_reimbursables.sql claude-code@34.27.146.58:/tmp/migration.sql"

powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 '/tmp/dbrun.sh < /tmp/migration.sql' 2>&1"
```

- [ ] **Step 3: Verify migration**

Write and run a query to confirm `billing_rate` column exists and NV-04142601 has rate=65:

```sql
SELECT ticket_number, billing_type, billing_rate, billing_amount
FROM jobs WHERE ticket_number = 'NV-04142601';

DESCRIBE job_reimbursables;
```

- [ ] **Step 4: Commit**

```bash
git add database/migrations/015_add_billing_rate_and_reimbursables.sql
git commit -m "feat: add billing_rate column and job_reimbursables table (migration 015)"
```

---

### Task 2: Model Changes

**Files:**
- Modify: `app/models.py:75-141` (Job model)
- Modify: `app/models.py` (add JobReimbursable model after Job class, ~line 142)

- [ ] **Step 1: Add `billing_rate` to Job model**

In `app/models.py`, add `billing_rate` column after `billing_type` (line 89), and add `reimbursables` relationship after `time_entries` (line 116). Also add `billing_rate` and `reimbursables` to `to_dict()`:

```python
# After line 89 (billing_type):
billing_rate = db.Column(db.Numeric(10, 2))

# After line 116 (time_entries relationship):
reimbursables = db.relationship('JobReimbursable', backref='job', lazy='dynamic', cascade='all, delete-orphan')
```

Update `to_dict()` to include `billing_rate` after `billing_type`:

```python
'billing_rate': float(self.billing_rate) if self.billing_rate else None,
```

- [ ] **Step 2: Add `recalculate_hourly_billing` method to Job**

Add this method to the Job class, after `to_dict()`:

```python
def recalculate_hourly_billing(self):
    """Recalculate billing_amount for hourly jobs based on rate x total hours."""
    if self.billing_type != 'hourly' or not self.billing_rate:
        return
    from sqlalchemy import func as sqlfunc
    total_hours = db.session.query(
        sqlfunc.coalesce(sqlfunc.sum(TimeEntry.hours_worked), 0)
    ).filter_by(job_id=self.job_id).scalar()
    self.billing_amount = self.billing_rate * total_hours
```

- [ ] **Step 3: Add `JobReimbursable` model**

Add this new model class right after the Job class (before PayPeriod):

```python
class JobReimbursable(db.Model):
    """Reimbursable line item on a job (travel, parts, misc)."""
    __tablename__ = 'job_reimbursables'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.Enum('travel', 'parts', 'misc'), nullable=False, default='misc')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'description': self.description,
            'amount': float(self.amount) if self.amount else 0,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
```

- [ ] **Step 4: Commit**

```bash
git add app/models.py
git commit -m "feat: add billing_rate, JobReimbursable model, and recalculate_hourly_billing"
```

---

### Task 3: Job API Changes

**Files:**
- Modify: `app/routes/jobs.py:111-215` (create_job)
- Modify: `app/routes/jobs.py:218-291` (update_job)
- Modify: `app/routes/jobs.py:92-108` (get_job)
- Modify: `app/routes/jobs.py` (add reimbursable CRUD endpoints)

- [ ] **Step 1: Update imports**

At the top of `app/routes/jobs.py`, add `JobReimbursable` to the model import:

```python
from app.models import Job, Platform, TimeEntry, JobReimbursable
```

- [ ] **Step 2: Update `create_job` to handle `billing_rate`**

In `create_job()`, after line 163 (`billing_amount = data.get('billing_amount') or None`), add:

```python
billing_rate = data.get('billing_rate') or None
```

In the `Job(...)` constructor (around line 179-197), add `billing_rate=billing_rate` after `billing_type`.

For hourly jobs, ignore the billing_amount from the request (it'll be 0 until time entries are added). After `db.session.add(job)` and before `db.session.commit()`, add:

```python
# For hourly jobs, billing_amount starts at 0 (calculated from time entries)
if data.get('billing_type') == 'hourly':
    job.billing_amount = 0
```

- [ ] **Step 3: Update `update_job` to handle `billing_rate`**

In `update_job()`, add `'billing_rate'` to the `updatable_fields` list (line 237-240).

After the main field update loop (after line 248), add logic to recalculate if billing type or rate changed:

```python
# Recalculate billing for hourly jobs
if job.billing_type == 'hourly':
    job.recalculate_hourly_billing()
```

This handles: changing rate, changing type to hourly, etc. If the job is not hourly, `billing_amount` is set directly by the updatable_fields loop.

- [ ] **Step 4: Update `get_job` to include reimbursables**

In `get_job()` (line 92-108), after `job_data['total_hours_worked'] = total_hours`, add:

```python
reimbursables = JobReimbursable.query.filter_by(job_id=job_id).order_by(JobReimbursable.created_at).all()
job_data['reimbursables'] = [r.to_dict() for r in reimbursables]
job_data['reimbursables_total'] = sum(float(r.amount) for r in reimbursables)
```

- [ ] **Step 5: Add reimbursable CRUD endpoints**

Add these two endpoints at the end of `jobs.py` (before the final closing of the file):

```python
@jobs_bp.route('/<int:job_id>/reimbursables', methods=['POST'])
@manager_required
@log_action('create', 'reimbursable')
def add_reimbursable(job_id):
    """Add a reimbursable line item to a job."""
    job = Job.query.get_or_404(job_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    description = (data.get('description') or '').strip()
    amount = data.get('amount')
    category = data.get('category', 'misc')

    if not description:
        return jsonify({'error': 'Description required'}), 400
    if not amount or float(amount) <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    if category not in ('travel', 'parts', 'misc'):
        return jsonify({'error': 'Category must be travel, parts, or misc'}), 400

    reimbursable = JobReimbursable(
        job_id=job_id,
        description=description,
        amount=amount,
        category=category
    )

    db.session.add(reimbursable)
    db.session.commit()

    audit_logger.log(
        action_type='reimbursable_added',
        entity_type='job',
        entity_id=job_id,
        new_values=reimbursable.to_dict(),
        description=f"Reimbursable '{description}' added to job {job.ticket_number}",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Reimbursable added',
        'reimbursable': reimbursable.to_dict()
    }), 201


@jobs_bp.route('/<int:job_id>/reimbursables/<int:reimbursable_id>', methods=['DELETE'])
@manager_required
@log_action('delete', 'reimbursable')
def delete_reimbursable(job_id, reimbursable_id):
    """Remove a reimbursable line item from a job."""
    job = Job.query.get_or_404(job_id)
    reimbursable = JobReimbursable.query.filter_by(id=reimbursable_id, job_id=job_id).first_or_404()

    old_values = reimbursable.to_dict()
    db.session.delete(reimbursable)
    db.session.commit()

    audit_logger.log(
        action_type='reimbursable_deleted',
        entity_type='job',
        entity_id=job_id,
        old_values=old_values,
        description=f"Reimbursable removed from job {job.ticket_number}",
        user_id=g.user_id
    )

    return jsonify({'message': 'Reimbursable removed'}), 200
```

- [ ] **Step 6: Commit**

```bash
git add app/routes/jobs.py
git commit -m "feat: add billing_rate handling and reimbursable CRUD endpoints to jobs API"
```

---

### Task 4: Time Entry Recalculation Hooks

**Files:**
- Modify: `app/routes/time_entries.py:165-272` (create_time_entry)
- Modify: `app/routes/time_entries.py:278-351` (update_time_entry)
- Modify: `app/routes/time_entries.py:356-383` (delete_time_entry)

- [ ] **Step 1: Add recalculation to `create_time_entry`**

In `create_time_entry()`, after `db.session.add(entry)` (line 256) and before `db.session.commit()` (line 257), add:

```python
# Recalculate billing for hourly jobs
job.recalculate_hourly_billing()
```

This is safe for non-hourly jobs — the method returns immediately if `billing_type != 'hourly'`.

- [ ] **Step 2: Add recalculation to `update_time_entry`**

In `update_time_entry()`, before `db.session.commit()` (line 337), add:

```python
# Recalculate billing for hourly jobs
job = Job.query.get(entry.job_id)
if job:
    job.recalculate_hourly_billing()
```

Also handle the case where `job_id` changed — need to recalculate both old and new jobs. Replace the above with:

```python
# Recalculate billing for hourly jobs (handle job_id change)
old_job_id = old_values.get('job_id')
if old_job_id and old_job_id != entry.job_id:
    old_job = Job.query.get(old_job_id)
    if old_job:
        old_job.recalculate_hourly_billing()
current_job = Job.query.get(entry.job_id)
if current_job:
    current_job.recalculate_hourly_billing()
```

- [ ] **Step 3: Add recalculation to `delete_time_entry`**

In `delete_time_entry()`, save the job_id before deletion. Before `db.session.delete(entry)` (line 372), add:

```python
job_id_for_recalc = entry.job_id
```

After `db.session.commit()` (line 373), add:

```python
# Recalculate billing for hourly jobs
job = Job.query.get(job_id_for_recalc)
if job:
    job.recalculate_hourly_billing()
    db.session.commit()
```

- [ ] **Step 4: Commit**

```bash
git add app/routes/time_entries.py
git commit -m "feat: recalculate hourly billing on time entry create/update/delete"
```

---

### Task 5: Pay Calculator — Add Reimbursables to Tech Pay

**Files:**
- Modify: `app/utils/pay_calculator.py:29-225` (calculate_job_pay)

- [ ] **Step 1: Import JobReimbursable**

Update the import line (line 26):

```python
from app.models import Job, TimeEntry, Technician, MileageRateHistory, PayPeriod, JobReimbursable
```

- [ ] **Step 2: Query reimbursables and add to tech pay**

In `calculate_job_pay()`, after the total_deductions calculation (after line 133, `total_deductions = total_mileage_pay + total_per_diem + total_personal_expenses`), add:

```python
# Get reimbursables for this job
reimbursables = JobReimbursable.query.filter_by(job_id=job_id).all()
total_reimbursables = sum(Decimal(str(r.amount)) for r in reimbursables)
```

In the per-tech loop (around line 191, where `total_pay` is calculated), add the reimbursable share. Replace the `total_pay` line:

```python
# old:
# total_pay = base_pay + data['mileage_pay'] + data['per_diem'] + data['personal_expenses']

# new — add reimbursable share (distributed by hours ratio)
if total_hours > 0 and total_reimbursables > 0:
    reimbursable_share = total_reimbursables * (data['hours'] / total_hours)
else:
    reimbursable_share = Decimal('0')

total_pay = base_pay + data['mileage_pay'] + data['per_diem'] + data['personal_expenses'] + reimbursable_share
```

In the technician dict that gets appended (around line 194-208), add:

```python
'reimbursable_share': float(reimbursable_share.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
```

- [ ] **Step 3: Update totals dict**

In the return dict's `totals` section (line 217-224), add `total_reimbursables` and update `total_pay`:

```python
'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
'total_pay': float((total_base_pay + total_mileage_pay + total_per_diem + total_personal_expenses + total_reimbursables).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
```

Also add at the top-level return (alongside `job_net`, `tech_pool`, etc.):

```python
'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
'reimbursables': [r.to_dict() for r in reimbursables],
```

- [ ] **Step 4: Commit**

```bash
git add app/utils/pay_calculator.py
git commit -m "feat: add reimbursable share to tech pay calculation"
```

---

### Task 6: Frontend — Job Form Billing Type Toggle

**Files:**
- Modify: `app/static/js/app.js:1083-1160` (job modal form section)

- [ ] **Step 1: Update billing section in edit mode**

In the job modal, replace the billing amount section (lines 1130-1140):

```javascript
// OLD (lines 1130-1140):
            <div class="form-row">
                ${field('Status', App.getStatusBadge(job.job_status), statusSelect)}
                ${editing
                    ? field('Billing Type', '', billingSelect)
                    : `<div class="form-group"><label>Billing</label><p>${job.billing_type || 'flat_rate'}: $${job.billing_amount || 0}</p></div>`}
            </div>
            ${editing ? `<div class="form-row">
                ${field('Billing Amount', '',
                    `<input type="number" step="0.01" class="form-control" name="billing_amount" value="${job.billing_amount || ''}">`)}
                <div class="form-group"></div>
            </div>` : ''}

// NEW:
            <div class="form-row">
                ${field('Status', App.getStatusBadge(job.job_status), statusSelect)}
                ${editing
                    ? field('Billing Type', '', billingSelect)
                    : `<div class="form-group"><label>Billing</label><p>${
                        job.billing_type === 'hourly' && job.billing_rate
                            ? `hourly @ $${job.billing_rate.toFixed(2)}/hr = $${(job.billing_amount || 0).toFixed(2)} (${entriesData.total_hours || 0} hrs)`
                            : `${job.billing_type || 'flat_rate'}: $${job.billing_amount || 0}`
                    }</p></div>`}
            </div>
            ${editing ? `<div class="form-row">
                <div class="form-group billing-rate-group" style="display: ${job.billing_type === 'hourly' ? 'block' : 'none'}">
                    <label>Billing Rate ($/hr)</label>
                    <input type="number" step="0.01" class="form-control" name="billing_rate" value="${job.billing_rate || ''}">
                </div>
                <div class="form-group billing-amount-group">
                    <label>Billing Amount${job.billing_type === 'hourly' ? ' (calculated)' : ''}</label>
                    <input type="number" step="0.01" class="form-control" name="billing_amount" value="${job.billing_amount || ''}" ${job.billing_type === 'hourly' ? 'readonly style="background: #e9ecef;"' : ''}>
                </div>
            </div>` : ''}
```

- [ ] **Step 2: Add billing type change handler**

After the modal is shown (the `App.showModal(...)` call at the end of `jobModal`), add an event listener. Find where the modal body is set and add after it:

```javascript
// After App.showModal call, add billing type toggle
setTimeout(() => {
    const billingTypeSelect = document.querySelector('[name="billing_type"]');
    if (billingTypeSelect) {
        billingTypeSelect.addEventListener('change', function() {
            const isHourly = this.value === 'hourly';
            const rateGroup = document.querySelector('.billing-rate-group');
            const amountInput = document.querySelector('[name="billing_amount"]');
            const amountLabel = amountInput?.closest('.form-group')?.querySelector('label');
            if (rateGroup) rateGroup.style.display = isHourly ? 'block' : 'none';
            if (amountInput) {
                amountInput.readOnly = isHourly;
                amountInput.style.background = isHourly ? '#e9ecef' : '';
                if (isHourly) amountInput.value = '0';
            }
            if (amountLabel) amountLabel.textContent = isHourly ? 'Billing Amount (calculated)' : 'Billing Amount';
        });
    }
}, 100);
```

- [ ] **Step 3: Update `saveJob` to include `billing_rate`**

The existing `saveJob` function (line 1194) already uses `Object.fromEntries(formData)` which will automatically include the `billing_rate` field since it's a named input in the form. No changes needed here — the form data will naturally include `billing_rate`.

However, for hourly jobs we should not send `billing_amount` (it's calculated server-side). Update `saveJob`:

```javascript
async saveJob(jobId) {
    const form = document.getElementById('job-form');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    // Don't send billing_amount for hourly jobs (it's auto-calculated)
    if (data.billing_type === 'hourly') {
        delete data.billing_amount;
    }

    try {
        if (jobId) {
            await API.jobs.update(jobId, data);
            App.showAlert('Job updated successfully', 'success');
            await Pages.jobModal(jobId, 'view');
        } else {
            await API.jobs.create(data);
            App.showAlert('Job created successfully', 'success');
            App.hideModal();
        }
        if (Pages.jobsPage) Pages.jobsPage(1);
    } catch (error) {
        App.showFormError(error.message);
    }
},
```

- [ ] **Step 4: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add billing type toggle and rate field in job form"
```

---

### Task 7: Frontend — Reimbursables Section on Job Detail

**Files:**
- Modify: `app/static/js/app.js:1083-1160` (job modal, view mode)
- Modify: `app/static/js/api.js` (add reimbursable API methods)

- [ ] **Step 1: Add reimbursable API methods**

In `app/static/js/api.js`, find the `jobs` section and add reimbursable methods:

```javascript
// Inside the jobs API object, add:
addReimbursable: (jobId, data) => apiCall(`/api/jobs/${jobId}/reimbursables`, { method: 'POST', body: JSON.stringify(data) }),
deleteReimbursable: (jobId, id) => apiCall(`/api/jobs/${jobId}/reimbursables/${id}`, { method: 'DELETE' }),
```

- [ ] **Step 2: Add reimbursables section to job modal view mode**

In `app/static/js/app.js`, in the job modal body (around line 1155, after the expenses/commissions form-row and before `${formClose}`), add the reimbursables section. This should only show in view mode (not when editing job fields) and for non-new jobs:

```javascript
${!isNew && !editing ? (() => {
    const reimbursables = entriesData.reimbursables || [];
    const total = entriesData.reimbursables_total || 0;
    const isManager = ['admin', 'manager'].includes(App.user.role);
    return `
        <div style="margin-top: 1rem; border-top: 1px solid #eee; padding-top: 1rem;">
            <label style="display: flex; justify-content: space-between; align-items: center;">
                Reimbursables
                ${isManager ? `<button class="btn btn-sm btn-outline-primary" onclick="Pages.addReimbursable(${jobId})"><i class="fas fa-plus"></i> Add</button>` : ''}
            </label>
            ${reimbursables.length > 0 ? `
                <table class="table table-sm" style="margin-top: 0.5rem;">
                    <thead><tr><th>Description</th><th>Category</th><th style="text-align:right">Amount</th>${isManager ? '<th></th>' : ''}</tr></thead>
                    <tbody>
                        ${reimbursables.map(r => `<tr>
                            <td>${r.description}</td>
                            <td><span class="badge badge-secondary">${r.category}</span></td>
                            <td style="text-align:right">$${r.amount.toFixed(2)}</td>
                            ${isManager ? `<td><button class="btn btn-sm btn-outline-danger" onclick="Pages.deleteReimbursable(${jobId}, ${r.id})"><i class="fas fa-trash"></i></button></td>` : ''}
                        </tr>`).join('')}
                    </tbody>
                    <tfoot><tr><td colspan="2"><strong>Total</strong></td><td style="text-align:right"><strong>$${total.toFixed(2)}</strong></td>${isManager ? '<td></td>' : ''}</tr></tfoot>
                </table>
            ` : '<p class="text-muted" style="margin-top: 0.5rem;">No reimbursable items</p>'}
        </div>
    `;
})() : ''}
```

Note: `entriesData` comes from the `get_job` API response which now includes `reimbursables` and `reimbursables_total` (from Task 3 Step 4).

- [ ] **Step 3: Add reimbursable action functions**

Add these functions to the `Pages` object:

```javascript
async addReimbursable(jobId) {
    const body = `
        <form id="reimbursable-form">
            <div class="form-group">
                <label>Description *</label>
                <input type="text" class="form-control" name="description" required placeholder="e.g. Hotel, Cable, Gas">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Amount *</label>
                    <input type="number" step="0.01" min="0.01" class="form-control" name="amount" required>
                </div>
                <div class="form-group">
                    <label>Category</label>
                    <select class="form-control" name="category">
                        <option value="travel">Travel</option>
                        <option value="parts">Parts</option>
                        <option value="misc" selected>Misc</option>
                    </select>
                </div>
            </div>
        </form>
    `;

    App.showModal('Add Reimbursable', body, '', `
        <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
        <button class="btn btn-primary" onclick="Pages.saveReimbursable(${jobId})">Add</button>
    `);
},

async saveReimbursable(jobId) {
    const form = document.getElementById('reimbursable-form');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    try {
        await API.jobs.addReimbursable(jobId, data);
        App.showAlert('Reimbursable added', 'success');
        await Pages.jobModal(jobId, 'view');
    } catch (error) {
        App.showFormError(error.message);
    }
},

async deleteReimbursable(jobId, reimbursableId) {
    if (!confirm('Remove this reimbursable item?')) return;
    try {
        await API.jobs.deleteReimbursable(jobId, reimbursableId);
        App.showAlert('Reimbursable removed', 'success');
        await Pages.jobModal(jobId, 'view');
    } catch (error) {
        App.showAlert(error.message, 'danger');
    }
},
```

- [ ] **Step 4: Commit**

```bash
git add app/static/js/app.js app/static/js/api.js
git commit -m "feat: add reimbursables section to job detail view with add/delete"
```

---

### Task 8: Deploy and Verify

**Files:** None (deployment task)

- [ ] **Step 1: Push to remote**

```bash
git push origin main
```

- [ ] **Step 2: Deploy to server**

```bash
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'cd /opt/work-tracking && sudo git pull origin main && sudo systemctl restart work-tracking' 2>&1"
```

- [ ] **Step 3: Verify in browser**

Open https://worktracking.sleepybear.tech and test:

1. **View NV-04142601**: should show "hourly @ $65.00/hr = $4,680.00 (72 hrs)"
2. **Edit a job**: change billing type to hourly — rate field appears, amount becomes read-only
3. **Add a time entry to NV-04142601**: verify billing_amount updates
4. **Add a reimbursable item**: verify it appears in the job detail, with delete button
5. **Check payroll report**: verify reimbursable share shows for techs on jobs with reimbursables
