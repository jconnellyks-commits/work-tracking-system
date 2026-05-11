# Job Bundling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow grouping related jobs into bundles that pool financials for fairer pay calculation across same-site and route scenarios.

**Architecture:** New `JobBundle` model with `bundle_id` FK on `jobs` and `time_entries`. Pay calculator gets a `calculate_bundle_pay()` function and `calculate_period_pay()` merges bundled jobs into single virtual units. API follows existing blueprint pattern (`app/routes/bundles.py`). Frontend adds bundle management to the jobs page and bundle selection to the time entry form.

**Tech Stack:** Flask, SQLAlchemy, MySQL, vanilla JavaScript SPA

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `database/migrations/017_job_bundles.sql` | Create | Migration: `job_bundles` table, `bundle_id` on `jobs` and `time_entries`, make `job_id` nullable |
| `app/models.py` | Modify | Add `JobBundle` model, add `bundle_id` FK to `Job` and `TimeEntry`, update `to_dict()` methods |
| `app/routes/bundles.py` | Create | Bundle CRUD + membership endpoints |
| `app/__init__.py` | Modify | Register bundles blueprint |
| `app/utils/pay_calculator.py` | Modify | Add `calculate_bundle_pay()`, update `calculate_period_pay()` to merge bundled jobs |
| `app/routes/time_entries.py` | Modify | Accept `bundle_id` in create/update, relax `job_id` requirement |
| `app/static/js/api.js` | Modify | Add `API.bundles` namespace |
| `app/static/js/app.js` | Modify | Bundle management UI on jobs page, bundle dropdown in time entry form, bundle indicators in reports |

---

### Task 1: Database Migration

**Files:**
- Create: `database/migrations/017_job_bundles.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- Job bundles table
CREATE TABLE IF NOT EXISTS job_bundles (
    bundle_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NULL,
    status ENUM('active', 'closed') NOT NULL DEFAULT 'active',
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Add bundle_id to jobs
ALTER TABLE jobs ADD COLUMN bundle_id INT NULL,
    ADD CONSTRAINT fk_jobs_bundle FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id) ON DELETE SET NULL,
    ADD INDEX idx_jobs_bundle (bundle_id);

-- Add bundle_id to time_entries, make job_id nullable
ALTER TABLE time_entries ADD COLUMN bundle_id INT NULL,
    ADD CONSTRAINT fk_time_entries_bundle FOREIGN KEY (bundle_id) REFERENCES job_bundles(bundle_id) ON DELETE SET NULL,
    ADD INDEX idx_time_entries_bundle (bundle_id);

ALTER TABLE time_entries MODIFY COLUMN job_id INT NULL;
```

- [ ] **Step 2: Deploy migration to server**

```bash
# SCP the file to server
powershell -Command "scp -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' 'database/migrations/017_job_bundles.sql' claude-code@34.27.146.58:/tmp/017_job_bundles.sql"

# Run via dbrun.sh
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 '/tmp/dbrun.sh /tmp/017_job_bundles.sql' 2>&1"
```

- [ ] **Step 3: Commit**

```bash
git add database/migrations/017_job_bundles.sql
git commit -m "feat: add job_bundles migration (017)"
```

---

### Task 2: JobBundle Model + Update Existing Models

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Add `JobBundle` model class after `JobReimbursable` (around line 182)**

Add this class to `app/models.py` after the `JobReimbursable` class:

```python
class JobBundle(db.Model):
    """Bundle of related jobs for pooled pay calculation."""
    __tablename__ = 'job_bundles'

    bundle_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.Enum('active', 'closed'), default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs = db.relationship('Job', backref='bundle', lazy='dynamic')
    time_entries = db.relationship('TimeEntry', backref='bundle', lazy='dynamic')
    created_by_user = db.relationship('User', foreign_keys=[created_by])

    @property
    def display_name(self):
        if self.name:
            return self.name
        first_job = self.jobs.order_by(Job.job_id).first()
        if first_job:
            return f"{first_job.description} Bundle"
        return f"Bundle #{self.bundle_id}"

    def to_dict(self):
        jobs_list = self.jobs.all()
        return {
            'bundle_id': self.bundle_id,
            'name': self.name,
            'display_name': self.display_name,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'job_count': len(jobs_list),
            'job_ids': [j.job_id for j in jobs_list],
        }
```

- [ ] **Step 2: Add `bundle_id` FK to `Job` model**

In the `Job` class, after the `external_url` column (around line 99), add:

```python
    bundle_id = db.Column(db.Integer, db.ForeignKey('job_bundles.bundle_id'), nullable=True)
```

- [ ] **Step 3: Add `bundle_id` and `bundle_name` to `Job.to_dict()`**

In `Job.to_dict()`, add these two entries after `'external_url'`:

```python
            'bundle_id': self.bundle_id,
            'bundle_name': self.bundle.display_name if self.bundle else None,
```

- [ ] **Step 4: Add `bundle_id` FK to `TimeEntry` model**

In the `TimeEntry` class, after `period_id` (around line 219), add:

```python
    bundle_id = db.Column(db.Integer, db.ForeignKey('job_bundles.bundle_id'), nullable=True)
```

- [ ] **Step 5: Make `job_id` nullable on `TimeEntry`**

Change line 217 from:

```python
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'), nullable=False)
```

to:

```python
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'), nullable=True)
```

- [ ] **Step 6: Add `bundle_id` and `bundle_name` to `TimeEntry.to_dict()`**

