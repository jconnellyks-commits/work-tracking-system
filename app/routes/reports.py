"""
Reporting routes for generating various work tracking reports.
Includes payroll, job billing, technician hours, and audit reports.
"""
from datetime import datetime, timedelta, date
from app.utils.timezone import get_local_today
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
from app.utils.pay_calculator import calculate_job_pay, calculate_period_pay

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
    Delegates to calculate_period_pay for the shared-pool weighted formula.
    """
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    tech_id_param = request.args.get('tech_id', '')

    if not from_date or not to_date:
        return jsonify({'error': 'Date range required'}), 400

    tech_ids = None
    if tech_id_param:
        tech_ids = [int(t) for t in tech_id_param.split(',') if t.strip().isdigit()]

    pay_data = calculate_period_pay(
        start_date=from_date, end_date=to_date, tech_ids=tech_ids
    )

    if not pay_data:
        return jsonify({'error': 'Could not calculate pay data'}), 400

    # Map output to the report format expected by the frontend
    technicians_report = []
    grand_totals = {
        'total_hours': Decimal('0'),
        'total_base_pay': Decimal('0'),
        'total_mileage_pay': Decimal('0'),
        'total_per_diem': Decimal('0'),
        'total_personal_expenses': Decimal('0'),
        'total_pay': Decimal('0'),
    }

    for tech in pay_data['technicians']:
        # Sort jobs by first entry date
        tech['jobs'].sort(key=lambda j: j['entry_dates'][0] if j['entry_dates'] else '')

        # Add aliases the frontend expects
        for job in tech['jobs']:
            job['billing_amount'] = job['job'].get('billing_amount', 0)
            job['job_profit'] = job['profit_share']
            job['tech_profit_share'] = job['profit_share']

        tech_entry = {
            'tech_id': tech['tech_id'],
            'tech_name': tech['tech_name'],
            'min_pay': tech['min_pay'],
            'jobs': tech['jobs'],
            'totals': {
                'total_hours': tech['total_hours'],
                'total_base_pay': tech['total_base_pay'],
                'total_mileage_pay': tech['total_mileage_pay'],
                'total_per_diem': tech['total_per_diem'],
                'total_personal_expenses': tech['total_personal_expenses'],
                'total_pay': tech['total_pay'],
                'total_profit_share': tech.get('total_profit_share', 0),
            }
        }
        technicians_report.append(tech_entry)

        for key in grand_totals:
            grand_totals[key] += Decimal(str(tech_entry['totals'][key]))

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


@reports_bp.route('/income-expense', methods=['GET'])
@manager_required
def income_expense_report():
    """
    Generate income/expense report showing profitability.

    Query parameters:
        - from_date: Start date (required)
        - to_date: End date (required)

    Returns breakdown of income, expenses, and net profit.
    Jobs with future dates are marked as projected and excluded from net profit.
    """
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    if not from_date or not to_date:
        return jsonify({'error': 'Date range required'}), 400

    # Get today's date for projected detection (uses configured timezone)
    today = get_local_today()

    # Get jobs in date range with verified time entries
    jobs_query = Job.query.filter(
        Job.job_date >= from_date,
        Job.job_date <= to_date
    ).all()

    jobs_data = []
    totals = {
        'billing': Decimal('0'),
        'job_expenses': Decimal('0'),
        'commissions': Decimal('0'),
        'tech_pay': Decimal('0'),
        'total_expenses': Decimal('0'),
        'net_profit': Decimal('0')
    }
    projected_totals = {
        'billing': Decimal('0'),
        'job_count': 0
    }

    for job in jobs_query:
        # Check if job is in the future (projected)
        is_projected = job.job_date and job.job_date > today

        # Calculate tech pay for this job
        pay_data = calculate_job_pay(job.job_id)
        tech_pay = Decimal('0')
        if pay_data and pay_data.get('totals'):
            tech_pay = Decimal(str(pay_data['totals'].get('total_pay', 0)))

        billing = Decimal(str(job.billing_amount or 0))
        job_expenses = Decimal(str(job.expenses or 0))
        commissions = Decimal(str(job.commissions or 0))
        total_expenses = job_expenses + commissions + tech_pay
        net_profit = billing - total_expenses

        # Get hours per date for multi-day job chart distribution
        entry_hours_by_date = {}
        for entry in job.time_entries:
            if entry.date_worked and entry.hours_worked:
                d = entry.date_worked.isoformat()
                entry_hours_by_date[d] = entry_hours_by_date.get(d, 0) + float(entry.hours_worked)

        job_entry = {
            'job_id': job.job_id,
            'ticket_number': job.ticket_number,
            'description': job.description,
            'job_date': job.job_date.isoformat() if job.job_date else None,
            'platform': job.platform.name if job.platform else None,
            'billing': float(billing),
            'job_expenses': float(job_expenses),
            'commissions': float(commissions),
            'tech_pay': float(tech_pay),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
            'is_projected': is_projected,
            'entry_hours_by_date': entry_hours_by_date
        }
        jobs_data.append(job_entry)

        # Update totals - only include non-projected jobs in actual totals
        if is_projected:
            projected_totals['billing'] += billing
            projected_totals['job_count'] += 1
        else:
            totals['billing'] += billing
            totals['job_expenses'] += job_expenses
            totals['commissions'] += commissions
            totals['tech_pay'] += tech_pay
            totals['total_expenses'] += total_expenses
            totals['net_profit'] += net_profit

    # Sort by date
    jobs_data.sort(key=lambda j: j['job_date'] or '')

    audit_logger.log(
        action_type='report_generated',
        entity_type='income_expense_report',
        description=f"Income/expense report generated for {from_date} to {to_date}",
        user_id=g.user_id
    )

    actual_job_count = len(jobs_data) - projected_totals['job_count']

    profit_margin = float((totals['net_profit'] / totals['billing'] * 100) if totals['billing'] > 0 else 0)
    projected_profit = float(projected_totals['billing'] * Decimal(str(profit_margin)) / 100) if profit_margin else 0

    return jsonify({
        'report_type': 'income_expense',
        'from_date': from_date,
        'to_date': to_date,
        'generated_at': datetime.utcnow().isoformat(),
        'jobs': jobs_data,
        'totals': {k: float(v) for k, v in totals.items()},
        'projected': {
            'billing': float(projected_totals['billing']),
            'job_count': projected_totals['job_count'],
            'profit': round(projected_profit, 2)
        },
        'job_count': actual_job_count,
        'total_job_count': len(jobs_data),
        'profit_margin': profit_margin
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

    # Build job filter
    job_filters = []
    if from_date:
        job_filters.append(Job.job_date >= from_date)
    if to_date:
        job_filters.append(Job.job_date <= to_date)

    # Query jobs grouped by platform (for job count and billing)
    jobs_query = db.session.query(
        Job.platform_id,
        func.count(Job.job_id).label('job_count'),
        func.sum(Job.billing_amount).label('total_billing')
    )
    if job_filters:
        jobs_query = jobs_query.filter(*job_filters)
    jobs_query = jobs_query.group_by(Job.platform_id)
    jobs_subquery = jobs_query.subquery()

    # Query time entries grouped by platform (for hours)
    hours_query = db.session.query(
        Job.platform_id,
        func.sum(TimeEntry.hours_worked).label('total_hours')
    ).join(
        TimeEntry, TimeEntry.job_id == Job.job_id
    ).filter(
        TimeEntry.status.in_(['verified', 'billed', 'paid'])
    )
    if job_filters:
        hours_query = hours_query.filter(*job_filters)
    hours_query = hours_query.group_by(Job.platform_id)
    hours_subquery = hours_query.subquery()

    # Combine with platforms
    query = db.session.query(
        Platform.platform_id,
        Platform.name,
        func.coalesce(jobs_subquery.c.job_count, 0).label('job_count'),
        func.coalesce(jobs_subquery.c.total_billing, 0).label('total_billing'),
        func.coalesce(hours_subquery.c.total_hours, 0).label('total_hours')
    ).outerjoin(
        jobs_subquery, jobs_subquery.c.platform_id == Platform.platform_id
    ).outerjoin(
        hours_subquery, hours_subquery.c.platform_id == Platform.platform_id
    )

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
    today = get_local_today()
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

    if period.status not in ('open', 'locked'):
        return jsonify({'error': 'Period is not open or locked'}), 400

    import logging
    logging.getLogger(__name__).warning(
        f'Deprecated: close_pay_period called for period {period_id}. '
        'Use the payout workflow (lock → pay) instead.'
    )

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


@reports_bp.route('/pay-periods/generate', methods=['POST'])
@manager_required
def generate_pay_periods():
    """
    Generate multiple recurring pay periods.

    Request body:
        {
            "anchor_end_date": "2026-01-21",  # End date of a known period
            "period_length_days": 14,         # Length of each period
            "count_back": 6,                  # How many past periods to generate
            "count_forward": 2                # How many future periods to generate
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    anchor_end = datetime.strptime(data.get('anchor_end_date'), '%Y-%m-%d').date()
    period_length = data.get('period_length_days', 14)
    count_back = data.get('count_back', 6)
    count_forward = data.get('count_forward', 2)

    created = []
    skipped = []

    # Generate periods going backwards
    for i in range(count_back, 0, -1):
        end_date = anchor_end - timedelta(days=period_length * i)
        start_date = end_date - timedelta(days=period_length - 1)

        # Check for existing
        existing = PayPeriod.query.filter(
            and_(
                PayPeriod.start_date <= end_date,
                PayPeriod.end_date >= start_date
            )
        ).first()

        if existing:
            skipped.append(f"{start_date} to {end_date}")
            continue

        period_name = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
        period = PayPeriod(start_date=start_date, end_date=end_date, period_name=period_name)
        db.session.add(period)
        created.append(period_name)

    # Generate the anchor period
    start_date = anchor_end - timedelta(days=period_length - 1)
    existing = PayPeriod.query.filter(
        and_(
            PayPeriod.start_date <= anchor_end,
            PayPeriod.end_date >= start_date
        )
    ).first()

    if not existing:
        period_name = f"{start_date.strftime('%b %d')} - {anchor_end.strftime('%b %d, %Y')}"
        period = PayPeriod(start_date=start_date, end_date=anchor_end, period_name=period_name)
        db.session.add(period)
        created.append(period_name)
    else:
        skipped.append(f"{start_date} to {anchor_end}")

    # Generate periods going forward
    for i in range(1, count_forward + 1):
        start_date = anchor_end + timedelta(days=1) + timedelta(days=period_length * (i - 1))
        end_date = start_date + timedelta(days=period_length - 1)

        existing = PayPeriod.query.filter(
            and_(
                PayPeriod.start_date <= end_date,
                PayPeriod.end_date >= start_date
            )
        ).first()

        if existing:
            skipped.append(f"{start_date} to {end_date}")
            continue

        period_name = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
        period = PayPeriod(start_date=start_date, end_date=end_date, period_name=period_name)
        db.session.add(period)
        created.append(period_name)

    db.session.commit()

    # Assign time entries to their periods
    all_periods = PayPeriod.query.all()
    assigned_count = 0
    for period in all_periods:
        unassigned = TimeEntry.query.filter(
            TimeEntry.period_id.is_(None),
            TimeEntry.date_worked >= period.start_date,
            TimeEntry.date_worked <= period.end_date
        ).all()
        for entry in unassigned:
            entry.period_id = period.period_id
            assigned_count += 1

    db.session.commit()

    return jsonify({
        'message': f'Generated {len(created)} pay periods',
        'created': created,
        'skipped': skipped,
        'entries_assigned': assigned_count
    }), 201


@reports_bp.route('/pay-periods/<int:period_id>', methods=['DELETE'])
@manager_required
def delete_pay_period(period_id):
    """Delete a pay period."""
    period = PayPeriod.query.get_or_404(period_id)

    # Unassign entries from this period
    TimeEntry.query.filter(TimeEntry.period_id == period_id).update({'period_id': None})

    db.session.delete(period)
    db.session.commit()

    return jsonify({'message': 'Pay period deleted'}), 200
