"""Technician self-service routes."""
from flask import Blueprint, jsonify, g
from app.models import Payout, PayPeriod, User
from app.utils.auth import jwt_required_with_user
from datetime import date

my_bp = Blueprint('my', __name__)


@my_bp.route('/dashboard', methods=['GET'])
@jwt_required_with_user
def my_dashboard():
    """Tech dashboard — YTD earnings, last payout, next period."""
    user = User.query.get(g.user_id)
    if not user or not user.tech_id:
        return jsonify({'error': 'No technician profile linked'}), 400

    tech_id = user.tech_id
    current_year = date.today().year

    # YTD earnings — sum of net_payout for paid payouts this year
    paid_payouts = Payout.query.filter_by(
        tech_id=tech_id, status='paid'
    ).join(PayPeriod).filter(
        PayPeriod.end_date >= date(current_year, 1, 1)
    ).all()

    ytd_earnings = sum(float(p.net_payout or 0) for p in paid_payouts)

    # Last payout
    last_payout = Payout.query.filter_by(
        tech_id=tech_id, status='paid'
    ).order_by(Payout.paid_at.desc()).first()

    # Next period end date
    next_period = PayPeriod.query.filter(
        PayPeriod.status.in_(['open', 'locked']),
        PayPeriod.end_date >= date.today()
    ).order_by(PayPeriod.end_date.asc()).first()

    return jsonify({
        'ytd_earnings': ytd_earnings,
        'last_payout': {
            'amount': float(last_payout.net_payout or 0),
            'paid_at': last_payout.paid_at.isoformat() if last_payout and last_payout.paid_at else None,
            'period_name': last_payout.pay_period.period_name if last_payout else None,
        } if last_payout else None,
        'next_period_end': next_period.end_date.isoformat() if next_period else None,
    })


@my_bp.route('/payouts', methods=['GET'])
@jwt_required_with_user
def my_payouts():
    """List tech's paid payouts."""
    user = User.query.get(g.user_id)
    if not user or not user.tech_id:
        return jsonify({'error': 'No technician profile linked'}), 400

    payouts = Payout.query.filter_by(
        tech_id=user.tech_id, status='paid'
    ).join(PayPeriod).order_by(PayPeriod.end_date.desc()).all()

    return jsonify({
        'payouts': [{
            **p.to_dict(),
            'period': p.pay_period.to_dict()
        } for p in payouts]
    })


@my_bp.route('/payouts/<int:payout_id>/stub', methods=['GET'])
@jwt_required_with_user
def my_stub(payout_id):
    """View own pay stub — must be paid and belong to this tech."""
    user = User.query.get(g.user_id)
    if not user or not user.tech_id:
        return jsonify({'error': 'No technician profile linked'}), 400

    payout = Payout.query.get_or_404(payout_id)
    if payout.tech_id != user.tech_id:
        return jsonify({'error': 'Not your payout'}), 403
    if payout.status != 'paid':
        return jsonify({'error': 'Stub not available yet'}), 403

    data = payout.to_dict()
    data['period'] = payout.pay_period.to_dict()
    data['job_details'] = [jd.to_dict() for jd in payout.job_details.all()]
    data['line_items'] = [li.to_dict() for li in payout.line_items.all()]
    data['advance_repayments'] = [ar.to_dict() for ar in payout.advance_repayments.all()]
    return jsonify(data)