In `TimeEntry.to_dict()`, add after `'external_url'`:

```python
            'bundle_id': self.bundle_id,
            'bundle_name': self.bundle.display_name if self.bundle else None,
```

- [ ] **Step 7: Commit**

```bash
git add app/models.py
git commit -m "feat: add JobBundle model, bundle_id FK on Job and TimeEntry"
```

---

### Task 3: Bundle API Routes

**Files:**
- Create: `app/routes/bundles.py`
- Modify: `app/__init__.py`

- [ ] **Step 1: Create `app/routes/bundles.py`**

```python
"""
Job bundle routes for creating, managing, and querying job bundles.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import JobBundle, Job, TimeEntry
from app.utils.logging import get_logger, audit_logger, log_action
from app.utils.auth import jwt_required_with_user, manager_required

bundles_bp = Blueprint('bundles', __name__)
logger = get_logger(__name__)


@bundles_bp.route('', methods=['GET'])
@jwt_required_with_user
def list_bundles():
    status = request.args.get('status')
    search = request.args.get('search', '').strip()

    query = JobBundle.query
    if status:
        query = query.filter(JobBundle.status == status)

    bundles = query.order_by(JobBundle.created_at.desc()).all()

    result = []
    for b in bundles:
        d = b.to_dict()
        if search and search.lower() not in d['display_name'].lower():
            continue
        result.append(d)

    return jsonify({'bundles': result}), 200


@bundles_bp.route('/<int:bundle_id>', methods=['GET'])
@jwt_required_with_user
def get_bundle(bundle_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    bundle_data = bundle.to_dict()
    bundle_data['jobs'] = [j.to_dict() for j in bundle.jobs.all()]
    return jsonify({'bundle': bundle_data}), 200


@bundles_bp.route('', methods=['POST'])
@manager_required
@log_action('create', 'bundle')
def create_bundle():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    job_ids = data.get('job_ids', [])
    if not job_ids:
        return jsonify({'error': 'At least one job_id required'}), 400

    # Validate jobs exist and aren't already bundled
    jobs = []
    for jid in job_ids:
        job = Job.query.get(jid)
        if not job:
            return jsonify({'error': f'Job {jid} not found'}), 404
        if job.bundle_id:
            return jsonify({'error': f'Job {job.ticket_number or jid} already belongs to a bundle'}), 409
        jobs.append(job)

    bundle = JobBundle(
        name=data.get('name', '').strip() or None,
        created_by=g.user_id,
    )
    db.session.add(bundle)
    db.session.flush()

    for job in jobs:
        job.bundle_id = bundle.bundle_id

    db.session.commit()

    logger.info(f"Bundle created: {bundle.bundle_id} with {len(jobs)} jobs")
    audit_logger.log(
        action_type='bundle_created',
        entity_type='bundle',
        entity_id=bundle.bundle_id,
        new_values=bundle.to_dict(),
        description=f"Bundle '{bundle.display_name}' created with {len(jobs)} jobs",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Bundle created successfully',
        'bundle': bundle.to_dict()
    }), 201


@bundles_bp.route('/<int:bundle_id>', methods=['PUT'])
@manager_required
@log_action('update', 'bundle')
def update_bundle(bundle_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = bundle.to_dict()

    if 'name' in data:
        bundle.name = data['name'].strip() or None
    if 'status' in data and data['status'] in ('active', 'closed'):
        bundle.status = data['status']

    db.session.commit()

    audit_logger.log(
        action_type='bundle_updated',
        entity_type='bundle',
        entity_id=bundle.bundle_id,
        old_values=old_values,
        new_values=bundle.to_dict(),
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Bundle updated',
        'bundle': bundle.to_dict()
    }), 200


@bundles_bp.route('/<int:bundle_id>', methods=['DELETE'])
@manager_required
@log_action('delete', 'bundle')
def delete_bundle(bundle_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    old_values = bundle.to_dict()

    # Unlink all jobs
    for job in bundle.jobs.all():
        job.bundle_id = None

    # Unlink bundle-only time entries (leave them, just clear bundle_id)
    for entry in bundle.time_entries.all():
        entry.bundle_id = None

    db.session.delete(bundle)
    db.session.commit()

    audit_logger.log(
        action_type='bundle_deleted',
        entity_type='bundle',
        entity_id=bundle_id,
        old_values=old_values,
        description=f"Bundle '{old_values['display_name']}' deleted",
        user_id=g.user_id
    )

    return jsonify({'message': 'Bundle deleted, jobs unlinked'}), 200


@bundles_bp.route('/<int:bundle_id>/jobs', methods=['POST'])
@manager_required
@log_action('update', 'bundle')
def add_jobs_to_bundle(bundle_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    data = request.get_json()
    if not data or 'job_ids' not in data:
        return jsonify({'error': 'job_ids required'}), 400

    added = []
    errors = []
    for jid in data['job_ids']:
        job = Job.query.get(jid)
        if not job:
            errors.append({'job_id': jid, 'error': 'Not found'})
            continue
        if job.bundle_id and job.bundle_id != bundle_id:
            errors.append({'job_id': jid, 'error': 'Already in another bundle'})
            continue
        if job.bundle_id == bundle_id:
            continue
        job.bundle_id = bundle_id
        added.append(jid)

    db.session.commit()

    return jsonify({
        'message': f'Added {len(added)} jobs to bundle',
        'added': added,
        'errors': errors,
        'bundle': bundle.to_dict()
    }), 200


@bundles_bp.route('/<int:bundle_id>/jobs/<int:job_id>', methods=['DELETE'])
@manager_required
@log_action('update', 'bundle')
def remove_job_from_bundle(bundle_id, job_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    job = Job.query.get_or_404(job_id)

    if job.bundle_id != bundle_id:
        return jsonify({'error': 'Job is not in this bundle'}), 400

    job.bundle_id = None
    db.session.commit()

    remaining = bundle.jobs.count()
    if remaining == 0:
        db.session.delete(bundle)
        db.session.commit()
        return jsonify({'message': 'Job removed; bundle deleted (no jobs left)'}), 200

    return jsonify({
        'message': 'Job removed from bundle',
        'bundle': bundle.to_dict()
    }), 200
```

