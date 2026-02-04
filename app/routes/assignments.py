"""
Job assignment routes for managing technician assignments to jobs.
Includes assignment creation, removal, and SMS notification functionality.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import Job, JobAssignment, Technician, User
from app.utils.sms_service import get_sms_service
from app.utils.auth import jwt_required_with_user, admin_required, manager_required
from app.utils.logging import get_logger, audit_logger

assignments_bp = Blueprint('assignments', __name__, url_prefix='/api/assignments')
logger = get_logger(__name__)


@assignments_bp.route('/job/<int:job_id>', methods=['GET'])
@manager_required
def get_job_assignments(job_id):
    """
    Get all assignments for a specific job.

    Returns list of technician assignments with their status and SMS info.
    Manager+ only.
    """
    job = Job.query.get_or_404(job_id)

    assignments = JobAssignment.query.filter_by(job_id=job_id)\
        .order_by(JobAssignment.assigned_at.desc())\
        .all()

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
        ).filter(JobAssignment.status.in_(['accepted', 'invited'])).first()

        if existing:
            errors.append({
                'tech_id': tech_id,
                'error': 'Technician already assigned to this job',
                'assignment_id': existing.assignment_id
            })
            continue

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
