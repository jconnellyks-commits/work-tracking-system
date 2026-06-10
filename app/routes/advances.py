"""Advance management routes."""
from datetime import datetime, date
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import Advance
from app.utils.auth import manager_required

advances_bp = Blueprint('advances', __name__)


@advances_bp.route('/', methods=['GET'])
@manager_required
def list_advances():
    """List advances, optionally filtered by tech and status."""
    query = Advance.query
    tech_id = request.args.get('tech_id', type=int)
    status = request.args.get('status')
    if tech_id:
        query = query.filter_by(tech_id=tech_id)
    if status:
        query = query.filter_by(status=status)
    advances = query.order_by(Advance.created_at.desc()).all()
    return jsonify({'advances': [a.to_dict() for a in advances]})


@advances_bp.route('/', methods=['POST'])
@manager_required
def create_advance():
    """Create a new advance for a technician."""
    data = request.get_json()
    tech_id = data.get('tech_id')
    amount = float(data.get('original_amount', 0))
    if not tech_id or amount <= 0:
        return jsonify({'error': 'tech_id and positive original_amount required'}), 400

    date_given = None
    if data.get('date_given'):
        date_given = date.fromisoformat(data['date_given'])

    advance = Advance(
        tech_id=tech_id,
        description=data.get('description', ''),
        original_amount=amount,
        remaining_balance=amount,
        max_per_period=data.get('max_per_period'),
        date_given=date_given,
        created_by=g.user_id,
    )
    db.session.add(advance)
    db.session.commit()
    return jsonify({'message': 'Advance created', 'advance': advance.to_dict()}), 201


@advances_bp.route('/<int:advance_id>', methods=['PUT'])
@manager_required
def update_advance(advance_id):
    """Update an advance (e.g. change max_per_period)."""
    advance = Advance.query.get_or_404(advance_id)
    if advance.status != 'active':
        return jsonify({'error': 'Can only update active advances'}), 400

    data = request.get_json()
    if 'max_per_period' in data:
        advance.max_per_period = data['max_per_period']
    if 'description' in data:
        advance.description = data['description']
    if 'date_given' in data:
        advance.date_given = date.fromisoformat(data['date_given']) if data['date_given'] else None

    db.session.commit()
    return jsonify({'message': 'Advance updated', 'advance': advance.to_dict()})


@advances_bp.route('/<int:advance_id>/cancel', methods=['POST'])
@manager_required
def cancel_advance(advance_id):
    """Cancel an active advance."""
    advance = Advance.query.get_or_404(advance_id)
    if advance.status != 'active':
        return jsonify({'error': 'Can only cancel active advances'}), 400

    advance.status = 'cancelled'
    db.session.commit()
    return jsonify({'message': 'Advance cancelled', 'advance': advance.to_dict()})
