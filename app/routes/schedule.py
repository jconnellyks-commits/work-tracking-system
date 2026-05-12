"""
Job schedule routes for multi-day job scheduling.
Manages scheduled dates and per-day tech assignments.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import Job, JobSchedule, JobAssignment, Technician
from app.utils.auth import jwt_required_with_user, manager_required
from app.utils.logging import get_logger
from app.utils.sms_service import get_sms_service

schedule_bp = Blueprint('schedule', __name__, url_prefix='/api/schedule')
logger = get_logger(__name__)


@schedule_bp.route('/job/<int:job_id>', methods=['GET'])
@jwt_required_with_user
def get_job_schedule(job_id):
    """Get all schedule entries for a job."""
    Job.query.get_or_404(job_id)
    entries = JobSchedule.query.filter_by(job_id=job_id)\
        .order_by(JobSchedule.scheduled_date).all()
    return jsonify({'schedule': [e.to_dict() for e in entries]}), 200


@schedule_bp.route('/job/<int:job_id>', methods=['POST'])
@manager_required
def add_schedule_entry(job_id):
    """Add one or more schedule entries to a job."""
    job = Job.query.get_or_404(job_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    # Support bulk or single
    entries_data = data.get('entries', [data])
    created = []

    for entry in entries_data:
        scheduled_date = entry.get('scheduled_date')
        if not scheduled_date:
            return jsonify({'error': 'scheduled_date is required'}), 400

        try:
            date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': f'Invalid date format: {scheduled_date}'}), 400

        tech_id = entry.get('tech_id') or None

        # Validate tech is assigned to this job (if specified)
        if tech_id:
            assignment = JobAssignment.query.filter_by(
                job_id=job_id, tech_id=tech_id
            ).filter(JobAssignment.status.in_(['accepted', 'invited'])).first()
            if not assignment:
                tech = Technician.query.get(tech_id)
                name = tech.name if tech else f'ID {tech_id}'
                return jsonify({'error': f'{name} is not assigned to this job'}), 400

        # Check for duplicate
        existing = JobSchedule.query.filter_by(
            job_id=job_id, scheduled_date=date_obj, tech_id=tech_id
        ).first()
        if existing:
            continue  # Skip duplicates silently

        schedule_entry = JobSchedule(
            job_id=job_id,
            scheduled_date=date_obj,
            tech_id=tech_id,
            notes=entry.get('notes', '').strip() or None
        )
        db.session.add(schedule_entry)
        created.append(schedule_entry)

    db.session.commit()
    logger.info(f"Added {len(created)} schedule entries to job {job_id}")

    sms = get_sms_service()
    for entry in created:
        if entry.tech_id:
            try:
                sms.send_schedule_notification(entry)
            except Exception as e:
                logger.warning(f"SMS failed for schedule entry {entry.id}: {e}")

    return jsonify({
        'message': f'{len(created)} schedule entries added',
        'schedule': [e.to_dict() for e in created]
    }), 201


@schedule_bp.route('/job/<int:job_id>/<int:entry_id>', methods=['PUT'])
@manager_required
def update_schedule_entry(job_id, entry_id):
    """Update a schedule entry."""
    entry = JobSchedule.query.filter_by(id=entry_id, job_id=job_id).first_or_404()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'scheduled_date' in data:
        try:
            entry.scheduled_date = datetime.strptime(data['scheduled_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    old_tech_id = entry.tech_id
    if 'tech_id' in data:
        tech_id = data['tech_id'] or None
        if tech_id:
            assignment = JobAssignment.query.filter_by(
                job_id=job_id, tech_id=tech_id
            ).filter(JobAssignment.status.in_(['accepted', 'invited'])).first()
            if not assignment:
                return jsonify({'error': 'Technician is not assigned to this job'}), 400
        entry.tech_id = tech_id

    if 'notes' in data:
        entry.notes = data['notes'].strip() or None

    db.session.commit()

    if entry.tech_id and entry.tech_id != old_tech_id:
        try:
            sms = get_sms_service()
            sms.send_schedule_notification(entry)
        except Exception as e:
            logger.warning(f"SMS failed for schedule entry {entry.id}: {e}")

    return jsonify({'message': 'Updated', 'entry': entry.to_dict()}), 200


@schedule_bp.route('/job/<int:job_id>/<int:entry_id>', methods=['DELETE'])
@manager_required
def delete_schedule_entry(job_id, entry_id):
    """Delete a schedule entry."""
    entry = JobSchedule.query.filter_by(id=entry_id, job_id=job_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    logger.info(f"Deleted schedule entry {entry_id} from job {job_id}")
    return jsonify({'message': 'Deleted'}), 200


@schedule_bp.route('', methods=['GET'])
@jwt_required_with_user
def get_schedule_range():
    """
    Get all schedule entries in a date range (for calendar rendering).
    Also returns jobs with job_date in range that have NO schedule entries (fallback).

    Query params: from (YYYY-MM-DD), to (YYYY-MM-DD)
    """
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    if not from_date or not to_date:
        return jsonify({'error': 'from and to query params required'}), 400

    try:
        from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
        to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    # Get scheduled entries in range
    entries = db.session.query(JobSchedule, Job).join(Job)\
        .filter(JobSchedule.scheduled_date >= from_dt)\
        .filter(JobSchedule.scheduled_date <= to_dt)\
        .filter(Job.job_status != 'cancelled')\
        .order_by(JobSchedule.scheduled_date).all()

    scheduled_job_ids = set()
    result_entries = []
    for sched, job in entries:
        scheduled_job_ids.add(job.job_id)
        result_entries.append({
            'id': sched.id,
            'job_id': job.job_id,
            'ticket_number': job.ticket_number,
            'client_name': job.client_name,
            'description': job.description,
            'job_status': job.job_status,
            'scheduled_date': sched.scheduled_date.isoformat(),
            'tech_id': sched.tech_id,
            'tech_name': sched.technician.name if sched.technician else None,
            'notes': sched.notes,
            'scheduled_start_time': job.scheduled_start_time.strftime('%H:%M') if job.scheduled_start_time else None,
        })

    # Fallback: jobs with job_date in range but NO schedule entries
    fallback_query = Job.query.filter(
        Job.job_date >= from_dt,
        Job.job_date <= to_dt,
        Job.job_status != 'cancelled',
    )
    if scheduled_job_ids:
        fallback_query = fallback_query.filter(~Job.job_id.in_(scheduled_job_ids))
    fallback_jobs = fallback_query.all()

    fallback_list = []
    for job in fallback_jobs:
        tech_names = [a.technician.name for a in job.assignments.filter(
            JobAssignment.status.in_(['accepted', 'invited'])
        ).all() if a.technician]
        fallback_list.append({
            'job_id': job.job_id,
            'ticket_number': job.ticket_number,
            'client_name': job.client_name,
            'description': job.description,
            'job_status': job.job_status,
            'job_date': job.job_date.isoformat() if job.job_date else None,
            'scheduled_start_time': job.scheduled_start_time.strftime('%H:%M') if job.scheduled_start_time else None,
            'assigned_techs': tech_names,
        })

    return jsonify({
        'entries': result_entries,
        'fallback_jobs': fallback_list
    }), 200
