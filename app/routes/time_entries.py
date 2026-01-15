"""
Time entry routes for tracking work hours.
Includes creation, updates, verification, and submission workflows.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from sqlalchemy import and_
from app import db
from app.models import TimeEntry, Job, Technician, PayPeriod
from app.utils.logging import get_logger, audit_logger, log_action
from app.utils.auth import (
    jwt_required_with_user,
    manager_required,
    can_access_technician_data,
    can_modify_time_entry,
    can_verify_time_entry,
)

time_entries_bp = Blueprint('time_entries', __name__)
logger = get_logger(__name__)


def calculate_hours(time_in, time_out):
    """Calculate hours worked between two times."""
    if not time_in or not time_out:
        return None

    # Create datetime objects for calculation
    base_date = datetime.today().date()
    dt_in = datetime.combine(base_date, time_in)
    dt_out = datetime.combine(base_date, time_out)

    # Handle overnight shifts
    if dt_out < dt_in:
        dt_out += timedelta(days=1)

    duration = dt_out - dt_in
    hours = Decimal(str(duration.total_seconds() / 3600))
    return round(hours, 2)


@time_entries_bp.route('', methods=['GET'])
@jwt_required_with_user
def list_time_entries():
    """
    List time entries with filtering.

    Query parameters:
        - page, per_page: Pagination
        - tech_id: Filter by technician
        - job_id: Filter by job
        - status: Filter by entry status
        - period_id: Filter by pay period
        - from_date, to_date: Date range filter
    """
    user = g.current_user
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    tech_id = request.args.get('tech_id', type=int)
    job_id = request.args.get('job_id', type=int)
    status = request.args.get('status')
    period_id = request.args.get('period_id', type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    unassigned = request.args.get('unassigned', '').lower() == 'true'

    query = TimeEntry.query

    # Technicians can only see their own entries
    if user.role == 'technician':
        if not user.tech_id:
            return jsonify({'error': 'User not linked to technician'}), 400
        query = query.filter(TimeEntry.tech_id == user.tech_id)
    elif unassigned:
        # Filter for entries without a technician assigned
        query = query.filter(TimeEntry.tech_id.is_(None))
    elif tech_id:
        query = query.filter(TimeEntry.tech_id == tech_id)

    if job_id:
        query = query.filter(TimeEntry.job_id == job_id)

    if status:
        query = query.filter(TimeEntry.status == status)

    if period_id:
        query = query.filter(TimeEntry.period_id == period_id)

    if from_date:
        query = query.filter(TimeEntry.date_worked >= from_date)

    if to_date:
        query = query.filter(TimeEntry.date_worked <= to_date)

    query = query.order_by(TimeEntry.date_worked.desc(), TimeEntry.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'time_entries': [te.to_dict() for te in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@time_entries_bp.route('/<int:entry_id>', methods=['GET'])
@jwt_required_with_user
def get_time_entry(entry_id):
    """Get a specific time entry."""
    user = g.current_user
    entry = TimeEntry.query.get_or_404(entry_id)

    # Check access
    if user.role == 'technician' and entry.tech_id != user.tech_id:
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({'time_entry': entry.to_dict()}), 200


@time_entries_bp.route('', methods=['POST'])
@jwt_required_with_user
@log_action('create', 'time_entry')
def create_time_entry():
    """
    Create a new time entry.

    Request body:
        {
            "job_id": 1,
            "tech_id": 1,  (optional for technicians - uses their own)
            "date_worked": "2026-01-12",
            "time_in": "08:00",
            "time_out": "16:30",
            "hours_worked": 8.5,  (optional - calculated if times provided)
            "notes": "Completed installation"
        }
    """
    user = g.current_user
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

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

    # Determine tech_id
    tech_id = data.get('tech_id')
    if user.role == 'technician':
        if not user.tech_id:
            return jsonify({'error': 'User not linked to technician'}), 400
        tech_id = user.tech_id
    # Managers/admins can leave tech_id null for imported/scraped entries

    # Validate technician if provided
    if tech_id:
        technician = Technician.query.get(tech_id)
        if not technician:
            return jsonify({'error': 'Technician not found'}), 404

    # Parse times
    time_in = None
    time_out = None
    if data.get('time_in'):
        time_in = datetime.strptime(data['time_in'], '%H:%M').time()
    if data.get('time_out'):
        time_out = datetime.strptime(data['time_out'], '%H:%M').time()

    # Calculate or use provided hours
    hours_worked = data.get('hours_worked')
    if time_in and time_out and not hours_worked:
        hours_worked = calculate_hours(time_in, time_out)

    # Find applicable pay period
    period_id = data.get('period_id')
    if not period_id:
        pay_period = PayPeriod.query.filter(
            and_(
                PayPeriod.start_date <= date_worked,
                PayPeriod.end_date >= date_worked,
                PayPeriod.status == 'open'
            )
        ).first()
        if pay_period:
            period_id = pay_period.period_id

    entry = TimeEntry(
        job_id=job_id,
        tech_id=tech_id,
        period_id=period_id,
        date_worked=date_worked,
        time_in=time_in,
        time_out=time_out,
        hours_worked=hours_worked,
        mileage=data.get('mileage') or 0,
        personal_expenses=data.get('personal_expenses') or 0,
        per_diem=data.get('per_diem') or 0,
        notes=data.get('notes', '').strip() or None,
        status='draft',
        created_by=user.user_id
    )

    db.session.add(entry)
    db.session.commit()

    logger.info(f"Time entry created: {entry.entry_id} for job {job_id}")
    audit_logger.log(
        action_type='time_entry_created',
        entity_type='time_entry',
        entity_id=entry.entry_id,
        new_values=entry.to_dict(),
        description=f"Time entry created for job {job.ticket_number}",
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Time entry created successfully',
        'time_entry': entry.to_dict()
    }), 201


@time_entries_bp.route('/<int:entry_id>', methods=['PUT'])
@jwt_required_with_user
@log_action('update', 'time_entry')
def update_time_entry(entry_id):
    """
    Update a time entry.
    Technicians can only update their own draft/submitted entries.
    """
    user = g.current_user
    entry = TimeEntry.query.get_or_404(entry_id)

    if not can_modify_time_entry(user, entry):
        return jsonify({'error': 'Cannot modify this time entry'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = entry.to_dict()

    # Update allowed fields
    if 'date_worked' in data:
        entry.date_worked = data['date_worked']

    if 'time_in' in data:
        entry.time_in = datetime.strptime(data['time_in'], '%H:%M').time() if data['time_in'] else None

    if 'time_out' in data:
        entry.time_out = datetime.strptime(data['time_out'], '%H:%M').time() if data['time_out'] else None

    if 'hours_worked' in data:
        entry.hours_worked = data['hours_worked']
    elif entry.time_in and entry.time_out:
        entry.hours_worked = calculate_hours(entry.time_in, entry.time_out)

    if 'notes' in data:
        entry.notes = data['notes'].strip() if data['notes'] else None

    if 'mileage' in data:
        entry.mileage = data['mileage'] or 0

    if 'personal_expenses' in data:
        entry.personal_expenses = data['personal_expenses'] or 0

    if 'per_diem' in data:
        entry.per_diem = data['per_diem'] or 0

    # Managers can update job_id and tech_id
    if user.role in ('admin', 'manager'):
        if 'job_id' in data:
            job = Job.query.get(data['job_id'])
            if not job:
                return jsonify({'error': 'Job not found'}), 404
            entry.job_id = data['job_id']

        if 'tech_id' in data:
            tech = Technician.query.get(data['tech_id'])
            if not tech:
                return jsonify({'error': 'Technician not found'}), 404
            entry.tech_id = data['tech_id']

    entry.updated_by = user.user_id
    db.session.commit()

    audit_logger.log(
        action_type='time_entry_updated',
        entity_type='time_entry',
        entity_id=entry.entry_id,
        old_values=old_values,
        new_values=entry.to_dict(),
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Time entry updated successfully',
        'time_entry': entry.to_dict()
    }), 200


@time_entries_bp.route('/<int:entry_id>', methods=['DELETE'])
@jwt_required_with_user
def delete_time_entry(entry_id):
    """
    Delete a time entry.
    Only draft entries can be deleted. Managers can delete any draft.
    """
    user = g.current_user
    entry = TimeEntry.query.get_or_404(entry_id)

    if entry.status != 'draft':
        return jsonify({'error': 'Only draft entries can be deleted'}), 400

    if user.role == 'technician' and entry.tech_id != user.tech_id:
        return jsonify({'error': 'Cannot delete this entry'}), 403

    old_values = entry.to_dict()

    db.session.delete(entry)
    db.session.commit()

    audit_logger.log(
        action_type='time_entry_deleted',
        entity_type='time_entry',
        entity_id=entry_id,
        old_values=old_values,
        user_id=user.user_id
    )

    return jsonify({'message': 'Time entry deleted successfully'}), 200


@time_entries_bp.route('/<int:entry_id>/submit', methods=['POST'])
@jwt_required_with_user
def submit_time_entry(entry_id):
    """Submit a draft time entry for verification."""
    user = g.current_user
    entry = TimeEntry.query.get_or_404(entry_id)

    if user.role == 'technician' and entry.tech_id != user.tech_id:
        return jsonify({'error': 'Access denied'}), 403

    if entry.status != 'draft':
        return jsonify({'error': 'Only draft entries can be submitted'}), 400

    if not entry.tech_id:
        return jsonify({'error': 'Technician must be assigned before submission'}), 400

    if not entry.hours_worked or entry.hours_worked <= 0:
        return jsonify({'error': 'Hours worked required before submission'}), 400

    old_status = entry.status
    entry.status = 'submitted'
    entry.updated_by = user.user_id
    db.session.commit()

    audit_logger.log(
        action_type='time_entry_submitted',
        entity_type='time_entry',
        entity_id=entry.entry_id,
        old_values={'status': old_status},
        new_values={'status': 'submitted'},
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Time entry submitted for verification',
        'time_entry': entry.to_dict()
    }), 200


@time_entries_bp.route('/<int:entry_id>/verify', methods=['POST'])
@manager_required
def verify_time_entry(entry_id):
    """Verify a submitted time entry (manager only)."""
    user = g.current_user
    entry = TimeEntry.query.get_or_404(entry_id)

    if not can_verify_time_entry(user, entry):
        return jsonify({
            'error': 'Entry must be submitted before verification',
            'current_status': entry.status
        }), 400

    old_status = entry.status
    entry.status = 'verified'
    entry.verified_by = user.user_id
    entry.verified_at = datetime.utcnow()
    entry.updated_by = user.user_id
    db.session.commit()

    audit_logger.log(
        action_type='time_entry_verified',
        entity_type='time_entry',
        entity_id=entry.entry_id,
        old_values={'status': old_status},
        new_values={'status': 'verified', 'verified_by': user.user_id},
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Time entry verified',
        'time_entry': entry.to_dict()
    }), 200


@time_entries_bp.route('/<int:entry_id>/reject', methods=['POST'])
@manager_required
def reject_time_entry(entry_id):
    """
    Reject a submitted time entry, sending it back to draft.

    Request body:
        {
            "reason": "Hours seem incorrect, please verify"
        }
    """
    user = g.current_user
    entry = TimeEntry.query.get_or_404(entry_id)
    data = request.get_json() or {}

    if entry.status != 'submitted':
        return jsonify({'error': 'Only submitted entries can be rejected'}), 400

    reason = data.get('reason', '').strip()

    old_status = entry.status
    entry.status = 'draft'
    if reason:
        entry.notes = f"[Rejected: {reason}]\n{entry.notes or ''}"
    entry.updated_by = user.user_id
    db.session.commit()

    audit_logger.log(
        action_type='time_entry_rejected',
        entity_type='time_entry',
        entity_id=entry.entry_id,
        old_values={'status': old_status},
        new_values={'status': 'draft', 'rejection_reason': reason},
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Time entry rejected and returned to draft',
        'time_entry': entry.to_dict()
    }), 200


@time_entries_bp.route('/bulk-submit', methods=['POST'])
@jwt_required_with_user
def bulk_submit_entries():
    """
    Submit multiple draft entries at once.

    Request body:
        {
            "entry_ids": [1, 2, 3]
        }
    """
    user = g.current_user
    data = request.get_json()

    if not data or 'entry_ids' not in data:
        return jsonify({'error': 'Entry IDs required'}), 400

    entry_ids = data['entry_ids']
    submitted = []
    errors = []

    for entry_id in entry_ids:
        entry = TimeEntry.query.get(entry_id)

        if not entry:
            errors.append({'entry_id': entry_id, 'error': 'Not found'})
            continue

        if user.role == 'technician' and entry.tech_id != user.tech_id:
            errors.append({'entry_id': entry_id, 'error': 'Access denied'})
            continue

        if entry.status != 'draft':
            errors.append({'entry_id': entry_id, 'error': 'Not in draft status'})
            continue

        if not entry.tech_id:
            errors.append({'entry_id': entry_id, 'error': 'No technician assigned'})
            continue

        if not entry.hours_worked or entry.hours_worked <= 0:
            errors.append({'entry_id': entry_id, 'error': 'Missing hours'})
            continue

        entry.status = 'submitted'
        entry.updated_by = user.user_id
        submitted.append(entry_id)

    db.session.commit()

    if submitted:
        audit_logger.log(
            action_type='bulk_submit',
            entity_type='time_entry',
            new_values={'submitted_ids': submitted},
            description=f"Bulk submitted {len(submitted)} time entries",
            user_id=user.user_id
        )

    return jsonify({
        'message': f'Submitted {len(submitted)} entries',
        'submitted': submitted,
        'errors': errors
    }), 200


@time_entries_bp.route('/bulk-verify', methods=['POST'])
@manager_required
def bulk_verify_entries():
    """
    Verify multiple submitted entries at once (manager only).

    Request body:
        {
            "entry_ids": [1, 2, 3]
        }
    """
    user = g.current_user
    data = request.get_json()

    if not data or 'entry_ids' not in data:
        return jsonify({'error': 'Entry IDs required'}), 400

    entry_ids = data['entry_ids']
    verified = []
    errors = []

    for entry_id in entry_ids:
        entry = TimeEntry.query.get(entry_id)

        if not entry:
            errors.append({'entry_id': entry_id, 'error': 'Not found'})
            continue

        if entry.status != 'submitted':
            errors.append({'entry_id': entry_id, 'error': 'Not submitted'})
            continue

        entry.status = 'verified'
        entry.verified_by = user.user_id
        entry.verified_at = datetime.utcnow()
        entry.updated_by = user.user_id
        verified.append(entry_id)

    db.session.commit()

    if verified:
        audit_logger.log(
            action_type='bulk_verify',
            entity_type='time_entry',
            new_values={'verified_ids': verified},
            description=f"Bulk verified {len(verified)} time entries",
            user_id=user.user_id
        )

    return jsonify({
        'message': f'Verified {len(verified)} entries',
        'verified': verified,
        'errors': errors
    }), 200


@time_entries_bp.route('/my-summary', methods=['GET'])
@jwt_required_with_user
def get_my_summary():
    """Get current user's time entry summary."""
    user = g.current_user

    if not user.tech_id:
        return jsonify({'error': 'User not linked to technician'}), 400

    from sqlalchemy import func

    # Get totals by status
    status_totals = db.session.query(
        TimeEntry.status,
        func.count(TimeEntry.entry_id),
        func.sum(TimeEntry.hours_worked)
    ).filter(
        TimeEntry.tech_id == user.tech_id
    ).group_by(TimeEntry.status).all()

    # Current week entries
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())

    week_entries = TimeEntry.query.filter(
        TimeEntry.tech_id == user.tech_id,
        TimeEntry.date_worked >= week_start
    ).all()

    week_hours = sum(
        float(e.hours_worked) for e in week_entries if e.hours_worked
    )

    return jsonify({
        'by_status': {
            status: {'count': count, 'hours': float(hours) if hours else 0}
            for status, count, hours in status_totals
        },
        'current_week': {
            'entries': len(week_entries),
            'hours': week_hours,
            'week_start': week_start.isoformat()
        }
    }), 200
