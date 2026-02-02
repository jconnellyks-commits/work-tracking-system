"""
System settings and pay calculation routes.
"""
import os
import subprocess
import glob
from datetime import datetime
from flask import Blueprint, request, jsonify, g, current_app
from app import db
from app.models import SystemSettings, MileageRateHistory
from app.utils.logging import get_logger, audit_logger
from app.utils.auth import jwt_required_with_user, admin_required, manager_required
from app.utils.pay_calculator import calculate_job_pay, calculate_tech_pay_summary

settings_bp = Blueprint('settings', __name__)
logger = get_logger(__name__)

# Backup directory
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')
SAFE_MODE_FILE = os.path.join(BACKUP_DIR, '.safe_mode')


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


# ============ Database Backup/Restore ============

def get_db_credentials():
    """Get database credentials from config."""
    from app.config import get_config
    config = get_config()
    return {
        'host': config.DB_HOST,
        'port': config.DB_PORT,
        'user': config.DB_USER,
        'password': config.DB_PASSWORD,
        'database': config.DB_NAME
    }


def ensure_backup_dir():
    """Ensure backup directory exists."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


@settings_bp.route('/backups', methods=['GET'])
@admin_required
def list_backups():
    """List all available backups."""
    ensure_backup_dir()

    backups = []
    for filepath in glob.glob(os.path.join(BACKUP_DIR, '*.sql')):
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        backups.append({
            'filename': filename,
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_safe_mode': filename.startswith('safe_mode_')
        })

    # Sort by date, newest first
    backups.sort(key=lambda x: x['created_at'], reverse=True)

    return jsonify({'backups': backups}), 200


@settings_bp.route('/backups', methods=['POST'])
@admin_required
def create_backup():
    """Create a new database backup."""
    ensure_backup_dir()

    data = request.get_json() or {}
    label = data.get('label', '')

    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if label:
        safe_label = ''.join(c if c.isalnum() or c in '-_' else '_' for c in label)
        filename = f"backup_{timestamp}_{safe_label}.sql"
    else:
        filename = f"backup_{timestamp}.sql"

    filepath = os.path.join(BACKUP_DIR, filename)

    # Get credentials
    creds = get_db_credentials()

    try:
        # Run mysqldump
        cmd = [
            'mysqldump',
            f'--host={creds["host"]}',
            f'--port={creds["port"]}',
            f'--user={creds["user"]}',
            f'--password={creds["password"]}',
            '--single-transaction',
            '--routines',
            '--triggers',
            creds['database']
        ]

        with open(filepath, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else 'Unknown error'
            # Remove failed backup file
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Backup failed: {error_msg}'}), 500

        stat = os.stat(filepath)

        audit_logger.log(
            action_type='backup_created',
            entity_type='system',
            description=f"Database backup created: {filename}",
            user_id=g.user_id
        )

        return jsonify({
            'message': 'Backup created successfully',
            'backup': {
                'filename': filename,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created_at': datetime.now().isoformat()
            }
        }), 201

    except subprocess.TimeoutExpired:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Backup timed out'}), 500
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Backup failed: {str(e)}'}), 500


@settings_bp.route('/backups/<filename>/restore', methods=['POST'])
@admin_required
def restore_backup(filename):
    """Restore database from a backup file."""
    ensure_backup_dir()

    # Validate filename (prevent directory traversal)
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup file not found'}), 404

    # Get credentials
    creds = get_db_credentials()

    try:
        # Run mysql restore
        cmd = [
            'mysql',
            f'--host={creds["host"]}',
            f'--port={creds["port"]}',
            f'--user={creds["user"]}',
            f'--password={creds["password"]}',
            creds['database']
        ]

        with open(filepath, 'r') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else 'Unknown error'
            return jsonify({'error': f'Restore failed: {error_msg}'}), 500

        audit_logger.log(
            action_type='backup_restored',
            entity_type='system',
            description=f"Database restored from: {filename}",
            user_id=g.user_id
        )

        return jsonify({'message': f'Database restored from {filename}'}), 200

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Restore timed out'}), 500
    except Exception as e:
        return jsonify({'error': f'Restore failed: {str(e)}'}), 500


@settings_bp.route('/backups/<filename>', methods=['DELETE'])
@admin_required
def delete_backup(filename):
    """Delete a backup file."""
    ensure_backup_dir()

    # Validate filename
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup file not found'}), 404

    os.remove(filepath)

    audit_logger.log(
        action_type='backup_deleted',
        entity_type='system',
        description=f"Backup deleted: {filename}",
        user_id=g.user_id
    )

    return jsonify({'message': 'Backup deleted'}), 200


@settings_bp.route('/backups/<filename>/download', methods=['GET'])
@admin_required
def download_backup(filename):
    """Download a backup file."""
    from flask import send_file
    ensure_backup_dir()

    # Validate filename
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup file not found'}), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='application/sql'
    )


# ============ Safe Mode ============

@settings_bp.route('/safe-mode', methods=['GET'])
@admin_required
def get_safe_mode_status():
    """Check if safe mode is active."""
    ensure_backup_dir()

    if os.path.exists(SAFE_MODE_FILE):
        with open(SAFE_MODE_FILE, 'r') as f:
            backup_filename = f.read().strip()
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        if os.path.exists(backup_path):
            stat = os.stat(backup_path)
            return jsonify({
                'active': True,
                'backup_filename': backup_filename,
                'started_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
            }), 200

    return jsonify({'active': False}), 200


@settings_bp.route('/safe-mode/enter', methods=['POST'])
@admin_required
def enter_safe_mode():
    """Enter safe mode - creates a snapshot backup."""
    ensure_backup_dir()

    # Check if already in safe mode
    if os.path.exists(SAFE_MODE_FILE):
        return jsonify({'error': 'Already in safe mode'}), 400

    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"safe_mode_{timestamp}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)

    creds = get_db_credentials()

    try:
        cmd = [
            'mysqldump',
            f'--host={creds["host"]}',
            f'--port={creds["port"]}',
            f'--user={creds["user"]}',
            f'--password={creds["password"]}',
            '--single-transaction',
            '--routines',
            '--triggers',
            creds['database']
        ]

        with open(filepath, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            if os.path.exists(filepath):
                os.remove(filepath)
            error_msg = result.stderr.decode() if result.stderr else 'Unknown error'
            return jsonify({'error': f'Failed to create snapshot: {error_msg}'}), 500

        # Store safe mode state
        with open(SAFE_MODE_FILE, 'w') as f:
            f.write(filename)

        audit_logger.log(
            action_type='safe_mode_entered',
            entity_type='system',
            description=f"Safe mode entered, snapshot: {filename}",
            user_id=g.user_id
        )

        return jsonify({
            'message': 'Safe mode activated. A snapshot has been created.',
            'backup_filename': filename
        }), 200

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Failed to enter safe mode: {str(e)}'}), 500


@settings_bp.route('/safe-mode/commit', methods=['POST'])
@admin_required
def commit_safe_mode():
    """Exit safe mode - keep changes, delete snapshot."""
    ensure_backup_dir()

    if not os.path.exists(SAFE_MODE_FILE):
        return jsonify({'error': 'Not in safe mode'}), 400

    # Read and delete the safe mode backup
    with open(SAFE_MODE_FILE, 'r') as f:
        backup_filename = f.read().strip()

    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    if os.path.exists(backup_path):
        os.remove(backup_path)

    os.remove(SAFE_MODE_FILE)

    audit_logger.log(
        action_type='safe_mode_committed',
        entity_type='system',
        description="Safe mode exited, changes committed",
        user_id=g.user_id
    )

    return jsonify({'message': 'Safe mode exited. Changes have been committed.'}), 200


@settings_bp.route('/safe-mode/revert', methods=['POST'])
@admin_required
def revert_safe_mode():
    """Exit safe mode - revert to snapshot."""
    ensure_backup_dir()

    if not os.path.exists(SAFE_MODE_FILE):
        return jsonify({'error': 'Not in safe mode'}), 400

    with open(SAFE_MODE_FILE, 'r') as f:
        backup_filename = f.read().strip()

    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    if not os.path.exists(backup_path):
        os.remove(SAFE_MODE_FILE)
        return jsonify({'error': 'Snapshot file not found'}), 404

    # Restore the backup
    creds = get_db_credentials()

    try:
        cmd = [
            'mysql',
            f'--host={creds["host"]}',
            f'--port={creds["port"]}',
            f'--user={creds["user"]}',
            f'--password={creds["password"]}',
            creds['database']
        ]

        with open(backup_path, 'r') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else 'Unknown error'
            return jsonify({'error': f'Restore failed: {error_msg}'}), 500

        # Clean up
        os.remove(backup_path)
        os.remove(SAFE_MODE_FILE)

        audit_logger.log(
            action_type='safe_mode_reverted',
            entity_type='system',
            description="Safe mode exited, changes reverted",
            user_id=g.user_id
        )

        return jsonify({'message': 'Database reverted to snapshot. Changes discarded.'}), 200

    except Exception as e:
        return jsonify({'error': f'Revert failed: {str(e)}'}), 500
