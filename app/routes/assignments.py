"""
Job assignment routes for managing technician assignments to jobs.
Includes assignment creation, removal, and SMS notification functionality.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import Job, JobAssignment, Technician, User, SMSNotification, EmailParserLog, EmailForward
from app.utils.sms_service import get_sms_service
from app.utils import gmail_forward
from app.utils.auth import jwt_required_with_user, admin_required, manager_required
from app.utils.logging import get_logger, audit_logger

assignments_bp = Blueprint('assignments', __name__, url_prefix='/api/assignments')
logger = get_logger(__name__)


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


@assignments_bp.route('/job/<int:job_id>', methods=['GET'])
@manager_required
def get_job_assignments(job_id):
    """
    Get all assignments for a specific job.

    Returns list of technician assignments with their status and SMS info.
    Manager+ only.
    """
    job = Job.query.get_or_404(job_id)

    include_cancelled = request.args.get('include_cancelled', 'false').lower() == 'true'
    query = JobAssignment.query.filter_by(job_id=job_id)
    if not include_cancelled:
        query = query.filter(JobAssignment.status.notin_(['cancelled', 'declined', 'expired']))
    assignments = query.order_by(JobAssignment.assigned_at.desc()).all()

    return jsonify({
        'job': job.to_dict(),
        'assignments': [a.to_dict() for a in assignments],
        'total': len(assignments)
    }), 200


@assignments_bp.route('/technician/<int:tech_id>', methods=['GET'])
@jwt_required_with_user
def get_technician_assignments(tech_id):
    """
    Get all assignments for a specific technician.

    Manager+ can view any technician's assignments.
    Technicians can only view their own assignments.
    """
    user = g.current_user

    # Check access
    if user.role == 'technician':
        if user.tech_id != tech_id:
            return jsonify({'error': 'Access denied'}), 403

    technician = Technician.query.get_or_404(tech_id)

    # Get query parameters for filtering
    status = request.args.get('status')
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'

    query = JobAssignment.query.filter_by(tech_id=tech_id)

    if status:
        query = query.filter(JobAssignment.status == status)

    if not include_completed:
        # Exclude assignments for completed/cancelled jobs by default
        query = query.join(Job).filter(Job.job_status.notin_(['completed', 'cancelled']))

    assignments = query.order_by(JobAssignment.assigned_at.desc()).all()

    return jsonify({
        'technician': technician.to_dict(),
        'assignments': [a.to_dict() for a in assignments],
        'total': len(assignments)
    }), 200


@assignments_bp.route('/my-jobs', methods=['GET'])
@jwt_required_with_user
def get_my_jobs():
    """
    Get current user's assigned jobs.

    Any authenticated user with a linked technician account.
    Returns jobs where the user's technician is assigned.
    """
    user = g.current_user

    if not user.tech_id:
        return jsonify({'error': 'User not linked to technician account'}), 400

    # Get query parameters for filtering
    status = request.args.get('status')
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'

    query = JobAssignment.query.filter_by(tech_id=user.tech_id)

    # Only show accepted assignments by default
    if status:
        query = query.filter(JobAssignment.status == status)
    else:
        query = query.filter(JobAssignment.status == 'accepted')

    if not include_completed:
        query = query.join(Job).filter(Job.job_status.notin_(['completed', 'cancelled']))

    assignments = query.order_by(JobAssignment.assigned_at.desc()).all()

    # Return jobs with assignment info
    jobs = []
    for assignment in assignments:
        job_data = assignment.job.to_dict() if assignment.job else {}
        job_data['assignment'] = {
            'assignment_id': assignment.assignment_id,
            'status': assignment.status,
            'is_primary': assignment.is_primary,
            'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            'notes': assignment.notes
        }
        jobs.append(job_data)

    return jsonify({
        'jobs': jobs,
        'total': len(jobs)
    }), 200


@assignments_bp.route('/job/<int:job_id>', methods=['POST'])
@manager_required
def assign_technicians_to_job(job_id):
    """
    Assign one or more technicians to a job.

    Request body:
        {
            "tech_ids": [1, 2, 3],
            "send_sms": true,
            "notes": "Optional notes for assignment"
        }

    Creates assignments with status='accepted'.
    Optionally sends SMS notifications to technicians.
    Manager+ only.
    """
    user = g.current_user
    job = Job.query.get_or_404(job_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    tech_ids = data.get('tech_ids', [])
    if not tech_ids or not isinstance(tech_ids, list):
        return jsonify({'error': 'tech_ids array required'}), 400

    send_sms = data.get('send_sms', False)
    notes = data.get('notes', '').strip() or None

    created_assignments = []
    errors = []
    sms_results = []
    email_forward_results = []

    for tech_id in tech_ids:
        # Validate technician exists
        technician = Technician.query.get(tech_id)
        if not technician:
            errors.append({'tech_id': tech_id, 'error': 'Technician not found'})
            continue

        if technician.status != 'active':
            errors.append({'tech_id': tech_id, 'error': 'Technician is not active'})
            continue

        # Check for existing assignment
        existing = JobAssignment.query.filter_by(
            job_id=job_id,
            tech_id=tech_id
        ).first()

        if existing:
            if existing.status in ('accepted', 'invited'):
                errors.append({
                    'tech_id': tech_id,
                    'error': 'Technician already assigned to this job',
                    'assignment_id': existing.assignment_id
                })
                continue
            # Reactivate cancelled/declined/expired assignment
            existing.status = 'accepted'
            existing.assigned_by = user.user_id
            existing.assigned_at = datetime.utcnow()
            existing.notes = notes
            existing.sms_sent = False
            existing.sms_sent_at = None
            existing.sms_delivery_status = 'pending'
            assignment = existing
        else:
            # Determine if this is the primary technician (first one assigned)
            existing_count = JobAssignment.query.filter_by(
                job_id=job_id,
                status='accepted'
            ).count()
            is_primary = existing_count == 0

            # Create assignment
            assignment = JobAssignment(
                job_id=job_id,
                tech_id=tech_id,
                status='accepted',
                is_primary=is_primary,
                assigned_by=user.user_id,
                assigned_at=datetime.utcnow(),
                notes=notes
            )

            db.session.add(assignment)
        db.session.flush()  # Get the assignment_id

        created_assignments.append(assignment)

        # Send SMS if requested
        if send_sms:
            sms_service = get_sms_service()
            sms_result = sms_service.send_job_assignment_notification(assignment)
            sms_results.append({
                'tech_id': tech_id,
                'tech_name': technician.name,
                'success': sms_result.get('success', False),
                'error': sms_result.get('error')
            })

        # Auto-forward TST dispatch email
        fwd_result = _forward_tst_email_for_assignment(job, assignment, technician)
        if fwd_result:
            email_forward_results.append(fwd_result)

    # Update job status to assigned if it was pending
    if created_assignments and job.job_status == 'pending':
        job.job_status = 'assigned'

    db.session.commit()

    # Log the action
    if created_assignments:
        audit_logger.log(
            action_type='technicians_assigned',
            entity_type='job',
            entity_id=job_id,
            new_values={
                'assigned_tech_ids': [a.tech_id for a in created_assignments],
                'assignment_ids': [a.assignment_id for a in created_assignments],
                'sms_sent': send_sms
            },
            description=f"Assigned {len(created_assignments)} technician(s) to job {job.ticket_number}",
            user_id=user.user_id
        )

    return jsonify({
        'message': f'Created {len(created_assignments)} assignment(s)',
        'assignments': [a.to_dict() for a in created_assignments],
        'errors': errors,
        'sms_results': sms_results if send_sms else None,
        'email_forward_results': email_forward_results if email_forward_results else None,
        'job': job.to_dict()
    }), 201 if created_assignments else 400


@assignments_bp.route('/<int:assignment_id>', methods=['DELETE'])
@manager_required
def remove_assignment(assignment_id):
    """
    Remove an assignment (sets status to cancelled).

    Manager+ only.
    """
    user = g.current_user
    assignment = JobAssignment.query.get_or_404(assignment_id)

    old_values = assignment.to_dict()

    # Soft delete by setting status to cancelled
    assignment.status = 'cancelled'
    assignment.updated_at = datetime.utcnow()

    db.session.commit()

    audit_logger.log(
        action_type='assignment_cancelled',
        entity_type='job_assignment',
        entity_id=assignment_id,
        old_values=old_values,
        new_values={'status': 'cancelled'},
        description=f"Removed technician {assignment.tech_id} from job {assignment.job_id}",
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Assignment removed successfully',
        'assignment': assignment.to_dict()
    }), 200


@assignments_bp.route('/<int:assignment_id>/resend-sms', methods=['POST'])
@manager_required
def resend_sms_notification(assignment_id):
    """
    Resend SMS notification for an assignment.

    Manager+ only.
    """
    user = g.current_user
    assignment = JobAssignment.query.get_or_404(assignment_id)

    if assignment.status != 'accepted':
        return jsonify({
            'error': 'Can only send SMS for accepted assignments',
            'current_status': assignment.status
        }), 400

    if not assignment.technician or not assignment.technician.phone:
        return jsonify({'error': 'Technician has no phone number'}), 400

    sms_service = get_sms_service()
    result = sms_service.send_job_assignment_notification(assignment)

    if result.get('success'):
        audit_logger.log(
            action_type='sms_resent',
            entity_type='job_assignment',
            entity_id=assignment_id,
            new_values={'sms_sent_at': assignment.sms_sent_at.isoformat() if assignment.sms_sent_at else None},
            description=f"Resent SMS for assignment {assignment_id}",
            user_id=user.user_id
        )

        return jsonify({
            'message': 'SMS notification sent successfully',
            'assignment': assignment.to_dict()
        }), 200
    else:
        return jsonify({
            'error': result.get('error', 'Failed to send SMS'),
            'assignment': assignment.to_dict()
        }), 500


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


@assignments_bp.route('/sms-status', methods=['GET'])
@admin_required
def get_sms_status():
    """
    Get SMS configuration status.

    Admin only.
    """
    sms_service = get_sms_service()
    config_status = sms_service.get_config_status()

    return jsonify({
        'sms_config': config_status
    }), 200


@assignments_bp.route('/job/<int:job_id>/availability-request', methods=['POST'])
@manager_required
def request_availability(job_id):
    """
    Send availability request SMS to one or more technicians for a job.

    Creates assignments with status='invited' and sends availability-request SMS.
    If a cancelled/declined/expired assignment already exists for a tech, it is
    reactivated (to work around the unique constraint on job_id+tech_id).

    Request body:
        {
            "tech_ids": [1, 2],
            "notes": "Optional notes"
        }

    Manager+ only.
    """
    user = g.current_user
    job = Job.query.get_or_404(job_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    tech_ids = data.get('tech_ids', [])
    if not tech_ids or not isinstance(tech_ids, list):
        return jsonify({'error': 'tech_ids array required'}), 400

    notes = data.get('notes', '').strip() or None

    sms_service = get_sms_service()
    sms_service.reload_config()

    created = []
    errors = []
    sms_results = []

    for tech_id in tech_ids:
        technician = Technician.query.get(tech_id)
        if not technician:
            errors.append({'tech_id': tech_id, 'error': 'Technician not found'})
            continue

        if technician.status != 'active':
            errors.append({'tech_id': tech_id, 'error': 'Technician is not active'})
            continue

        # Check for any existing assignment (unique constraint requires update, not insert)
        existing = JobAssignment.query.filter_by(job_id=job_id, tech_id=tech_id).first()

        if existing:
            if existing.status in ('accepted', 'invited'):
                errors.append({
                    'tech_id': tech_id,
                    'error': 'Technician already has an active assignment for this job',
                    'assignment_id': existing.assignment_id
                })
                continue
            # Reuse the existing record (cancelled/declined/expired)
            existing.status = 'invited'
            existing.availability_response = 'pending'
            existing.availability_responded_at = None
            existing.responded_at = None
            existing.assigned_by = user.user_id
            existing.assigned_at = datetime.utcnow()
            existing.notes = notes
            existing.sms_sent = False
            existing.sms_sent_at = None
            existing.sms_delivery_status = 'pending'
            assignment = existing
        else:
            assignment = JobAssignment(
                job_id=job_id,
                tech_id=tech_id,
                status='invited',
                availability_response='pending',
                is_primary=False,
                assigned_by=user.user_id,
                assigned_at=datetime.utcnow(),
                notes=notes,
            )
            db.session.add(assignment)

        db.session.flush()

        sms_result = sms_service.send_availability_request(assignment)
        created.append(assignment)
        sms_results.append({
            'tech_id': tech_id,
            'tech_name': technician.name,
            'success': sms_result.get('success', False),
            'error': sms_result.get('error'),
        })

    db.session.commit()

    if created:
        audit_logger.log(
            action_type='availability_requested',
            entity_type='job',
            entity_id=job_id,
            new_values={
                'invited_tech_ids': [a.tech_id for a in created],
                'assignment_ids': [a.assignment_id for a in created],
            },
            description=f"Sent availability request to {len(created)} technician(s) for job {job.ticket_number}",
            user_id=user.user_id
        )

    return jsonify({
        'message': f'Sent availability request to {len(created)} technician(s)',
        'assignments': [a.to_dict() for a in created],
        'errors': errors,
        'sms_results': sms_results,
        'job': job.to_dict()
    }), 201 if created else 400


@assignments_bp.route('/sms/log', methods=['GET'])
@manager_required
def get_sms_log():
    """
    Get SMS notification log.

    Query params:
        tech_id: Filter by technician
        status: Filter by status (pending/sent/delivered/failed)
        limit: Max records to return (default 100)

    Manager+ only.
    """
    tech_id = request.args.get('tech_id', type=int)
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)

    query = SMSNotification.query

    if tech_id:
        query = query.filter_by(tech_id=tech_id)

    if status:
        query = query.filter_by(status=status)

    notifications = (
        query
        .order_by(SMSNotification.created_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'total': len(notifications)
    }), 200


@assignments_bp.route('/sms/log/<int:notification_id>/spam', methods=['PATCH'])
@manager_required
def toggle_sms_spam(notification_id):
    """Toggle is_spam flag on an SMS notification. Manager+ only."""
    notif = SMSNotification.query.get_or_404(notification_id)
    notif.is_spam = not notif.is_spam
    db.session.commit()
    return jsonify({'notification': notif.to_dict()}), 200


@assignments_bp.route('/sms/log/<int:notification_id>', methods=['DELETE'])
@manager_required
def delete_sms_notification(notification_id):
    """Delete an SMS notification log entry. Manager+ only."""
    notif = SMSNotification.query.get_or_404(notification_id)
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'message': 'Notification deleted'}), 200