- [ ] **Step 2: Register the blueprint in `app/__init__.py`**

In `app/__init__.py`, add after the `email_parser_bp` import (around line 77):

```python
    from app.routes.bundles import bundles_bp
```

And add after the `email_parser_bp` registration (around line 92):

```python
    app.register_blueprint(bundles_bp, url_prefix='/api/bundles')
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/bundles.py app/__init__.py
git commit -m "feat: add bundle CRUD and membership API endpoints"
```

---

### Task 4: Pay Calculator — Bundle Support

**Files:**
- Modify: `app/utils/pay_calculator.py`

- [ ] **Step 1: Add `calculate_bundle_pay()` function**

Add this function after `calculate_job_pay()` (after line 242):

```python
def calculate_bundle_pay(bundle_id):
    """
    Calculate pay for all technicians across a job bundle.
    Pools billing/expenses/commissions from all jobs, gathers all
    time entries (job-level and bundle-level), then applies the
    standard tech pool formula.
    """
    from app.models import JobBundle
    bundle = JobBundle.query.get(bundle_id)
    if not bundle:
        return None

    jobs = bundle.jobs.all()
    if not jobs:
        return {
            'bundle': bundle.to_dict(),
            'jobs': [],
            'job_net': 0,
            'tech_pool': 0,
            'total_deductions': 0,
            'total_reimbursables': 0,
            'reimbursables': [],
            'technicians': [],
            'totals': {
                'total_hours': 0, 'total_base_pay': 0, 'total_mileage_pay': 0,
                'total_per_diem': 0, 'total_personal_expenses': 0,
                'total_reimbursables': 0, 'total_pay': 0
            }
        }

    # Pool financials across all jobs
    billing_amount = sum(Decimal(str(j.billing_amount or 0)) for j in jobs)
    expenses = sum(Decimal(str(j.expenses or 0)) for j in jobs)
    commissions = sum(Decimal(str(j.commissions or 0)) for j in jobs)
    job_net = billing_amount - expenses - commissions

    # Gather ALL time entries: on bundled jobs + directly on the bundle
    job_ids = [j.job_id for j in jobs]
    entries = TimeEntry.query.filter(
        db.or_(
            TimeEntry.job_id.in_(job_ids),
            TimeEntry.bundle_id == bundle_id
        )
    ).all()

    if not entries:
        return {
            'bundle': bundle.to_dict(),
            'jobs': [j.to_dict() for j in jobs],
            'job_net': float(job_net),
            'tech_pool': 0,
            'total_deductions': 0,
            'total_reimbursables': 0,
            'reimbursables': [],
            'technicians': [],
            'totals': {
                'total_hours': 0, 'total_base_pay': 0, 'total_mileage_pay': 0,
                'total_per_diem': 0, 'total_personal_expenses': 0,
                'total_reimbursables': 0, 'total_pay': 0
            }
        }

    # Gather reimbursables from all jobs
    all_reimbursables = []
    for j in jobs:
        all_reimbursables.extend(JobReimbursable.query.filter_by(job_id=j.job_id).all())
    total_reimbursables = sum((Decimal(str(r.amount)) for r in all_reimbursables), Decimal('0'))

    # Group entries by technician
    tech_data = {}
    for entry in entries:
        tech_id = entry.tech_id
        if tech_id not in tech_data:
            tech = Technician.query.get(tech_id)
            tech_data[tech_id] = {
                'tech_id': tech_id,
                'tech_name': tech.name if tech else f'Tech #{tech_id}',
                'min_pay': Decimal(str(tech.hourly_rate or 0)) if tech else Decimal('0'),
                'hours': Decimal('0'),
                'mileage': Decimal('0'),
                'per_diem': Decimal('0'),
                'personal_expenses': Decimal('0'),
                'entries': []
            }

        mileage_rate = MileageRateHistory.get_rate_for_date(entry.date_worked)
        entry_data = entry.to_dict()
        entry_data['mileage_rate'] = mileage_rate
        entry_data['mileage_pay'] = float(Decimal(str(entry.mileage or 0)) * Decimal(str(mileage_rate)))

        tech_data[tech_id]['entries'].append(entry_data)
        tech_data[tech_id]['hours'] += Decimal(str(entry.hours_worked or 0))
        tech_data[tech_id]['mileage'] += Decimal(str(entry.mileage or 0))
        tech_data[tech_id]['per_diem'] += Decimal(str(entry.per_diem or 0))
        tech_data[tech_id]['personal_expenses'] += Decimal(str(entry.personal_expenses or 0))

    # Calculate total deductions
    total_mileage_pay = Decimal('0')
    total_per_diem = Decimal('0')
    total_personal_expenses = Decimal('0')

    for tech_id, data in tech_data.items():
        mileage_pay = Decimal('0')
        for entry in data['entries']:
            mileage_pay += Decimal(str(entry['mileage_pay']))
        data['mileage_pay'] = mileage_pay
        total_mileage_pay += mileage_pay
        total_per_diem += data['per_diem']
        total_personal_expenses += data['personal_expenses']

    total_deductions = total_mileage_pay + total_per_diem + total_personal_expenses

    # Tech pool
    tech_pool = (job_net - total_deductions) / 2
    if tech_pool < 0:
        tech_pool = Decimal('0')

    total_hours = sum(data['hours'] for data in tech_data.values())
    weighted_sum = sum(data['min_pay'] * data['hours'] for data in tech_data.values())

    # Calculate base pay per tech (same formula as calculate_job_pay)
    technicians = []
    total_base_pay = Decimal('0')

    for tech_id, data in tech_data.items():
        using_minimum = False
        if total_hours == 0:
            weight = Decimal('0')
            base_pay = Decimal('0')
            effective_rate = Decimal('0')
        elif len(tech_data) == 1:
            weight = Decimal('1')
            if data['hours'] > 0:
                calculated_rate = tech_pool / data['hours']
                if calculated_rate < data['min_pay']:
                    using_minimum = True
                    effective_rate = data['min_pay']
                else:
                    effective_rate = calculated_rate
                base_pay = data['hours'] * effective_rate
            else:
                effective_rate = data['min_pay']
                base_pay = Decimal('0')
        else:
            if weighted_sum > 0:
                weight = (data['min_pay'] * data['hours']) / weighted_sum
            else:
                weight = Decimal('1') / len(tech_data)

            weighted_base = tech_pool * weight
            min_pay_amount = data['hours'] * data['min_pay']
            if weighted_base < min_pay_amount:
                using_minimum = True
                base_pay = min_pay_amount
            else:
                base_pay = weighted_base

            if data['hours'] > 0:
                effective_rate = base_pay / data['hours']
            else:
                effective_rate = data['min_pay']

        if total_hours > 0 and total_reimbursables > 0:
            reimbursable_share = total_reimbursables * (data['hours'] / total_hours)
        else:
            reimbursable_share = Decimal('0')

        total_pay = base_pay + data['mileage_pay'] + data['per_diem'] + data['personal_expenses'] + reimbursable_share
        total_base_pay += base_pay

        technicians.append({
            'tech_id': tech_id,
            'tech_name': data['tech_name'],
            'hours': float(data['hours'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'min_pay': float(data['min_pay'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'weight': float(weight.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)) if len(tech_data) > 1 else 1.0,
            'base_pay': float(base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'mileage': float(data['mileage'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'mileage_pay': float(data['mileage_pay'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'per_diem': float(data['per_diem'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'personal_expenses': float(data['personal_expenses'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'reimbursable_share': float(reimbursable_share.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float(total_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'effective_rate': float(effective_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'using_minimum': using_minimum,
            'entries': data['entries']
        })

    return {
        'bundle': bundle.to_dict(),
        'jobs': [j.to_dict() for j in jobs],
        'job_net': float(job_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'tech_pool': float(tech_pool.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_deductions': float(total_deductions.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'reimbursables': [r.to_dict() for r in all_reimbursables],
        'technicians': technicians,
        'totals': {
            'total_hours': float(total_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_base_pay': float(total_base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_mileage_pay': float(total_mileage_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_per_diem': float(total_per_diem.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_personal_expenses': float(total_personal_expenses.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float((total_base_pay + total_mileage_pay + total_per_diem + total_personal_expenses + total_reimbursables).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        }
    }
```

