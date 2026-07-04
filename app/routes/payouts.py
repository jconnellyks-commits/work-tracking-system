"""Payout management routes."""
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import (
    Payout, PayoutJobDetail, PayoutLineItem, PayPeriod,
    Advance, AdvanceRepayment, Technician, PayoutAdjustment
)
from app.utils.auth import manager_required
from app.utils.pay_calculator import calculate_period_pay

payouts_bp = Blueprint('payouts', __name__)


@payouts_bp.route('/', methods=['GET'])
@manager_required
def list_payouts():
    """List payouts for a period."""
    period_id = request.args.get('period_id', type=int)
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    query = Payout.query.filter_by(period_id=period_id)
    tech_id = request.args.get('tech_id')
    if tech_id:
        tech_ids = [int(t) for t in tech_id.split(',')]
        query = query.filter(Payout.tech_id.in_(tech_ids))
    payouts = query.all()
    return jsonify({
        'payouts': [p.to_dict() for p in payouts]
    })


@payouts_bp.route('/<int:payout_id>', methods=['GET'])
@manager_required
def get_payout(payout_id):
    """Get single payout with job details and line items."""
    payout = Payout.query.get_or_404(payout_id)
    data = payout.to_dict()
    data['job_details'] = [jd.to_dict() for jd in payout.job_details.all()]
    data['line_items'] = [li.to_dict() for li in payout.line_items.all()]
    data['advance_repayments'] = [ar.to_dict() for ar in payout.advance_repayments.all()]
    return jsonify(data)


def _create_payout_for_tech(period_id, tech_data, now):
    """Create a locked payout record for a single technician. Returns the Payout."""
    tech_id = tech_data['tech_id']

    payout = Payout(
        period_id=period_id,
        tech_id=tech_id,
        status='locked',
        total_hours=tech_data['total_hours'],
        total_base_pay=tech_data['total_base_pay'],
        total_mileage_pay=tech_data['total_mileage_pay'],
        total_per_diem=tech_data['total_per_diem'],
        total_personal_expenses=tech_data['total_personal_expenses'],
        total_bonuses=0,
        total_deductions=0,
        total_advance_repayment=0,
        locked_at=now,
    )
    db.session.add(payout)
    db.session.flush()

    net_before_advances = (
        Decimal(str(payout.total_base_pay or 0)) + Decimal(str(payout.total_mileage_pay or 0))
        + Decimal(str(payout.total_per_diem or 0)) + Decimal(str(payout.total_personal_expenses or 0))
    )

    total_advance_repayment = Decimal('0')
    active_advances = Advance.query.filter_by(
        tech_id=tech_id, status='active'
    ).order_by(Advance.created_at.asc()).all()

    available = net_before_advances
    for advance in active_advances:
        if available <= 0:
            break
        cap = Decimal(str(advance.max_per_period or advance.remaining_balance))
        repay = min(cap, Decimal(str(advance.remaining_balance)), available)
        if repay > 0:
            repayment = AdvanceRepayment(
                advance_id=advance.advance_id,
                payout_id=payout.payout_id,
                amount=repay,
            )
            db.session.add(repayment)
            advance.remaining_balance = Decimal(str(advance.remaining_balance)) - repay
            if advance.remaining_balance <= 0:
                advance.remaining_balance = Decimal('0')
                advance.status = 'repaid'
                advance.repaid_at = now
            total_advance_repayment += repay
            available -= repay

    payout.total_advance_repayment = total_advance_repayment
    db.session.flush()

    # Auto-apply pending carried-forward adjustments from prior periods
    pending_adjs = PayoutAdjustment.query.join(Payout).filter(
        Payout.tech_id == tech_id,
        PayoutAdjustment.resolution == 'pending',
    ).all()

    for adj in pending_adjs:
        li_type = 'bonus' if adj.amount_diff >= 0 else 'deduction'
        li = PayoutLineItem(
            payout_id=payout.payout_id,
            type=li_type,
            description=f'Carry-forward: {adj.description}',
            amount=abs(adj.amount_diff),
            created_by=g.user_id,
        )
        db.session.add(li)
        adj.resolution = 'carried_forward'
        adj.resolved_to_period_id = period_id
        adj.resolved_at = now

    db.session.flush()
    payout.recalculate_net()
    db.session.flush()

    for job_data in tech_data['jobs']:
        raw_job_id = job_data['job_id']
        job_id = None
        bundle_id = None
        if isinstance(raw_job_id, str) and raw_job_id.startswith('bundle:'):
            bundle_id = int(raw_job_id.split(':')[1])
        else:
            job_id = raw_job_id

        detail = PayoutJobDetail(
            payout_id=payout.payout_id,
            job_id=job_id,
            bundle_id=bundle_id,
            date_worked=job_data.get('date_worked'),
            hours=job_data['hours'],
            base_pay=job_data['base_pay'],
            mileage_pay=job_data['mileage_pay'],
            per_diem=job_data['per_diem'],
            personal_expenses=job_data['personal_expenses'],
            effective_rate=job_data['effective_rate'],
            profit_share=job_data.get('profit_share', 0),
        )
        db.session.add(detail)

    return payout


