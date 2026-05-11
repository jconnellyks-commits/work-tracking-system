"""
Email parser status and activity log endpoints.
"""

import subprocess
import re
from datetime import datetime

from flask import Blueprint, request, jsonify
from app.models import db, EmailParserLog
from app.utils.auth import jwt_required_with_user, admin_required

email_parser_bp = Blueprint('email_parser', __name__)


@email_parser_bp.route('/status', methods=['GET'])
@admin_required
def get_status():
    """Check email-parser systemd service status via subprocess."""
    try:
        result = subprocess.run(
            ['systemctl', 'show', 'email-parser',
             '--property=ActiveState,SubState,ExecMainStartTimestamp,NRestarts'],
            capture_output=True, text=True, timeout=5
        )
        props = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, val = line.split('=', 1)
                props[key.strip()] = val.strip()

        active_state = props.get('ActiveState', 'unknown')
        running = active_state == 'active'

        since_raw = props.get('ExecMainStartTimestamp', '')
        since = None
        uptime = None
        if since_raw and since_raw != 'n/a':
            ts_clean = re.sub(r'^[A-Za-z]+ ', '', since_raw)
            ts_clean = re.sub(r' [A-Z]{2,4}$', '', ts_clean)
            try:
                start_dt = datetime.strptime(ts_clean, '%Y-%m-%d %H:%M:%S')
                since = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                if running:
                    delta = datetime.now() - start_dt
                    total_seconds = int(delta.total_seconds())
                    days = total_seconds // 86400
                    hours = (total_seconds % 86400) // 3600
                    minutes = (total_seconds % 3600) // 60
                    parts = []
                    if days > 0:
                        parts.append(f"{days}d")
                    if hours > 0:
                        parts.append(f"{hours}h")
                    parts.append(f"{minutes}m")
                    uptime = ' '.join(parts)
            except ValueError:
                pass

        restart_count = int(props.get('NRestarts', 0))

        return jsonify({
            'running': running,
            'state': props.get('SubState', 'unknown'),
            'uptime': uptime,
            'since': since,
            'restart_count': restart_count,
        })

    except subprocess.TimeoutExpired:
        return jsonify({'running': False, 'state': 'timeout', 'uptime': None, 'since': None, 'restart_count': 0})
    except FileNotFoundError:
        return jsonify({'running': False, 'state': 'systemctl not found', 'uptime': None, 'since': None, 'restart_count': 0})


@email_parser_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """Return paginated, filterable activity log."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    platform = request.args.get('platform')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = EmailParserLog.query

    if platform:
        query = query.filter(EmailParserLog.platform == platform)
    if status:
        query = query.filter(EmailParserLog.status == status)
    if date_from:
        try:
            query = query.filter(EmailParserLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(EmailParserLog.timestamp <= dt_to)
        except ValueError:
            pass

    query = query.order_by(EmailParserLog.timestamp.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'logs': [log.to_dict() for log in pagination.items],
        'page': pagination.page,
        'pages': pagination.pages,
        'total': pagination.total,
    })


@email_parser_bp.route('/logs', methods=['POST'])
@jwt_required_with_user
def create_log():
    """Create a log entry (called by the email parser daemon)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['platform', 'email_type', 'subject', 'status']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    log = EmailParserLog(
        platform=data['platform'],
        email_type=data['email_type'],
        ticket_number=data.get('ticket_number'),
        client_name=data.get('client_name'),
        subject=data['subject'],
        status=data['status'],
        job_id=data.get('job_id'),
        error_message=data.get('error_message'),
        gmail_message_id=data.get('gmail_message_id'),
    )
    db.session.add(log)
    db.session.commit()

    return jsonify(log.to_dict()), 201