- [ ] **Step 2: Update the import line at top of `pay_calculator.py`**

Change line 26 from:

```python
from app.models import Job, TimeEntry, Technician, MileageRateHistory, PayPeriod, JobReimbursable
```

to:

```python
from app.models import Job, JobBundle, TimeEntry, Technician, MileageRateHistory, PayPeriod, JobReimbursable
```

- [ ] **Step 3: Update `calculate_period_pay()` to merge bundled jobs**

In the `calculate_period_pay()` function, after the entries are fetched and before grouping by job (replace lines 432-439), replace the job grouping block:

```python
    # Group entries by job → tech
    # {job_id: {tech_id: [entries]}}
    job_tech_entries = {}
    for entry in entries:
        if entry.job_id not in job_tech_entries:
            job_tech_entries[entry.job_id] = {}
        if entry.tech_id not in job_tech_entries[entry.job_id]:
            job_tech_entries[entry.job_id][entry.tech_id] = []
        job_tech_entries[entry.job_id][entry.tech_id].append(entry)
```

with:

```python
    # Group entries by effective unit (bundle or standalone job) → tech
    # Bundled jobs merge under key "bundle:<id>"; standalone jobs use job_id
    # {unit_key: {tech_id: [entries]}}
    job_tech_entries = {}
    bundle_job_map = {}  # unit_key -> set of job_ids in that bundle

    for entry in entries:
        # Determine the unit key: bundle if job is bundled, else job_id
        job = Job.query.get(entry.job_id) if entry.job_id else None
        if job and job.bundle_id:
            unit_key = f"bundle:{job.bundle_id}"
            if unit_key not in bundle_job_map:
                bundle_job_map[unit_key] = set()
            bundle_job_map[unit_key].add(entry.job_id)
        elif entry.bundle_id:
            unit_key = f"bundle:{entry.bundle_id}"
            if unit_key not in bundle_job_map:
                bundle_job_map[unit_key] = set()
        else:
            unit_key = entry.job_id

        if unit_key not in job_tech_entries:
            job_tech_entries[unit_key] = {}
        if entry.tech_id not in job_tech_entries[unit_key]:
            job_tech_entries[unit_key][entry.tech_id] = []
        job_tech_entries[unit_key][entry.tech_id].append(entry)

    # Also pick up bundle-only entries (bundle_id set, no job_id) from the period
    bundle_only_entries = TimeEntry.query.filter(
        TimeEntry.date_worked >= start_date,
        TimeEntry.date_worked <= end_date,
        TimeEntry.status.in_(['verified', 'billed', 'paid']),
        TimeEntry.job_id.is_(None),
        TimeEntry.bundle_id.isnot(None),
    )
    if tech_ids:
        bundle_only_entries = bundle_only_entries.filter(TimeEntry.tech_id.in_(tech_ids))
    for entry in bundle_only_entries.all():
        unit_key = f"bundle:{entry.bundle_id}"
        if unit_key not in bundle_job_map:
            bundle_job_map[unit_key] = set()
        if unit_key not in job_tech_entries:
            job_tech_entries[unit_key] = {}
        if entry.tech_id not in job_tech_entries[unit_key]:
            job_tech_entries[unit_key][entry.tech_id] = []
        job_tech_entries[unit_key][entry.tech_id].append(entry)
```

