"""
Reporting routes for generating various work tracking reports.
Includes payroll, job billing, technician hours, and audit reports.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func, and_
from app import db
from app.models import (
    TimeEntry, Job, Technician, Platform, PayPeriod, AuditLog, User
)
from app.utils.logging import get_logger, audit_logger
from app.utils.auth import (
    jwt_required_with_user,
    manager_required,
    admin_required,
    can_access_technician_data,
)
from app.utils.pay_calculator import calculate_job_pay

reports_bp = Blueprint('reports', __name__)
logger = get_logger(__name__)


@reports_bp.route('/payroll', methods=['GET'])
@manager_required
def payroll_report():
    """
    Generate payroll report for a pay period.

    Query parameters:
        - period_id: Pay period ID (required or use date range)
        - from_date: Start date
        - to_date: End date
        - tech_id: Filter by technician (optional)
    """
    period_id = request.args.get('period_id', type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    tech_id = request.args.get('tech_id', type=int)

    # Build base query
    query = db.session.query(
        Technician.tech_id,
        Technician.name,
        Technician.hourly_rate,
        func.count(TimeEntry.entry_id).label('entry_count'),
        func.sum(TimeEntry.hours_worked).label('total_hours')
    ).join(
        TimeEntry, TimeEntry.tech_id == Technician.tech_id
    ).filter(
        TimeEntry.status.in_(['verified', 'billed', 'paid'])
    )

    # Apply filters
    if period_id:
        query = query.filter(TimeEntry.period_id == period_id)
    elif from_date and to_date:
        query = query.filter(
            and_(
                TimeEntry.date_worked >= from_date,
                TimeEntry.date_worked <= to_date
            )
        )
    else:
        return jsonify({'error': 'Period ID or date range required'}), 400

    if tech_id:
        query = query.filter(Technician.tech_id == tech_id)

    query = query.group_by(
        Technician.tech_id, Technician.name, Technician.hourly_rate
    )

    results = query.all()

    payroll_data = []
    grand_total_hours = Decimal('0')
    grand_total_pay = Decimal('0')

    for row in results:
        hours = Decimal(str(row.total_hours or 0))
        rate = Decimal(str(row.hourly_rate or 0))
        total_pay = hours * rate

        payroll_data.append({
            'tech_id': row.tech_id,
            'name': row.name,
            'hourly_rate': float(rate),
            'entry_count': row.entry_count,
            'total_hours': float(hours),
            'total_pay': float(total_pay)
        })

        grand_total_hours += hours
        grand_total_pay += total_pay

    # Log report generation
    audit_logger.log(
        action_type='report_generated',
        entity_type='payroll_report',
        description=f"Payroll report generated for period {period_id or f'{from_date} to {to_date}'}",
        user_id=g.user_id
    )

    return jsonify({
        'report_type': 'payroll',
        'period_id': period_id,
        'from_date': from_date,
        'to_date': to_date,
        'generated_at': datetime.utcnow().isoformat(),
        'data': payroll_data,
        'summary': {
            'technician_count': len(payroll_data),
            'total_hours': float(grand_total_hours),
            'total_pay': float(grand_total_pay)
        }
    }), 200


@reports_bp.route('/payroll-detail', methods=['GET'])
@manager_required
def payroll_detail_report():
    """
    Generate detailed payroll report with per-job pay breakdowns.

    Query parameters:
        - from_date: Start date (required)
        - to_date: End date (required)
        - tech_id: Filter by specific technician (optional)

    Returns detailed pay breakdown for each technician showing:
        - All jobs worked with pay calculation
        - Base pay, mileage, per diem, expenses per job
        - Using minimum rate indicator
        - Grand totals
    """
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    tech_id = request.args.get('tech_id', type=int)

    if not from_date or not to_date:
        return jsonify({'error': 'Date range required'}), 400

    # Get all time entries in the period
    entry_query = TimeEntry.query.filter(
        TimeEntry.date_worked >= from_date,
        TimeEntry.date_worked <= to_date,
        TimeEntry.status.in_(['verified', 'billed', 'paid'])
    )

    if tech_id:
        entry_query = entry_query.filter(TimeEntry.tech_id == tech_id)

    entries = entry_query.all()

    # Group entries by technician and find unique jobs
    tech_jobs = {}  # {tech_id: set(job_ids)}
    for entry in entries:
        if entry.tech_id not in tech_jobs:
            tech_jobs[entry.tech_id] = set()
        tech_jobs[entry.tech_id].add(entry.job_id)

    # Build detailed report for each technician
    technicians_report = []
    grand_totals = {
        'total_hours': Decimal('0'),
        'total_base_pay': Decimal('0'),
        'total_mileage_pay': Decimal('0'),
        'total_per_diem': Decimal('0'),
        'total_personal_expenses': Decimal('0'),
        'total_pay': Decimal('0')
    }

    for tid, job_ids in tech_jobs.items():
        tech = Technician.query.get(tid)
        if not tech:
            continue

        tech_data = {
            'tech_id': tid,
            'tech_name': tech.name,
            'min_pay': float(tech.hourly_rate or 0),
            'jobs': [],
            'totals': {
                'total_hours': Decimal('0'),
                'total_base_pay': Decimal('0'),
                'total_mileage_pay': Decimal('0'),
                'total_per_diem': Decimal('0'),
                'total_personal_expenses': Decimal('0'),
                'total_pay': Decimal('0')
            }
        }

        for job_id in job_ids:
            job = Job.query.get(job_id)
            if not job:
                continue

            # Calculate pay for this job
            pay_data = calculate_job_pay(job_id)
            if not pay_data:
                continue

            # Find this tech's pay in the job
            tech_pay = None
            for t in pay_data['technicians']:
                if t['tech_id'] == tid:
                    tech_pay = t
                    break

            if not tech_pay:
                continue

            # Get entry dates for this tech on this job
            tech_entries = [e for e in tech_pay['entries']]
            entry_dates = sorted(set(
                e['date_worked'] for e in tech_entries if e.get('date_worked')
            ))

            # Format date display: single date or range
            if len(entry_dates) == 0:
                date_display = None
            elif len(entry_dates) == 1:
                date_display = entry_dates[0]
            else:
                date_display = f"{entry_dates[0]} - {entry_dates[-1]}"

            # Add job to tech's report
            job_entry = {
                'job_id': job_id,
                'ticket_number': job.ticket_number,
                'description': job.description,
                'entry_dates': entry_dates,
                'date_display': date_display,
                'external_url': job.external_url,
                'billing_amount': float(job.billing_amount or 0),
                'hours': tech_pay['hours'],
                'effective_rate': tech_pay['effective_rate'],
                'using_minimum': tech_pay['using_minimum'],
                'base_pay': tech_pay['base_pay'],
                'mileage': tech_pay['mileage'],
                'mileage_pay': tech_pay['mileage_pay'],
                'per_diem': tech_pay['per_diem'],
                'personal_expenses': tech_pay['personal_expenses'],
                'total_pay': tech_pay['total_pay']
            }
            tech_data['jobs'].append(job_entry)

            # Update tech totals
            tech_data['totals']['total_hours'] += Decimal(str(tech_pay['hours']))
            tech_data['totals']['total_base_pay'] += Decimal(str(tech_pay['base_pay']))
            tech_data['totals']['total_mileage_pay'] += Decimal(str(tech_pay['mileage_pay']))
            tech_data['totals']['total_per_diem'] += Decimal(str(tech_pay['per_diem']))
            tech_data['totals']['total_personal_expenses'] += Decimal(str(tech_pay['personal_expenses']))
            tech_data['totals']['total_pay'] += Decimal(str(tech_pay['total_pay']))

        # Convert tech totals to float
        tech_data['totals'] = {k: float(v) for k, v in tech_data['totals'].items()}

        # Sort jobs by first entry date
        tech_data['jobs'].sort(key=lambda j: j['entry_dates'][0] if j['entry_dates'] else '')

        # Update grand totals
        for key in grand_totals:
            grand_totals[key] += Decimal(str(tech_data['totals'][key]))

        technicians_report.append(tech_data)

    # Sort technicians by name
    technicians_report.sort(key=lambda t: t['tech_name'])

    # Log report generation
    audit_logger.log(
        action_type='report_generated',
        entity_type='payroll_detail_report',
        description=f"Detailed payroll report generated for {from_date} to {to_date}",
        user_id=g.user_id
    )

    return jsonify({
        'report_type': 'payroll_detail',
        'from_date': from_date,
        'to_date': to_date,
        'generated_at': datetime.utcnow().isoformat(),
        'technicians': technicians_report,
        'grand_totals': {k: float(v) for k, v in grand_totals.items()},
        'technician_count': len(technicians_report)
    }), 200


@reports_bp.route('/technician-hours', methods=['GET'])
@jwt_required_with_user
def technician_hours_report():
    """
    Get hours breakdown for a technician.
    Technicians can view their own; managers can view all.

    Query parameters:
        - tech_id: Technician ID (required for managers)
        - from_date, to_date: Date range (required)
        - group_by: 'day', 'week', or 'job' (default: day)
    """
    user = g.current_user
    tech_id = request.args.get('tech_id', type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    group_by = request.args.get('group_by', 'day')

    # Determine technician to report on
    if user.role == 'technician':
        tech_id = user.tech_id
        if not tech_id:
            return jsonify({'error': 'User not linked to technician'}), 400
    elif not tech_id:
        return jsonify({'error': 'Technician ID required'}), 400

    # Check access
    if not can_access_technician_data(user, tech_id):
        return jsonify({'error': 'Access denied'}), 403

    if not from_date or not to_date:
        return jsonify({'error': 'Date range required'}), 400

    technician = Technician.query.get_or_404(tech_id)

    # Base query
    base_query = TimeEntry.query.filter(
        TimeEntry.tech_id == tech_id,
        TimeEntry.date_worked >= from_date,
        TimeEntry.date_worked <= to_date
    )

    if group_by == 'job':
        # Group by job
        results = db.session.query(
            Job.job_id,
            Job.ticket_number,
            Job.description,
            Platform.name.label('platform'),
            func.count(TimeEntry.entry_id).label('entry_count'),
            func.sum(TimeEntry.hours_worked).label('total_hours')
        ).join(
            TimeEntry, TimeEntry.job_id == Job.job_id
        ).join(
            Platform, Job.platform_id == Platform.platform_id
        ).filter(
            TimeEntry.tech_id == tech_id,
            TimeEntry.date_worked >= from_date,
            TimeEntry.date_worked <= to_date
        ).group_by(
            Job.job_id, Job.ticket_number, Job.description, Platform.name
        ).all()

        data = [{
            'job_id': r.job_id,
            'ticket_number': r.ticket_number,
            'description': r.description,
            'platform': r.platform,
            'entry_count': r.entry_count,
            'hours': float(r.total_hours or 0)
        } for r in results]

    elif group_by == 'week':
        # Group by week
        entries = base_query.order_by(TimeEntry.date_worked).all()
        weeks = {}

        for entry in entries:
            # Get week start (Monday)
            week_start = entry.date_worked - timedelta(days=entry.date_worked.weekday())
            week_key = week_start.isoformat()

            if week_key not in weeks:
                weeks[week_key] = {
                    'week_start': week_key,
                    'entries': 0,
                    'hours': 0
                }

            weeks[week_key]['entries'] += 1
            weeks[week_key]['hours'] += float(entry.hours_worked or 0)

        data = list(weeks.values())

    else:  # group_by == 'day'
        results = db.session.query(
            TimeEntry.date_worked,
            func.count(TimeEntry.entry_id).label('entry_count'),
            func.sum(TimeEntry.hours_worked).label('total_hours')
        ).filter(
            TimeEntry.tech_id == tech_id,
            TimeEntry.date_worked >= from_date,
            TimeEntry.date_worked <= to_date
        ).group_by(TimeEntry.date_worked).order_by(TimeEntry.date_worked).all()

        data = [{
            'date': r.date_worked.isoformat(),
            'entry_count': r.entry_count,
            'hours': float(r.total_hours or 0)
        } for r in results]

    total_hours = sum(d.get('hours', 0) for d in data)

    return jsonify({
        'report_type': 'technician_hours',
        'technician': technician.to_dict(),
        'from_date': from_date,
        'to_date': to_date,
        'group_by': group_by,
        'data': data,
        'total_hours': total_hours
    }), 200


@reports_bp.route('/job-billing', methods=['GET'])
@manager_required
def job_billing_report():
    """
    Generate job billing summary report.

    Query parameters:
        - from_date, to_date: Date range
        - platform_id: Filter by platform
        - status: Filter by job status
    """
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    platform_id = request.args.get('platform_id', type=int)
    status = request.args.get('status')

    query = db.session.query(
        Job.job_id,
        Job.ticket_number,
        Job.description,
        Job.client_name,
        Job.billing_type,
        Job.billing_amount,
        Job.job_status,
        Platform.name.label('platform'),
        func.count(TimeEntry.entry_id).label('entry_count'),
        func.sum(TimeEntry.hours_worked).label('actual_hours')
    ).join(
        Platform, Job.platform_id == Platform.platform_id
    ).outerjoin(
        TimeEntry, and_(
            TimeEntry.job_id == Job.job_id,
            TimeEntry.status.in_(['verified', 'billed', 'paid'])
        )
    )

    if from_date:
        query = query.filter(Job.job_date >= from_date)

    if to_date:
        query = query.filter(Job.job_date <= to_date)

    if platform_id:
        query = query.filter(Job.platform_id == platform_id)

    if status:
        query = query.filter(Job.job_status == status)

    query = query.group_by(
        Job.job_id, Job.ticket_number, Job.description, Job.client_name,
        Job.billing_type, Job.billing_amount, Job.job_status, Platform.name
    ).order_by(Job.job_date.desc())

    results = query.all()

    data = []
    total_billing = Decimal('0')
    total_hours = Decimal('0')

    for r in results:
        billing = Decimal(str(r.billing_amount or 0))
        hours = Decimal(str(r.actual_hours or 0))

        data.append({
            'job_id': r.job_id,
            'ticket_number': r.ticket_number,
            'description': r.description,
            'client_name': r.client_name,
            'platform': r.platform,
            'billing_type': r.billing_type,
            'billing_amount': float(billing),
            'actual_hours': float(hours),
            'entry_count': r.entry_count,
            'job_status': r.job_status
        })

        total_billing += billing
        total_hours += hours

    audit_logger.log(
        action_type='report_generated',
        entity_type='job_billing_report',
        description=f"Job billing report generated",
        user_id=g.user_id
    )

    return jsonify({
        'report_type': 'job_billing',
        'from_date': from_date,
        'to_date': to_date,
        'generated_at': datetime.utcnow().isoformat(),
        'data': data,
        'summary': {
            'job_count': len(data),
            'total_billing': float(total_billing),
            'total_hours': float(total_hours)
        }
    }), 200


@reports_bp.route('/platform-summary', methods=['GET'])
@manager_required
def platform_summary_report():
    """
    Generate platform-level summary report.

    Query parameters:
        - from_date, to_date: Date range
    """
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = db.session.query(
        Platform.platform_id,
        Platform.name,
        func.count(func.distinct(Job.job_id)).label('job_count'),
        func.sum(Job.billing_amount).label('total_billing'),
        func.sum(TimeEntry.hours_worked).label('total_hours')
    ).outerjoin(
        Job, Job.platform_id == Platform.platform_id
    ).outerjoin(
        TimeEntry, and_(
            TimeEntry.job_id == Job.job_id,
            TimeEntry.status.in_(['verified', 'billed', 'paid'])
        )
    )

    if from_date:
        query = query.filter(Job.job_date >= from_date)

    if to_date:
        query = query.filter(Job.job_date <= to_date)

    query = query.group_by(Platform.platform_id, Platform.name)

    results = query.all()

    data = [{
        'platform_id': r.platform_id,
        'name': r.name,
        'job_count': r.job_count or 0,
        'total_billing': float(r.total_billing or 0),
        'total_hours': float(r.total_hours or 0)
    } for r in results]

    return jsonify({
        'report_type': 'platform_summary',
        'from_date': from_date,
        'to_date': to_date,
        'generated_at': datetime.utcnow().isoformat(),
        'data': data
    }), 200


@reports_bp.route('/audit-log', methods=['GET'])
@admin_required
def audit_log_report():
    """
    Query audit logs (admin only).

    Query parameters:
        - page, per_page: Pagination
        - user_id: Filter by user
        - action_type: Filter by action type
        - entity_type: Filter by entity type
        - from_date, to_date: Date range
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    user_id = request.args.get('user_id', type=int)
    action_type = request.args.get('action_type')
    entity_type = request.args.get('entity_type')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = AuditLog.query

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if action_type:
        query = query.filter(AuditLog.action_type == action_type)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)

    if to_date:
        to_dt = datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(AuditLog.created_at < to_dt)

    query = query.order_by(AuditLog.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'audit_logs': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@reports_bp.route('/dashboard', methods=['GET'])
@jwt_required_with_user
def dashboard_stats():
    """
    Get dashboard statistics based on user role.
    Technicians see their own stats; managers see team-wide stats.
    """
    user = g.current_user
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    stats = {}

    if user.role in ('admin', 'manager'):
        # Team-wide stats
        stats['pending_verification'] = TimeEntry.query.filter_by(
            status='submitted'
        ).count()

        stats['active_jobs'] = Job.query.filter(
            Job.job_status.in_(['pending', 'assigned', 'in_progress'])
        ).count()

        stats['completed_this_week'] = Job.query.filter(
            Job.completed_date >= week_start,
            Job.job_status == 'completed'
        ).count()

        # Hours this month by status
        month_entries = TimeEntry.query.filter(
            TimeEntry.date_worked >= month_start
        ).all()

        stats['month_hours'] = {
            'total': sum(float(e.hours_worked or 0) for e in month_entries),
            'verified': sum(
                float(e.hours_worked or 0) for e in month_entries
                if e.status in ('verified', 'billed', 'paid')
            ),
            'pending': sum(
                float(e.hours_worked or 0) for e in month_entries
                if e.status in ('draft', 'submitted')
            )
        }

        # Active technicians
        stats['active_technicians'] = Technician.query.filter_by(
            status='active'
        ).count()

    else:
        # Technician's own stats
        if not user.tech_id:
            return jsonify({'error': 'User not linked to technician'}), 400

        tech_entries = TimeEntry.query.filter(
            TimeEntry.tech_id == user.tech_id,
            TimeEntry.date_worked >= month_start
        ).all()

        stats['my_hours_this_month'] = sum(
            float(e.hours_worked or 0) for e in tech_entries
        )

        stats['my_draft_entries'] = len([
            e for e in tech_entries if e.status == 'draft'
        ])

        stats['my_pending_entries'] = len([
            e for e in tech_entries if e.status == 'submitted'
        ])

        # Week breakdown
        week_entries = [e for e in tech_entries if e.date_worked >= week_start]
        stats['my_hours_this_week'] = sum(
            float(e.hours_worked or 0) for e in week_entries
        )

    return jsonify({
        'dashboard': stats,
        'as_of': datetime.utcnow().isoformat(),
        'user_role': user.role
    }), 200


@reports_bp.route('/pay-periods', methods=['GET'])
@jwt_required_with_user
def list_pay_periods():
    """List pay periods with summary information."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    status = request.args.get('status')

    query = PayPeriod.query

    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(PayPeriod.end_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    periods = []
    for period in pagination.items:
        period_data = period.to_dict()

        # Add entry count and hours
        entries = TimeEntry.query.filter_by(period_id=period.period_id).all()
        period_data['entry_count'] = len(entries)
        period_data['total_hours'] = sum(
            float(e.hours_worked or 0) for e in entries
        )
        period_data['verified_hours'] = sum(
            float(e.hours_worked or 0) for e in entries
            if e.status in ('verified', 'billed', 'paid')
        )

        periods.append(period_data)

    return jsonify({
        'pay_periods': periods,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@reports_bp.route('/pay-periods', methods=['POST'])
@manager_required
def create_pay_period():
    """
    Create a new pay period.

    Request body:
        {
            "start_date": "2026-01-01",
            "end_date": "2026-01-14",
            "period_name": "Jan 1-14, 2026"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not start_date or not end_date:
        return jsonify({'error': 'Start and end dates required'}), 400

    # Check for overlap
    existing = PayPeriod.query.filter(
        and_(
            PayPeriod.start_date <= end_date,
            PayPeriod.end_date >= start_date
        )
    ).first()

    if existing:
        return jsonify({'error': 'Pay period overlaps with existing period'}), 409

    period = PayPeriod(
        start_date=start_date,
        end_date=end_date,
        period_name=data.get('period_name', f"{start_date} to {end_date}")
    )

    db.session.add(period)
    db.session.commit()

    # Assign unassigned entries to this period
    unassigned = TimeEntry.query.filter(
        TimeEntry.period_id.is_(None),
        TimeEntry.date_worked >= start_date,
        TimeEntry.date_worked <= end_date
    ).all()

    for entry in unassigned:
        entry.period_id = period.period_id

    db.session.commit()

    audit_logger.log(
        action_type='pay_period_created',
        entity_type='pay_period',
        entity_id=period.period_id,
        new_values=period.to_dict(),
        description=f"Pay period {period.period_name} created",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Pay period created successfully',
        'pay_period': period.to_dict(),
        'entries_assigned': len(unassigned)
    }), 201


@reports_bp.route('/pay-periods/<int:period_id>/close', methods=['POST'])
@manager_required
def close_pay_period(period_id):
    """Close a pay period (no more edits allowed)."""
    period = PayPeriod.query.get_or_404(period_id)

    if period.status != 'open':
        return jsonify({'error': 'Period is not open'}), 400

    # Check for unverified entries
    unverified = TimeEntry.query.filter(
        TimeEntry.period_id == period_id,
        TimeEntry.status.in_(['draft', 'submitted'])
    ).count()

    if unverified > 0:
        return jsonify({
            'error': 'Cannot close period with unverified entries',
            'unverified_count': unverified
        }), 400

    # Calculate total hours
    total = db.session.query(
        func.sum(TimeEntry.hours_worked)
    ).filter(TimeEntry.period_id == period_id).scalar()

    period.status = 'closed'
    period.closed_at = datetime.utcnow()
    period.total_hours = total

    db.session.commit()

    audit_logger.log(
        action_type='pay_period_closed',
        entity_type='pay_period',
        entity_id=period.period_id,
        new_values={'status': 'closed', 'total_hours': float(total or 0)},
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Pay period closed',
        'pay_period': period.to_dict()
    }), 200
