"""Payout adjustment routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import PayoutAdjustment, Payout, PayoutLineItem, PayPeriod
from app.utils.auth import manager_required

payout_adjustments_bp = Blueprint('payout_adjustments', __name__)


@payout_adjustments_bp.route('/', methods=['GET'])
@manager_required
def list_adjustments():
    """List adjustments, filtered by period and/or resolution status."""
    query = PayoutAdjustment.query.join(Payout)
    period_id = request.args.get('period_id', type=int)
    tech_id = request.args.get('tech_id', type=int)
    resolution = request.args.get('resolution')
    if period_id:
        query = query.filter(Payout.period_id == period_id)
    if tech_id:
        query = query.filter(Payout.tech_id == tech_id)
    if resolution:
        query = query.filter(PayoutAdjustment.resolution == resolution)
    adjustments = query.order_by(PayoutAdjustment.created_at.desc()).all()
    return jsonify({'adjustments': [a.to_dict() for a in adjustments]})


@payout_adjustments_bp.route('/<int:adj_id>/resolve', methods=['POST'])
@manager_required
def resolve_adjustment(adj_id):
    """Resolve an adjustment — carry forward or dismiss."""
    adj = PayoutAdjustment.query.get_or_404(adj_id)
    if adj.resolution != 'pending':
        return jsonify({'error': 'Adjustment already resolved'}), 400

    data = request.get_json()
    resolution = data.get('resolution')
    if resolution not in ('carried_forward', 'dismissed'):
        return jsonify({'error': 'resolution must be carried_forward or dismissed'}), 400

    adj.resolution = resolution
    adj.resolved_by = g.user_id
    adj.resolved_at = datetime.utcnow()

    if resolution == 'carried_forward':
        # Find the tech's next open payout period
        payout = Payout.query.get(adj.payout_id)
        next_period = PayPeriod.query.filter(
            PayPeriod.status == 'open',
            PayPeriod.start_date > payout.pay_period.end_date
        ).order_by(PayPeriod.start_date.asc()).first()

        if not next_period:
            return jsonify({'error': 'No open future pay period found to carry forward to'}), 400

        adj.resolved_to_period_id = next_period.period_id

        # If the next period already has a locked payout for this tech, add a line item now
        next_payout = Payout.query.filter_by(
            period_id=next_period.period_id, tech_id=payout.tech_id
        ).first()

        if next_payout and next_payout.status == 'locked':
            li_type = 'bonus' if adj.amount_diff >= 0 else 'deduction'
            li = PayoutLineItem(
                payout_id=next_payout.payout_id,
                type=li_type,
                description=f'Carried forward: {adj.description}',
                amount=abs(adj.amount_diff),
                created_by=g.user_id,
            )
            db.session.add(li)
            db.session.flush()
            next_payout.recalculate_net()

    db.session.commit()
    return jsonify({'message': f'Adjustment {resolution}', 'adjustment': adj.to_dict()})