- [ ] **Step 4: Update the per-job loop to handle bundle keys**

Replace the job_total_hours precomputation and the loop header. The current code (lines 442-455):

```python
    # Precompute total job hours (ALL entries, not just period) for each job
    job_total_hours = {}
    for jid in job_tech_entries:
        total = db.session.query(func.sum(TimeEntry.hours_worked)).filter_by(job_id=jid).scalar()
        job_total_hours[jid] = Decimal(str(total or 0))

    # Process each job, distribute pay across techs
    # Accumulate results per tech: {tech_id: {tech_data}}
    tech_results = {}

    for job_id, tech_entries_map in job_tech_entries.items():
        job = Job.query.get(job_id)
        if not job:
            continue
```

becomes:

```python
    # Precompute total hours (ALL entries, not just period) for each unit
    job_total_hours = {}
    for unit_key in job_tech_entries:
        if isinstance(unit_key, str) and unit_key.startswith('bundle:'):
            bid = int(unit_key.split(':')[1])
            bundle_obj = JobBundle.query.get(bid)
            if not bundle_obj:
                continue
            bundle_jids = [j.job_id for j in bundle_obj.jobs.all()]
            total = db.session.query(func.sum(TimeEntry.hours_worked)).filter(
                db.or_(
                    TimeEntry.job_id.in_(bundle_jids) if bundle_jids else False,
                    TimeEntry.bundle_id == bid
                )
            ).scalar()
            job_total_hours[unit_key] = Decimal(str(total or 0))
        else:
            total = db.session.query(func.sum(TimeEntry.hours_worked)).filter_by(job_id=unit_key).scalar()
            job_total_hours[unit_key] = Decimal(str(total or 0))

    tech_results = {}

    for unit_key, tech_entries_map in job_tech_entries.items():
        # Build a virtual "job" for bundles by pooling financials
        if isinstance(unit_key, str) and unit_key.startswith('bundle:'):
            bid = int(unit_key.split(':')[1])
            bundle_obj = JobBundle.query.get(bid)
            if not bundle_obj:
                continue
            bundle_jobs = bundle_obj.jobs.all()
            # Create a virtual job object with pooled financials
            class _VirtualJob:
                pass
            job = _VirtualJob()
            job.job_id = unit_key
            job.billing_amount = sum(Decimal(str(j.billing_amount or 0)) for j in bundle_jobs)
            job.expenses = sum(Decimal(str(j.expenses or 0)) for j in bundle_jobs)
            job.commissions = sum(Decimal(str(j.commissions or 0)) for j in bundle_jobs)
            job.ticket_number = bundle_obj.display_name
            job.description = bundle_obj.display_name
            job.client_name = bundle_jobs[0].client_name if bundle_jobs else None
            job.external_url = None
            job.to_dict = lambda bj=bundle_jobs, bo=bundle_obj: {
                'job_id': f"bundle:{bo.bundle_id}",
                'ticket_number': bo.display_name,
                'description': bo.display_name,
                'client_name': bj[0].client_name if bj else None,
                'billing_amount': float(sum(Decimal(str(j.billing_amount or 0)) for j in bj)),
                'bundle_id': bo.bundle_id,
            }
        else:
            job = Job.query.get(unit_key)
            if not job:
                continue
```

The rest of the loop body (`job_techs` aggregation, prorate, pool, distribute) stays the same — it references `job.billing_amount`, `job.expenses`, `job.commissions` which are now set correctly for both real jobs and virtual bundle jobs. The only change is to use `unit_key` instead of `job_id` when looking up `job_total_hours`:

Replace:

```python
        total_hours_for_job = job_total_hours.get(job_id, Decimal('0'))
```

with:

```python
        total_hours_for_job = job_total_hours.get(unit_key, Decimal('0'))
```

(This line appears twice in the function — once in the prorate section around line 506, and once in the weighted distribution around lines 547 and 586. Update both.)

- [ ] **Step 5: Add bundle pay endpoint to bundles route**

Add to the bottom of `app/routes/bundles.py`:

