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


@bundles_bp.route('/<int:bundle_id>/pay', methods=['GET'])
@manager_required
def bundle_pay(bundle_id):
    from app.utils.pay_calculator import calculate_bundle_pay
    result = calculate_bundle_pay(bundle_id)
    if not result:
        return jsonify({'error': 'Bundle not found'}), 404
    return jsonify(result), 200