@payouts_bp.route('/lock', methods=['POST'])
@manager_required
def lock_payouts():
    """Lock all remaining payouts for a period — skips already-locked techs."""
    data = request.get_json()
    period_id = data.get('period_id')
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    period = PayPeriod.query.get_or_404(period_id)
    if period.status not in ('open',):
        return jsonify({'error': f'Period is {period.status}, must be open to lock'}), 400

    already_locked_tech_ids = {
        p.tech_id for p in Payout.query.filter_by(period_id=period_id).all()
    }

    pay_data = calculate_period_pay(period_id=period_id)
    if not pay_data or not pay_data['technicians']:
        return jsonify({'error': 'No technician pay data found for this period'}), 400

    now = datetime.utcnow()
    payouts_created = []

    for tech_data in pay_data['technicians']:
        if tech_data['tech_id'] in already_locked_tech_ids:
            continue
        payout = _create_payout_for_tech(period_id, tech_data, now)
        payouts_created.append(payout)

    period.status = 'locked'
    db.session.commit()

    return jsonify({
        'message': f'Locked {len(payouts_created)} payouts',
        'payouts': [p.to_dict() for p in payouts_created]
    })


@payouts_bp.route('/lock-tech', methods=['POST'])
@manager_required
def lock_single_tech():
    """Lock payout for a single technician — period stays open."""
    data = request.get_json()
    period_id = data.get('period_id')
    tech_id = data.get('tech_id')
    if not period_id or not tech_id:
        return jsonify({'error': 'period_id and tech_id required'}), 400

    period = PayPeriod.query.get_or_404(period_id)
    if period.status not in ('open',):
        return jsonify({'error': f'Period is {period.status}, must be open to lock individual techs'}), 400

    existing = Payout.query.filter_by(period_id=period_id, tech_id=tech_id).first()
    if existing:
        return jsonify({'error': 'Payout already exists for this technician'}), 400

    pay_data = calculate_period_pay(period_id=period_id)
    if not pay_data or not pay_data['technicians']:
        return jsonify({'error': 'No pay data found'}), 400

    tech_data = next((t for t in pay_data['technicians'] if t['tech_id'] == tech_id), None)
    if not tech_data:
        return jsonify({'error': 'Technician has no entries in this period'}), 400

    now = datetime.utcnow()
    payout = _create_payout_for_tech(period_id, tech_data, now)
    db.session.commit()

    return jsonify({
        'message': f'Locked payout for {tech_data["tech_name"]}',
        'payout': payout.to_dict()
    })


@payouts_bp.route('/<int:payout_id>/unlock', methods=['POST'])
@manager_required
def unlock_payout(payout_id):
    """Unlock a single payout — reverses advance repayments, deletes payout, reopens period."""
    payout = Payout.query.get_or_404(payout_id)
    if payout.status not in ('locked',):
        return jsonify({'error': f'Payout is {payout.status}, can only unlock locked payouts'}), 400

    tech_name = payout.technician.name if payout.technician else 'Unknown'
    period_id = payout.period_id

    for repayment in payout.advance_repayments.all():
        advance = Advance.query.get(repayment.advance_id)
        if advance:
            advance.remaining_balance = Decimal(str(advance.remaining_balance)) + Decimal(str(repayment.amount))
            if advance.status == 'repaid':
                advance.status = 'active'
                advance.repaid_at = None

    # Un-resolve any adjustments that were carried forward into this payout
    for adj in payout.adjustments.all():
        if adj.resolution == 'carried_forward' and adj.resolved_to_period_id == period_id:
            adj.resolution = 'pending'
            adj.resolved_to_period_id = None
            adj.resolved_by = None
            adj.resolved_at = None

    db.session.delete(payout)

    period = PayPeriod.query.get(period_id)
    if period and period.status in ('locked', 'closed'):
        remaining = Payout.query.filter(
            Payout.period_id == period_id,
            Payout.payout_id != payout_id
        ).count()
        if remaining == 0 or period.status == 'locked':
            period.status = 'open'
            period.closed_at = None

    db.session.commit()
    return jsonify({'message': f'Payout unlocked for {tech_name}'})