```python
@bundles_bp.route('/<int:bundle_id>/pay', methods=['GET'])
@manager_required
def bundle_pay(bundle_id):
    from app.utils.pay_calculator import calculate_bundle_pay
    result = calculate_bundle_pay(bundle_id)
    if not result:
        return jsonify({'error': 'Bundle not found'}), 404
    return jsonify(result), 200
```

- [ ] **Step 6: Commit**

```bash
git add app/utils/pay_calculator.py app/routes/bundles.py
git commit -m "feat: add calculate_bundle_pay and bundle-aware period pay"
```

---

### Task 5: Time Entry Routes — Bundle Support

**Files:**
- Modify: `app/routes/time_entries.py`

- [ ] **Step 1: Update `create_time_entry()` to accept `bundle_id`**

In `create_time_entry()`, replace the `job_id` validation block (lines 186-198):

```python
    job_id = data.get('job_id')
    date_worked = data.get('date_worked')

    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400

    if not date_worked:
        return jsonify({'error': 'Date worked required'}), 400

    # Validate job
    job = Job.query.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
```

with:

```python
    job_id = data.get('job_id')
    bundle_id = data.get('bundle_id')
    date_worked = data.get('date_worked')

    if not job_id and not bundle_id:
        return jsonify({'error': 'Job ID or Bundle ID required'}), 400

    if not date_worked:
        return jsonify({'error': 'Date worked required'}), 400

    # Validate job if provided
    job = None
    if job_id:
        job = Job.query.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

    # Validate bundle if provided
    from app.models import JobBundle
    if bundle_id:
        bundle = JobBundle.query.get(bundle_id)
        if not bundle:
            return jsonify({'error': 'Bundle not found'}), 404
```

Then update the `TimeEntry()` constructor call (around line 240) to include `bundle_id`:

```python
    entry = TimeEntry(
        job_id=job_id,
        bundle_id=bundle_id,
        tech_id=tech_id,
```

And update the hourly recalculation after commit (around line 257-259) to be conditional:

```python
    # Recalculate billing for hourly jobs
    if job:
        job.recalculate_hourly_billing()
```

- [ ] **Step 2: Update `update_time_entry()` to handle `bundle_id`**

In `update_time_entry()`, after the `job_id` update block for managers (around line 326-329), add:

```python
        if 'bundle_id' in data:
            if data['bundle_id']:
                from app.models import JobBundle
                bundle = JobBundle.query.get(data['bundle_id'])
                if not bundle:
                    return jsonify({'error': 'Bundle not found'}), 404
            entry.bundle_id = data['bundle_id'] or None
```

- [ ] **Step 3: Update `list_time_entries()` to support `bundle_id` filter**

In `list_time_entries()`, after the `job_id` filter (around line 104), add:

```python
    bundle_id = request.args.get('bundle_id', type=int)
    if bundle_id:
        query = query.filter(TimeEntry.bundle_id == bundle_id)
```

- [ ] **Step 4: Commit**

```bash
git add app/routes/time_entries.py
git commit -m "feat: time entries accept bundle_id, job_id now optional"
```

---

### Task 6: API Client — Bundle Methods

**Files:**
- Modify: `app/static/js/api.js`

- [ ] **Step 1: Add `API.bundles` namespace**

After the `jobs` section (after the closing `},` around line 239), add:

