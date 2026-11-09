"""
Job bundle routes for creating, managing, and querying job bundles.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import JobBundle, BundleExpense, Job, TimeEntry
from app.utils.logging import get_logger, audit_logger, log_action
from app.utils.auth import jwt_required_with_user, manager_required

bundles_bp = Blueprint('bundles', __name__)
logger = get_logger(__name__)


def bundle_pay_is_settled(bundle):
    """True once a bundle is fully paid out - no unpaid work left on it.

    Bundles run across several pay periods and technicians are locked one at
    a time, so part of a bundle being paid is the normal state while work is
    still going on (topeka10-12: one tech's share locked, most hours unpaid).
    Expenses are allowed until nothing is left to pay. Locked payouts keep
    their snapshot either way; an expense only shapes pay not yet locked.
    """
    from app.models import Payout, PayPeriod
    from app.routes.imports import SETTLED_PERIOD_STATUSES

    jobs = bundle.jobs.all()
    if any(j.job_status not in ('completed', 'cancelled') for j in jobs):
        return False

    job_ids = [j.job_id for j in jobs]
    entry_filter = TimeEntry.bundle_id == bundle.bundle_id
    if job_ids:
        entry_filter = db.or_(entry_filter, TimeEntry.job_id.in_(job_ids))
    entries = TimeEntry.query.filter(entry_filter).all()
    if not entries:
        return False

    closed_periods = {p.period_id for p in PayPeriod.query.filter(
        PayPeriod.status.in_(SETTLED_PERIOD_STATUSES)).all()}
    locked_payouts = {(p.tech_id, p.period_id) for p in Payout.query.filter(
        Payout.status.in_(('locked', 'paid'))).all()}

    for e in entries:
        if e.period_id in closed_periods:
            continue
        if e.tech_id and e.period_id and (e.tech_id, e.period_id) in locked_payouts:
            continue
        return False  # unassigned, not yet in a period, or in an unlocked payout
    return True


def _detect(bundle_id, description):
    """Re-check this bundle's locked payouts after its pooled numbers changed."""
    from app.routes.jobs import detect_bundle_payout_adjustments
    detect_bundle_payout_adjustments(bundle_id, description)


def _bundle_matches(d, search):
    """Match a search term against a bundle's name, tickets, and clients."""
    haystack = ' '.join([d['display_name']] + d['tickets'] + d['clients']).lower()
    return search.lower() in haystack


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
        if search and not _bundle_matches(d, search):
            continue
        result.append(d)

    return jsonify({'bundles': result}), 200


@bundles_bp.route('/<int:bundle_id>', methods=['GET'])
@jwt_required_with_user
def get_bundle(bundle_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    bundle_data = bundle.to_dict()
    bundle_data['jobs'] = [j.to_dict() for j in bundle.jobs.all()]
    bundle_data['expenses'] = [e.to_dict() for e in
                               bundle.expense_items.order_by(BundleExpense.expense_date, BundleExpense.id)]
    bundle_data['pay_settled'] = bundle_pay_is_settled(bundle)
    return jsonify({'bundle': bundle_data}), 200


def _parse_expense(data, existing=None):
    """Validate an expense payload. Returns (fields, error)."""
    fields = {}

    if existing is None or 'expense_date' in data:
        try:
            fields['expense_date'] = datetime.strptime(str(data.get('expense_date', '')), '%Y-%m-%d').date()
        except ValueError:
            return None, 'expense_date (YYYY-MM-DD) required'

    if existing is None or 'description' in data:
        description = (data.get('description') or '').strip()
        if not description:
            return None, 'description required'
        fields['description'] = description[:255]

    if existing is None or 'amount' in data:
        try:
            amount = Decimal(str(data.get('amount'))).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError, ValueError):
            return None, 'amount must be a number'
        if amount <= 0:
            return None, 'amount must be greater than 0'
        fields['amount'] = amount

    if 'category' in data or existing is None:
        category = data.get('category') or 'other'
        if category not in BundleExpense.CATEGORIES:
            return None, f"category must be one of {', '.join(BundleExpense.CATEGORIES)}"
        fields['category'] = category

    return fields, None


def _settled_response(bundle):
    return jsonify({
        'error': f"'{bundle.display_name}' is fully paid out - every job is complete and all "
                 f"of its time is in locked or paid payouts. Changing its expenses would move "
                 f"already-paid numbers; record the difference as a payout adjustment instead."
    }), 409


@bundles_bp.route('/<int:bundle_id>/expenses', methods=['POST'])
@manager_required
@log_action('update', 'bundle')
def add_bundle_expense(bundle_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    fields, error = _parse_expense(request.get_json() or {})
    if error:
        return jsonify({'error': error}), 400
    if bundle_pay_is_settled(bundle):
        return _settled_response(bundle)

    expense = BundleExpense(bundle_id=bundle_id, created_by=g.user_id, **fields)
    db.session.add(expense)
    db.session.commit()

    audit_logger.log(
        action_type='bundle_expense_added',
        entity_type='bundle',
        entity_id=bundle_id,
        new_values=expense.to_dict(),
        description=f"Expense ${expense.amount} '{expense.description}' added to '{bundle.display_name}'",
        user_id=g.user_id
    )
    _detect(bundle_id, f"expense added ({expense.description} ${expense.amount})")
    return jsonify({'message': 'Expense added', 'expense': expense.to_dict()}), 201


@bundles_bp.route('/<int:bundle_id>/expenses/<int:expense_id>', methods=['PUT'])
@manager_required
@log_action('update', 'bundle')
def update_bundle_expense(bundle_id, expense_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    expense = BundleExpense.query.filter_by(id=expense_id, bundle_id=bundle_id).first_or_404()
    fields, error = _parse_expense(request.get_json() or {}, existing=expense)
    if error:
        return jsonify({'error': error}), 400
    if bundle_pay_is_settled(bundle):
        return _settled_response(bundle)

    old_values = expense.to_dict()
    for key, value in fields.items():
        setattr(expense, key, value)
    db.session.commit()

    audit_logger.log(
        action_type='bundle_expense_updated',
        entity_type='bundle',
        entity_id=bundle_id,
        old_values=old_values,
        new_values=expense.to_dict(),
        user_id=g.user_id
    )
    _detect(bundle_id, f"expense changed ({expense.description})")
    return jsonify({'message': 'Expense updated', 'expense': expense.to_dict()}), 200


@bundles_bp.route('/<int:bundle_id>/expenses/<int:expense_id>', methods=['DELETE'])
@manager_required
@log_action('update', 'bundle')
def delete_bundle_expense(bundle_id, expense_id):
    bundle = JobBundle.query.get_or_404(bundle_id)
    expense = BundleExpense.query.filter_by(id=expense_id, bundle_id=bundle_id).first_or_404()
    if bundle_pay_is_settled(bundle):
        return _settled_response(bundle)

    old_values = expense.to_dict()
    db.session.delete(expense)
    db.session.commit()

    audit_logger.log(
        action_type='bundle_expense_deleted',
        entity_type='bundle',
        entity_id=bundle_id,
        old_values=old_values,
        description=f"Expense ${old_values['amount']:.2f} '{old_values['description']}' removed from '{bundle.display_name}'",
        user_id=g.user_id
    )
    _detect(bundle_id, f"expense removed ({old_values['description']})")
    return jsonify({'message': 'Expense deleted'}), 200


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
    if bundle.expense_items.count():
        return jsonify({'error': 'This bundle has expenses. Remove them first, '
                                 'or they would be deleted with the bundle.'}), 409
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
    if added:
        _detect(bundle_id, f"{len(added)} job(s) added to bundle")

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
    _detect(bundle_id, f"{job.ticket_number} removed from bundle")

    remaining = bundle.jobs.count()
    # A bundle with expenses is kept even when empty, so they aren't lost.
    if remaining == 0 and not bundle.expense_items.count():
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