@payouts_bp.route('/<int:payout_id>/pay', methods=['POST'])
@manager_required
def pay_payout(payout_id):
    """Mark a single payout as paid."""
    from flask import g
    payout = Payout.query.get_or_404(payout_id)
    if payout.status != 'locked':
        return jsonify({'error': 'Payout must be locked to mark as paid'}), 400

    payout.status = 'paid'
    payout.paid_at = datetime.utcnow()
    payout.paid_by = g.user_id

    # Auto-close period only if ALL techs with entries have payouts AND all are paid
    period = PayPeriod.query.get(payout.period_id)
    unpaid = Payout.query.filter_by(period_id=payout.period_id).filter(Payout.status != 'paid').count()
    if unpaid <= 1:
        from app.models import TimeEntry
        techs_with_entries = {
            t[0] for t in db.session.query(TimeEntry.tech_id).filter(
                TimeEntry.date_worked >= period.start_date,
                TimeEntry.date_worked <= period.end_date,
                TimeEntry.status.in_(['verified', 'billed', 'paid']),
                TimeEntry.tech_id.isnot(None)
            ).distinct().all()
        }
        techs_with_payouts = {
            p.tech_id for p in Payout.query.filter_by(period_id=payout.period_id).all()
        }
        if techs_with_entries.issubset(techs_with_payouts):
            period.status = 'closed'
            period.closed_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'message': 'Payout marked as paid', 'payout': payout.to_dict()})


@payouts_bp.route('/pay-all', methods=['POST'])
@manager_required
def pay_all_payouts():
    """Mark all locked payouts for a period as paid."""
    from flask import g
    data = request.get_json()
    period_id = data.get('period_id')
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    payouts = Payout.query.filter_by(period_id=period_id, status='locked').all()
    if not payouts:
        return jsonify({'error': 'No locked payouts found'}), 400

    now = datetime.utcnow()
    for payout in payouts:
        payout.status = 'paid'
        payout.paid_at = now
        payout.paid_by = g.user_id

    # Close the period
    period = PayPeriod.query.get(period_id)
    period.status = 'closed'
    period.closed_at = now

    db.session.commit()
    return jsonify({'message': f'Marked {len(payouts)} payouts as paid'})


@payouts_bp.route('/<int:payout_id>/line-items', methods=['POST'])
@manager_required
def add_line_item(payout_id):
    """Add a bonus or deduction to a locked payout."""
    from flask import g
    payout = Payout.query.get_or_404(payout_id)
    if payout.status != 'locked':
        return jsonify({'error': 'Can only add line items to locked payouts'}), 400

    data = request.get_json()
    item_type = data.get('type')
    if item_type not in ('bonus', 'deduction'):
        return jsonify({'error': 'type must be bonus or deduction'}), 400

    li = PayoutLineItem(
        payout_id=payout_id,
        type=item_type,
        description=data.get('description', ''),
        amount=data.get('amount', 0),
        created_by=g.user_id,
    )
    db.session.add(li)
    db.session.flush()
    payout.recalculate_net()
    db.session.commit()
    return jsonify({'message': 'Line item added', 'line_item': li.to_dict(), 'payout': payout.to_dict()})


@payouts_bp.route('/line-items/<int:item_id>', methods=['DELETE'])
@manager_required
def remove_line_item(item_id):
    """Remove a line item from a locked payout."""
    li = PayoutLineItem.query.get_or_404(item_id)
    payout = Payout.query.get(li.payout_id)
    if payout.status != 'locked':
        return jsonify({'error': 'Can only remove line items from locked payouts'}), 400

    db.session.delete(li)
    db.session.flush()
    payout.recalculate_net()
    db.session.commit()
    return jsonify({'message': 'Line item removed', 'payout': payout.to_dict()})


@payouts_bp.route('/<int:payout_id>/stub', methods=['GET'])
@manager_required
def get_stub(payout_id):
    """Get full pay stub data for a payout."""
    payout = Payout.query.get_or_404(payout_id)
    data = payout.to_dict()
    data['period'] = payout.pay_period.to_dict()
    data['job_details'] = [jd.to_dict() for jd in payout.job_details.all()]
    data['line_items'] = [li.to_dict() for li in payout.line_items.all()]
    data['advance_repayments'] = [ar.to_dict() for ar in payout.advance_repayments.all()]
    return jsonify(data)
