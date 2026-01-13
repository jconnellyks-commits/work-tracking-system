"""
Job management routes for creating, updating, and querying jobs.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from sqlalchemy import or_
from app import db
from app.models import Job, Platform, TimeEntry
from app.utils.logging import get_logger, audit_logger, log_action
from app.utils.auth import jwt_required_with_user, manager_required

jobs_bp = Blueprint('jobs', __name__)
logger = get_logger(__name__)


@jobs_bp.route('', methods=['GET'])
@jwt_required_with_user
def list_jobs():
    """
    List jobs with optional filtering and pagination.

    Query parameters:
        - page: Page number (default 1)
        - per_page: Items per page (default 25)
        - status: Filter by job_status
        - platform_id: Filter by platform
        - search: Search in ticket_number, description, client_name
        - from_date: Filter jobs on or after this date
        - to_date: Filter jobs on or before this date
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    status = request.args.get('status')
    platform_id = request.args.get('platform_id', type=int)
    search = request.args.get('search', '').strip()
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = Job.query

    # Apply filters
    if status:
        query = query.filter(Job.job_status == status)

    if platform_id:
        query = query.filter(Job.platform_id == platform_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Job.ticket_number.ilike(search_term),
                Job.description.ilike(search_term),
                Job.client_name.ilike(search_term)
            )
        )

    if from_date:
        query = query.filter(Job.job_date >= from_date)

    if to_date:
        query = query.filter(Job.job_date <= to_date)

    # Order by job date descending
    query = query.order_by(Job.job_date.desc(), Job.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'jobs': [job.to_dict() for job in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@jobs_bp.route('/<int:job_id>', methods=['GET'])
@jwt_required_with_user
def get_job(job_id):
    """Get a specific job by ID with time entries summary."""
    job = Job.query.get_or_404(job_id)

    # Get time entries summary
    time_entries = TimeEntry.query.filter_by(job_id=job_id).all()
    total_hours = sum(
        float(te.hours_worked) for te in time_entries if te.hours_worked
    )

    job_data = job.to_dict()
    job_data['time_entries_count'] = len(time_entries)
    job_data['total_hours_worked'] = total_hours

    return jsonify({'job': job_data}), 200


@jobs_bp.route('', methods=['POST'])
@manager_required
@log_action('create', 'job')
def create_job():
    """
    Create a new job.

    Request body:
        {
            "platform_id": 1,
            "ticket_number": "WM-12345",
            "description": "Install network equipment",
            "client_name": "ABC Corp",
            "job_type": "Installation",
            "location": "123 Main St",
            "billing_type": "flat_rate",
            "billing_amount": 250.00,
            "estimated_hours": 4.0,
            "job_date": "2026-01-15",
            "due_date": "2026-01-20"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    # Required fields
    platform_id = data.get('platform_id')
    description = data.get('description', '').strip()

    if not platform_id:
        return jsonify({'error': 'Platform ID required'}), 400

    if not description:
        return jsonify({'error': 'Description required'}), 400

    # Validate platform
    platform = Platform.query.get(platform_id)
    if not platform:
        return jsonify({'error': 'Platform not found'}), 404

    # Check for duplicate ticket number
    ticket_number = data.get('ticket_number', '').strip() or None
    if ticket_number:
        existing = Job.query.filter_by(ticket_number=ticket_number).first()
        if existing:
            return jsonify({'error': 'Ticket number already exists'}), 409

    # Create job - handle empty strings for optional fields
    job_date = data.get('job_date') or None
    due_date = data.get('due_date') or None
    billing_amount = data.get('billing_amount') or None
    estimated_hours = data.get('estimated_hours') or None

    job = Job(
        platform_id=platform_id,
        platform_job_code=data.get('platform_job_code', '').strip() or None,
        ticket_number=ticket_number,
        description=description,
        client_name=data.get('client_name', '').strip() or None,
        job_type=data.get('job_type', '').strip() or None,
        location=data.get('location', '').strip() or None,
        billing_type=data.get('billing_type', 'flat_rate'),
        billing_amount=billing_amount,
        estimated_hours=estimated_hours,
        job_status=data.get('job_status', 'pending'),
        job_date=job_date,
        due_date=due_date
    )

    db.session.add(job)
    db.session.commit()

    logger.info(f"Job created: {job.job_id} - {job.ticket_number}")
    audit_logger.log(
        action_type='job_created',
        entity_type='job',
        entity_id=job.job_id,
        new_values=job.to_dict(),
        description=f"Job {job.ticket_number} created",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Job created successfully',
        'job': job.to_dict()
    }), 201


@jobs_bp.route('/<int:job_id>', methods=['PUT'])
@manager_required
@log_action('update', 'job')
def update_job(job_id):
    """
    Update an existing job.

    Request body: Same fields as create, all optional.
    """
    job = Job.query.get_or_404(job_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = job.to_dict()

    # Update fields if provided
    updatable_fields = [
        'platform_id', 'platform_job_code', 'ticket_number', 'description',
        'client_name', 'job_type', 'location', 'billing_type', 'billing_amount',
        'estimated_hours', 'job_status', 'job_date', 'due_date', 'completed_date'
    ]

    for field in updatable_fields:
        if field in data:
            value = data[field]
            if isinstance(value, str):
                value = value.strip() or None
            setattr(job, field, value)

    # Validate ticket number uniqueness if changed
    if 'ticket_number' in data and data['ticket_number']:
        existing = Job.query.filter(
            Job.ticket_number == data['ticket_number'],
            Job.job_id != job_id
        ).first()
        if existing:
            return jsonify({'error': 'Ticket number already exists'}), 409

    # Auto-set completed_date when marking as completed
    if data.get('job_status') == 'completed' and not job.completed_date:
        job.completed_date = datetime.utcnow().date()

    db.session.commit()

    logger.info(f"Job updated: {job.job_id}")
    audit_logger.log(
        action_type='job_updated',
        entity_type='job',
        entity_id=job.job_id,
        old_values=old_values,
        new_values=job.to_dict(),
        description=f"Job {job.ticket_number} updated",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Job updated successfully',
        'job': job.to_dict()
    }), 200


@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
@manager_required
@log_action('delete', 'job')
def delete_job(job_id):
    """
    Delete a job (soft delete by setting status to cancelled).
    Jobs with time entries cannot be deleted.
    """
    job = Job.query.get_or_404(job_id)

    # Check for time entries
    time_entries_count = TimeEntry.query.filter_by(job_id=job_id).count()
    if time_entries_count > 0:
        return jsonify({
            'error': 'Cannot delete job with time entries',
            'time_entries_count': time_entries_count
        }), 400

    old_values = job.to_dict()

    # Soft delete
    job.job_status = 'cancelled'
    db.session.commit()

    logger.info(f"Job cancelled: {job.job_id}")
    audit_logger.log(
        action_type='job_cancelled',
        entity_type='job',
        entity_id=job.job_id,
        old_values=old_values,
        new_values={'job_status': 'cancelled'},
        description=f"Job {job.ticket_number} cancelled",
        user_id=g.user_id
    )

    return jsonify({'message': 'Job cancelled successfully'}), 200


@jobs_bp.route('/<int:job_id>/time-entries', methods=['GET'])
@jwt_required_with_user
def get_job_time_entries(job_id):
    """Get all time entries for a specific job."""
    job = Job.query.get_or_404(job_id)

    time_entries = TimeEntry.query.filter_by(job_id=job_id)\
        .order_by(TimeEntry.date_worked.desc())\
        .all()

    return jsonify({
        'job': job.to_dict(),
        'time_entries': [te.to_dict() for te in time_entries],
        'total_hours': sum(
            float(te.hours_worked) for te in time_entries if te.hours_worked
        )
    }), 200


@jobs_bp.route('/platforms', methods=['GET'])
@jwt_required_with_user
def list_platforms():
    """List all available platforms."""
    status = request.args.get('status', 'active')

    query = Platform.query
    if status:
        query = query.filter_by(status=status)

    platforms = query.order_by(Platform.name).all()

    return jsonify({
        'platforms': [p.to_dict() for p in platforms]
    }), 200


@jobs_bp.route('/platforms', methods=['POST'])
@manager_required
def create_platform():
    """
    Create a new platform.

    Request body:
        {
            "name": "New Platform",
            "code": "newplatform",
            "description": "Description here",
            "api_endpoint": "https://api.example.com"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    code = data.get('code', '').strip().lower()

    if not name or not code:
        return jsonify({'error': 'Name and code required'}), 400

    # Check for duplicates
    if Platform.query.filter_by(name=name).first():
        return jsonify({'error': 'Platform name already exists'}), 409

    if Platform.query.filter_by(code=code).first():
        return jsonify({'error': 'Platform code already exists'}), 409

    platform = Platform(
        name=name,
        code=code,
        description=data.get('description', '').strip() or None,
        api_endpoint=data.get('api_endpoint', '').strip() or None
    )

    db.session.add(platform)
    db.session.commit()

    audit_logger.log(
        action_type='platform_created',
        entity_type='platform',
        entity_id=platform.platform_id,
        new_values=platform.to_dict(),
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Platform created successfully',
        'platform': platform.to_dict()
    }), 201


@jobs_bp.route('/stats', methods=['GET'])
@jwt_required_with_user
def get_job_stats():
    """Get job statistics overview."""
    from sqlalchemy import func

    # Job counts by status
    status_counts = db.session.query(
        Job.job_status,
        func.count(Job.job_id)
    ).group_by(Job.job_status).all()

    # Jobs by platform
    platform_counts = db.session.query(
        Platform.name,
        func.count(Job.job_id)
    ).join(Job).group_by(Platform.name).all()

    # Recent jobs (last 30 days)
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
    recent_count = Job.query.filter(Job.created_at >= thirty_days_ago).count()

    return jsonify({
        'by_status': {status: count for status, count in status_counts},
        'by_platform': {name: count for name, count in platform_counts},
        'recent_jobs': recent_count
    }), 200