```javascript
    // Bundle endpoints
    bundles: {
        async list(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/bundles${query ? '?' + query : ''}`);
        },

        async get(bundleId) {
            return API.request(`/bundles/${bundleId}`);
        },

        async create(data) {
            return API.request('/bundles', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        async update(bundleId, data) {
            return API.request(`/bundles/${bundleId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        async delete(bundleId) {
            return API.request(`/bundles/${bundleId}`, {
                method: 'DELETE'
            });
        },

        async addJobs(bundleId, jobIds) {
            return API.request(`/bundles/${bundleId}/jobs`, {
                method: 'POST',
                body: JSON.stringify({ job_ids: jobIds })
            });
        },

        async removeJob(bundleId, jobId) {
            return API.request(`/bundles/${bundleId}/jobs/${jobId}`, {
                method: 'DELETE'
            });
        },

        async getPay(bundleId) {
            return API.request(`/bundles/${bundleId}/pay`);
        }
    },
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/api.js
git commit -m "feat: add API.bundles client methods"
```

---

### Task 7: Frontend — Jobs Page Bundle Management

**Files:**
- Modify: `app/static/js/app.js`

- [ ] **Step 1: Add "Create Bundle" button to jobs page header**

In `Pages.jobs()`, update the card-header HTML (around line 617-618) to add the bundle button:

```javascript
                    ${isManager ? '<button class="btn btn-primary" id="new-job-btn"><i class="fas fa-plus"></i> New Job</button>' : ''}
                    ${isManager ? '<button class="btn btn-secondary" id="create-bundle-btn" style="margin-left:8px"><i class="fas fa-layer-group"></i> Create Bundle</button>' : ''}
```

- [ ] **Step 2: Add bundle badge to job rows**

In the `loadJobs()` function, update the table row template (around line 690-709) to show a bundle indicator. After the description cell, add a bundle badge:

Replace:

```javascript
                        <td>${job.description}</td>
```

with:

```javascript
                        <td>${job.description}${job.bundle_name ? ` <span class="badge badge-bundle" onclick="Pages.viewBundle(${job.bundle_id})" title="Bundle: ${job.bundle_name}" style="cursor:pointer;background:#e0e7ff;color:#3730a3;padding:2px 6px;border-radius:4px;font-size:0.75rem;margin-left:4px"><i class="fas fa-layer-group"></i> ${job.bundle_name}</span>` : ''}</td>
```

- [ ] **Step 3: Add actions dropdown items for bundle management**

In the actions column of each job row, add bundle options for managers. Update the actions `<td>` to include:

```javascript
                            ${isManager && !job.bundle_id ? `<button class="btn btn-sm btn-outline" onclick="Pages.addJobToBundle(${job.job_id})" title="Add to Bundle"><i class="fas fa-layer-group"></i></button>` : ''}
                            ${isManager && job.bundle_id ? `<button class="btn btn-sm btn-outline" onclick="Pages.removeJobFromBundle(${job.job_id}, ${job.bundle_id})" title="Remove from Bundle"><i class="fas fa-unlink"></i></button>` : ''}
```

- [ ] **Step 4: Add `Pages.createBundle()` modal function**

Add this function to the `Pages` object:

```javascript
    async createBundle() {
        const data = await API.jobs.list({ per_page: 200, sort_by: 'job_date', sort_order: 'desc' });
        const unbundledJobs = data.jobs.filter(j => !j.bundle_id && j.job_status !== 'cancelled');

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal" style="max-width:600px">
                <div class="modal-header">
                    <h3>Create Job Bundle</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Bundle Name (optional)</label>
                        <input type="text" class="form-control" id="bundle-name" placeholder="Leave blank for auto-name">
                    </div>
                    <div class="form-group">
                        <label>Select Jobs</label>
                        <input type="text" class="form-control" id="bundle-job-search" placeholder="Search jobs..." style="margin-bottom:8px">
                        <div id="bundle-job-list" style="max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:4px;padding:8px">
                            ${unbundledJobs.map(j => `
                                <label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer">
                                    <input type="checkbox" value="${j.job_id}" class="bundle-job-check">
                                    <span><strong>${j.ticket_number || 'No ticket'}</strong> - ${j.description} (${j.client_name || 'No client'})</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn btn-primary" id="save-bundle-btn">Create Bundle</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('bundle-job-search').addEventListener('input', (e) => {
            const search = e.target.value.toLowerCase();
            document.querySelectorAll('.bundle-job-check').forEach(cb => {
                const label = cb.closest('label');
                label.style.display = label.textContent.toLowerCase().includes(search) ? 'flex' : 'none';
            });
        });

        document.getElementById('save-bundle-btn').addEventListener('click', async () => {
            const selected = [...document.querySelectorAll('.bundle-job-check:checked')].map(cb => parseInt(cb.value));
            if (selected.length < 1) {
                App.showToast('Select at least one job', 'error');
                return;
            }
            const name = document.getElementById('bundle-name').value.trim();
            try {
                await API.bundles.create({ name: name || undefined, job_ids: selected });
                App.showToast('Bundle created', 'success');
                modal.remove();
                Pages.jobsPage(1);
            } catch (e) {
                App.showToast(e.message || 'Failed to create bundle', 'error');
            }
        });
    },
```

- [ ] **Step 5: Add `Pages.viewBundle()` modal**

```javascript
    async viewBundle(bundleId) {
        const data = await API.bundles.get(bundleId);
        const bundle = data.bundle;

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal" style="max-width:700px">
                <div class="modal-header">
                    <h3><i class="fas fa-layer-group"></i> ${bundle.display_name}</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <h4>Jobs in Bundle (${bundle.jobs.length})</h4>
                    <table style="width:100%">
                        <thead><tr><th>Ticket</th><th>Description</th><th>Client</th><th>Billing</th><th>Status</th></tr></thead>
                        <tbody>
                            ${bundle.jobs.map(j => `
                                <tr>
                                    <td>${j.ticket_number || '-'}</td>
                                    <td>${j.description}</td>
                                    <td>${j.client_name || '-'}</td>
                                    <td>$${(j.billing_amount || 0).toFixed(2)}</td>
                                    <td>${App.getStatusBadge(j.job_status)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                        <tfoot>
                            <tr style="font-weight:bold">
                                <td colspan="3">Pooled Total</td>
                                <td>$${bundle.jobs.reduce((s, j) => s + (j.billing_amount || 0), 0).toFixed(2)}</td>
                                <td></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    },
```

- [ ] **Step 6: Add `Pages.addJobToBundle()` and `Pages.removeJobFromBundle()`**

```javascript
    async addJobToBundle(jobId) {
        const bundlesData = await API.bundles.list({ status: 'active' });
        const bundles = bundlesData.bundles;

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal" style="max-width:400px">
                <div class="modal-header">
                    <h3>Add to Bundle</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    ${bundles.length > 0 ? `
                        <div class="form-group">
                            <label>Select Existing Bundle</label>
                            <select class="form-control" id="select-bundle">
                                <option value="">-- Select --</option>
                                ${bundles.map(b => `<option value="${b.bundle_id}">${b.display_name} (${b.job_count} jobs)</option>`).join('')}
                            </select>
                        </div>
                        <div style="text-align:center;padding:8px;color:var(--text-secondary)">— or —</div>
                    ` : ''}
                    <button class="btn btn-outline" id="new-bundle-for-job" style="width:100%">Create New Bundle with This Job</button>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    ${bundles.length > 0 ? '<button class="btn btn-primary" id="add-to-bundle-btn">Add</button>' : ''}
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        if (bundles.length > 0) {
            document.getElementById('add-to-bundle-btn').addEventListener('click', async () => {
                const bundleId = document.getElementById('select-bundle').value;
                if (!bundleId) { App.showToast('Select a bundle', 'error'); return; }
                try {
                    await API.bundles.addJobs(parseInt(bundleId), [jobId]);
                    App.showToast('Job added to bundle', 'success');
                    modal.remove();
                    Pages.jobsPage(1);
                } catch (e) {
                    App.showToast(e.message || 'Failed', 'error');
                }
            });
        }

        document.getElementById('new-bundle-for-job').addEventListener('click', () => {
            modal.remove();
            Pages.createBundle();
        });
    },

    async removeJobFromBundle(jobId, bundleId) {
        if (!confirm('Remove this job from its bundle?')) return;
        try {
            await API.bundles.removeJob(bundleId, jobId);
            App.showToast('Job removed from bundle', 'success');
            Pages.jobsPage(1);
        } catch (e) {
            App.showToast(e.message || 'Failed', 'error');
        }
    },
```

- [ ] **Step 7: Wire up the Create Bundle button**

In `Pages.jobs()`, after the `new-job-btn` event listener (around line 748), add:

```javascript
        if (isManager) {
            const bundleBtn = document.getElementById('create-bundle-btn');
            if (bundleBtn) bundleBtn.addEventListener('click', () => Pages.createBundle());
        }
```

- [ ] **Step 8: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: bundle management UI on jobs page"
```

---

### Task 8: Frontend — Time Entry Form Bundle Support

**Files:**
- Modify: `app/static/js/app.js`

- [ ] **Step 1: Find the `editEntry()` function and add bundle dropdown**

Locate `Pages.editEntry` (or the equivalent entry edit modal function). Add a "Bundle" dropdown alongside the "Job" dropdown. The bundle dropdown should load bundles from `API.bundles.list()`.

After the job dropdown `<select>`, add:

```html
<div class="form-group">
    <label>Bundle (optional)</label>
    <select class="form-control" id="entry-bundle">
        <option value="">-- None --</option>
    </select>
</div>
```

Populate it on load:

```javascript
const bundlesData = await API.bundles.list({ status: 'active' });
const bundleSelect = document.getElementById('entry-bundle');
bundlesData.bundles.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.bundle_id;
    opt.textContent = `${b.display_name} (${b.job_count} jobs)`;
    bundleSelect.appendChild(opt);
});
if (entry && entry.bundle_id) {
    bundleSelect.value = entry.bundle_id;
}
```

- [ ] **Step 2: Make job dropdown optional when bundle is selected**

Add change listeners so selecting a bundle removes the "required" indicator on the job dropdown, and vice versa:

```javascript
const jobSelect = document.getElementById('entry-job');
const bundleSelect = document.getElementById('entry-bundle');

bundleSelect.addEventListener('change', () => {
    if (bundleSelect.value) {
        jobSelect.required = false;
        jobSelect.closest('.form-group').querySelector('label').textContent = 'Job (optional)';
    } else {
        jobSelect.required = true;
        jobSelect.closest('.form-group').querySelector('label').textContent = 'Job';
    }
});
```

- [ ] **Step 3: Include `bundle_id` in the save payload**

In the save handler, include `bundle_id` in the data sent to the API:

```javascript
const entryData = {
    job_id: jobSelect.value ? parseInt(jobSelect.value) : null,
    bundle_id: bundleSelect.value ? parseInt(bundleSelect.value) : null,
    // ... other fields
};
```

- [ ] **Step 4: Show bundle name in time entries list**

In the time entries table rendering, update the display to show bundle name when present:

Where job ticket is displayed for each entry, add a fallback:

```javascript
const jobDisplay = entry.job_ticket || (entry.bundle_name ? `[Bundle] ${entry.bundle_name}` : '-');
```

- [ ] **Step 5: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: bundle dropdown in time entry form, bundle display in list"
```

---

### Task 9: Frontend — Bundle Indicators in Reports

**Files:**
- Modify: `app/static/js/app.js`

- [ ] **Step 1: Update payroll detail report rendering**

In the payroll detail report section of `app.js`, where job rows are rendered per technician, add a visual indicator for bundled entries. When a job row has `bundle_id`, show a small bundle icon prefix:

```javascript
const bundlePrefix = jobRow.job?.bundle_id
    ? '<i class="fas fa-layer-group" style="color:#6366f1;margin-right:4px" title="Bundled"></i>'
    : '';
```

Prepend this to the ticket/description cell in the payroll table.

- [ ] **Step 2: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: bundle indicators in payroll report"
```

---

### Task 10: Deploy and Test

- [ ] **Step 1: Push to remote**

```bash
git push origin main
```

- [ ] **Step 2: Deploy to server**

```bash
powershell -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' -o StrictHostKeyChecking=no -i 'C:\Users\Jeremiah\.ssh\gcp_work_tracking' claude-code@34.27.146.58 'cd /opt/work-tracking && sudo git pull origin main && sudo systemctl restart work-tracking' 2>&1"
```

- [ ] **Step 3: Verify in browser**

Test the following:
1. Create a bundle with 2+ jobs from the Jobs page
2. Verify bundle badge appears on bundled jobs
3. Click the badge to see bundle detail modal
4. Create a time entry against the bundle (no specific job)
5. Create a time entry against a specific bundled job
6. Check payroll report — bundled jobs should show pooled pay calculation
7. Remove a job from a bundle, verify it becomes standalone again
8. Delete a bundle, verify jobs are unlinked

- [ ] **Step 4: Final commit if any fixes needed**
