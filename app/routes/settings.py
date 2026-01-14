"""
System settings and pay calculation routes.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import SystemSettings, MileageRateHistory
from app.utils.logging import get_logger, audit_logger
from app.utils.auth import jwt_required_with_user, admin_required, manager_required
from app.utils.pay_calculator import calculate_job_pay, calculate_tech_pay_summary

settings_bp = Blueprint('settings', __name__)
logger = get_logger(__name__)


# ============ System Settings ============

@settings_bp.route('', methods=['GET'])
@manager_required
def list_settings():
    """List all system settings."""
    settings = SystemSettings.query.all()
    return jsonify({
        'settings': [s.to_dict() for s in settings]
    }), 200


@settings_bp.route('/<key>', methods=['GET'])
@jwt_required_with_user
def get_setting(key):
    """Get a specific setting by key."""
    setting = SystemSettings.query.filter_by(setting_key=key).first()
    if not setting:
        return jsonify({'error': 'Setting not found'}), 404
    return jsonify({'setting': setting.to_dict()}), 200


@settings_bp.route('', methods=['POST'])
@admin_required
def create_setting():
    """
    Create a new system setting.

    Request body:
        {
            "setting_key": "per_mile_rate",
            "setting_value": "0.67",
            "description": "IRS standard mileage rate",
            "effective_date": "2026-01-01"
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    key = data.get('setting_key', '').strip()
    value = data.get('setting_value', '').strip()

    if not key or not value:
        return jsonify({'error': 'Setting key and value required'}), 400

    if SystemSettings.query.filter_by(setting_key=key).first():
        return jsonify({'error': 'Setting already exists'}), 409

    effective_date = None
    if data.get('effective_date'):
        effective_date = datetime.strptime(data['effective_date'], '%Y-%m-%d').date()

    setting = SystemSettings(
        setting_key=key,
        setting_value=value,
        description=data.get('description', '').strip() or None,
        effective_date=effective_date
    )

    db.session.add(setting)
    db.session.commit()

    audit_logger.log(
        action_type='setting_created',
        entity_type='system_setting',
        entity_id=setting.setting_id,
        new_values=setting.to_dict(),
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Setting created',
        'setting': setting.to_dict()
    }), 201


@settings_bp.route('/<key>', methods=['PUT'])
@admin_required
def update_setting(key):
    """Update a system setting."""
    setting = SystemSettings.query.filter_by(setting_key=key).first()
    if not setting:
        return jsonify({'error': 'Setting not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = setting.to_dict()

    if 'setting_value' in data:
        setting.setting_value = str(data['setting_value']).strip()

    if 'description' in data:
        setting.description = data['description'].strip() if data['description'] else None

    if 'effective_date' in data:
        if data['effective_date']:
            setting.effective_date = datetime.strptime(data['effective_date'], '%Y-%m-%d').date()
        else:
            setting.effective_date = None

    db.session.commit()

    audit_logger.log(
        action_type='setting_updated',
        entity_type='system_setting',
        entity_id=setting.setting_id,
        old_values=old_values,
        new_values=setting.to_dict(),
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Setting updated',
        'setting': setting.to_dict()
    }), 200


# ============ Mileage Rate History ============

@settings_bp.route('/mileage-rates', methods=['GET'])
@jwt_required_with_user
def list_mileage_rates():
    """List all mileage rates."""
    rates = MileageRateHistory.query.order_by(MileageRateHistory.effective_date.desc()).all()
    return jsonify({
        'mileage_rates': [r.to_dict() for r in rates]
    }), 200


@settings_bp.route('/mileage-rates', methods=['POST'])
@admin_required
def create_mileage_rate():
    """
    Create a new mileage rate.

    Request body:
        {
            "rate_per_mile": 0.67,
            "effective_date": "2026-01-01",
            "description": "2026 IRS standard mileage rate"
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    rate = data.get('rate_per_mile')
    effective_date = data.get('effective_date')

    if rate is None or not effective_date:
        return jsonify({'error': 'Rate and effective date required'}), 400

    effective_date = datetime.strptime(effective_date, '%Y-%m-%d').date()

    # Close any existing open-ended rate
    open_rate = MileageRateHistory.query.filter(
        MileageRateHistory.end_date.is_(None),
        MileageRateHistory.effective_date < effective_date
    ).first()

    if open_rate:
        # Set end date to day before new rate starts
        from datetime import timedelta
        open_rate.end_date = effective_date - timedelta(days=1)

    new_rate = MileageRateHistory(
        rate_per_mile=rate,
        effective_date=effective_date,
        description=data.get('description', '').strip() or None
    )

    db.session.add(new_rate)
    db.session.commit()

    audit_logger.log(
        action_type='mileage_rate_created',
        entity_type='mileage_rate',
        entity_id=new_rate.rate_id,
        new_values=new_rate.to_dict(),
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Mileage rate created',
        'mileage_rate': new_rate.to_dict()
    }), 201


@settings_bp.route('/mileage-rates/current', methods=['GET'])
@jwt_required_with_user
def get_current_mileage_rate():
    """Get the current effective mileage rate."""
    rate = MileageRateHistory.get_rate_for_date(datetime.utcnow().date())
    return jsonify({
        'rate_per_mile': rate
    }), 200


# ============ Pay Calculations ============

@settings_bp.route('/pay/job/<int:job_id>', methods=['GET'])
@manager_required
def get_job_pay(job_id):
    """
    Calculate and return pay breakdown for a job.

    Returns detailed pay calculation for all technicians on the job.
    """
    result = calculate_job_pay(job_id)
    if not result:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(result), 200


@settings_bp.route('/pay/technician/<int:tech_id>', methods=['GET'])
@manager_required
def get_tech_pay(tech_id):
    """
    Calculate and return pay summary for a technician.

    Query parameters:
        - start_date: Filter entries from this date
        - end_date: Filter entries until this date
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    result = calculate_tech_pay_summary(tech_id, start_date, end_date)
    return jsonify(result), 200
