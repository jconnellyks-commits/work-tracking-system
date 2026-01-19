"""
Import routes for external data sources like Field Nation.
"""

from flask import Blueprint, request, jsonify, g
from app.models import db, Job, TimeEntry, Technician, Platform
from app.utils.auth import jwt_required_with_user, admin_required
from datetime import datetime
import re

imports_bp = Blueprint('imports', __name__)


@imports_bp.route('/fieldnation', methods=['POST'])
@jwt_required_with_user
@admin_required
def import_fieldnation():
    """
    Import work orders and time entries from Field Nation scraper.

    Expected JSON format:
    [
        {
            "work_order_id": "18164666",
            "url": "https://app.fieldnation.com/workorders/18164666",
            "title": "Field Service Repairs- F3396AO - Outage",
            "company": "Pro-Vigil",
            "status": "Work Done",
            "total_hours": 3.02,
            "total_pay": 136.96,
            "scheduled_date": "11/13/2025",
            "time_entries": [
                {
                    "hours": 3.02,
                    "date": "11/13/2025",
                    "time_in": "1:35 PM",
                    "time_out": "4:36 PM",
                    "mileage": 0.02
                }
            ]
        }
    ]
    """
    user = g.current_user
    data = request.get_json()

    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of work orders'}), 400

    results = {
        'imported_jobs': 0,
        'imported_entries': 0,
        'skipped_jobs': 0,
        'skipped_entries': 0,
        'errors': []
    }

    for wo in data:
        try:
            wo_id = wo.get('work_order_id', '')
            url = wo.get('url', '')
            title = wo.get('title', '')
            company = wo.get('company', '')

            # Check if job already exists by external URL or ticket number
            existing_job = None
            if url:
                existing_job = Job.query.filter_by(external_url=url).first()
            if not existing_job and wo_id:
                # Try matching by ticket number containing the work order ID
                existing_job = Job.query.filter(Job.ticket_number.like(f'%{wo_id}%')).first()

            if existing_job:
                job = existing_job
                results['skipped_jobs'] += 1
            else:
                # Create new job
                # Parse scheduled date
                scheduled_date = None
                if wo.get('scheduled_date'):
                    try:
                        # Try different date formats
                        for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y']:
                            try:
                                scheduled_date = datetime.strptime(
                                    wo['scheduled_date'].split()[0],  # Handle "THU Nov 13" format
                                    fmt
                                ).date()
                                break
                            except:
                                continue
                    except:
                        pass

                # Get or create Field Nation platform
                platform = Platform.query.filter_by(name='Field Nation').first()
                if not platform:
                    platform = Platform(name='Field Nation', code='FN')
                    db.session.add(platform)
                    db.session.flush()

                job = Job(
                    ticket_number=f"FN-{wo_id}",
                    description=title[:500] if title else f"Field Nation #{wo_id}",
                    client_name=company[:200] if company else 'Field Nation',
                    scheduled_date=scheduled_date,
                    job_status='completed',
                    billing_amount=wo.get('total_pay', 0),
                    external_url=url,
                    platform_id=platform.platform_id,
                    platform_job_code=wo_id,
                    created_by=user.user_id,
                    updated_by=user.user_id
                )
                db.session.add(job)
                db.session.flush()  # Get the job_id
                results['imported_jobs'] += 1

            # Import time entries
            time_entries = wo.get('time_entries', [])
            for te in time_entries:
                try:
                    # Parse date
                    entry_date = None
                    if te.get('date'):
                        for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y']:
                            try:
                                entry_date = datetime.strptime(te['date'], fmt).date()
                                break
                            except:
                                continue

                    if not entry_date:
                        entry_date = job.scheduled_date or datetime.now().date()

                    # Parse times
                    time_in = None
                    time_out = None

                    if te.get('time_in'):
                        time_in = parse_time(te['time_in'])
                    if te.get('time_out'):
                        time_out = parse_time(te['time_out'])

                    # Check if similar entry already exists
                    existing_entry = TimeEntry.query.filter_by(
                        job_id=job.job_id,
                        date_worked=entry_date,
                        hours_worked=te.get('hours', 0)
                    ).first()

                    if existing_entry:
                        results['skipped_entries'] += 1
                        continue

                    entry = TimeEntry(
                        job_id=job.job_id,
                        tech_id=None,  # Unassigned - needs manual assignment
                        date_worked=entry_date,
                        time_in=time_in,
                        time_out=time_out,
                        hours_worked=te.get('hours', 0),
                        mileage=te.get('mileage', 0),
                        status='draft',
                        notes=f"Imported from Field Nation WO#{wo_id}",
                        created_by=user.user_id,
                        updated_by=user.user_id
                    )
                    db.session.add(entry)
                    results['imported_entries'] += 1

                except Exception as e:
                    results['errors'].append(f"Time entry error for WO#{wo_id}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"Work order {wo_id} error: {str(e)}")

    db.session.commit()

    return jsonify({
        'message': 'Import completed',
        'results': results
    })


def parse_time(time_str):
    """Parse time string to time object."""
    if not time_str:
        return None

    time_str = time_str.strip().upper()

    # Try different formats
    formats = [
        '%I:%M %p',      # 1:35 PM
        '%I:%M%p',       # 1:35PM
        '%H:%M',         # 13:35
        '%I:%M:%S %p',   # 1:35:00 PM
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except:
            continue

    return None


@imports_bp.route('/fieldnation/preview', methods=['POST'])
@jwt_required_with_user
@admin_required
def preview_fieldnation_import():
    """
    Preview what would be imported without actually importing.
    """
    data = request.get_json()

    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of work orders'}), 400

    preview = {
        'new_jobs': [],
        'existing_jobs': [],
        'total_entries': 0
    }

    for wo in data:
        wo_id = wo.get('work_order_id', '')
        url = wo.get('url', '')

        # Check if job exists
        existing_job = None
        if url:
            existing_job = Job.query.filter_by(external_url=url).first()
        if not existing_job and wo_id:
            existing_job = Job.query.filter(Job.ticket_number.like(f'%{wo_id}%')).first()

        entry_count = len(wo.get('time_entries', []))
        preview['total_entries'] += entry_count

        if existing_job:
            preview['existing_jobs'].append({
                'work_order_id': wo_id,
                'title': wo.get('title', ''),
                'existing_job_id': existing_job.job_id,
                'time_entries': entry_count
            })
        else:
            preview['new_jobs'].append({
                'work_order_id': wo_id,
                'title': wo.get('title', ''),
                'company': wo.get('company', ''),
                'time_entries': entry_count
            })

    return jsonify(preview)
