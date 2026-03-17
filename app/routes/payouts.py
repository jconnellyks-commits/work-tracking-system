"""Payout management routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify
from app import db
from app.models import (
    Payout, PayoutJobDetail, PayoutLineItem, PayPeriod,
    Advance, AdvanceRepayment, Technician
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

    payouts = Payout.query.filter_by(period_id=period_id).all()
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


@payouts_bp.route('/lock', methods=['POST'])
@manager_required
def lock_payouts():
    """Lock all payouts for a period — creates snapshot records."""
    data = request.get_json()
    period_id = data.get('period_id')
    if not period_id:
        return jsonify({'error': 'period_id required'}), 400

    period = PayPeriod.query.get_or_404(period_id)
    if period.status != 'open':
        return jsonify({'error': f'Period is {period.status}, must be open to lock'}), 400

    # Check no existing payouts
    existing = Payout.query.filter_by(period_id=period_id).first()
    if existing:
        return jsonify({'error': 'Payouts already exist for this period'}), 400

    # Calculate period pay
    pay_data = calculate_period_pay(period_id=period_id)
    if not pay_data or not pay_data['technicians']:
        return jsonify({'error': 'No technician pay data found for this period'}), 400

    now = datetime.utcnow()
    payouts_created = []

    for tech_data in pay_data['technicians']:
        tech_id = tech_data['tech_id']

        # Create payout record
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
        db.session.flush()  # Get payout_id for FKs

        # Calculate net before advances
        net_before_advances = (
            float(payout.total_base_pay) + float(payout.total_mileage_pay)
            + float(payout.total_per_diem) + float(payout.total_personal_expenses)
        )

        # Process advance repayments (oldest first)
        total_advance_repayment = 0
        active_advances = Advance.query.filter_by(
            tech_id=tech_id, status='active'
        ).order_by(Advance.created_at.asc()).all()

        available = net_before_advances
        for advance in active_advances:
            if available <= 0:
                break
            cap = float(advance.max_per_period or advance.remaining_balance)
            repay = min(cap, float(advance.remaining_balance), available)
            if repay > 0:
                repayment = AdvanceRepayment(
                    advance_id=advance.advance_id,
                    payout_id=payout.payout_id,
                    amount=repay,
                )
                db.session.add(repayment)
                advance.remaining_balance = float(advance.remaining_balance) - repay
                if advance.remaining_balance <= 0:
                    advance.remaining_balance = 0
                    advance.status = 'repaid'
                    advance.repaid_at = now
                total_advance_repayment += repay
                available -= repay

        payout.total_advance_repayment = total_advance_repayment
        db.session.flush()
        payout.recalculate_net()
        db.session.flush()

        # Create job detail snapshots
        for job_data in tech_data['jobs']:
            detail = PayoutJobDetail(
                payout_id=payout.payout_id,
                job_id=job_data['job_id'],
                hours=job_data['hours'],
                base_pay=job_data['base_pay'],
                mileage_pay=job_data['mileage_pay'],
                per_diem=job_data['per_diem'],
                personal_expenses=job_data['personal_expenses'],
                effective_rate=job_data['effective_rate'],
                profit_share=job_data.get('profit_share', 0),
            )
            db.session.add(detail)

        payouts_created.append(payout)

    # Lock the period
    period.status = 'locked'
    db.session.commit()

    return jsonify({
        'message': f'Locked {len(payouts_created)} payouts',
        'payouts': [p.to_dict() for p in payouts_created]
    })


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

    # Check if all payouts for this period are now paid
    period = PayPeriod.query.get(payout.period_id)
    unpaid = Payout.query.filter_by(period_id=payout.period_id).filter(Payout.status != 'paid').count()
    if unpaid <= 1:  # This one is about to be paid
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
