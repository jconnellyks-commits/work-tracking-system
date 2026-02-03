"""
Import routes for external data sources like Field Nation.
"""

from flask import Blueprint, request, jsonify, g
from app.models import db, Job, TimeEntry, Technician, Platform
from app.utils.auth import jwt_required_with_user, admin_required
from datetime import datetime
import re
import hashlib

imports_bp = Blueprint('imports', __name__)


def generate_source_hash(platform, external_id, date, time_in=None, time_out=None, hours=None):
    """
    Generate a unique hash for a scraped time entry.
    Used for duplicate detection regardless of how entries are split between technicians.

    Format: {platform}:{external_id}:{date}:{time_in}:{time_out}
    If no times, uses hours: {platform}:{external_id}:{date}:hours:{hours}
    """
    if time_in and time_out:
        source = f"{platform}:{external_id}:{date}:{time_in}:{time_out}"
    elif hours:
        source = f"{platform}:{external_id}:{date}:hours:{hours}"
    else:
        source = f"{platform}:{external_id}:{date}"

    return hashlib.sha256(source.encode()).hexdigest()[:32]


def map_fieldnation_status(fn_status):
    """Map Field Nation status to internal job status."""
    if not fn_status:
        return 'pending'

    fn_status = fn_status.lower().strip()

    # Field Nation statuses mapped to internal statuses
    status_map = {
        # Pending/not started
        'published': 'pending',
        'routed': 'pending',
        'requested': 'pending',

        # Assigned but not started
        'assigned': 'assigned',
        'confirmed': 'assigned',
        'scheduled': 'assigned',

        # Work in progress
        'in progress': 'in_progress',
        'on my way': 'in_progress',
        'checked in': 'in_progress',
        'work done': 'in_progress',

        # Completed
        'approved': 'completed',
        'paid': 'completed',
        'completed': 'completed',

        # Cancelled
        'cancelled': 'cancelled',
        'canceled': 'cancelled',
    }

    return status_map.get(fn_status, 'pending')


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
        'updated_jobs': 0,
        'imported_entries': 0,
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

            # Map Field Nation status to internal status
            mapped_status = map_fieldnation_status(wo.get('status', ''))

            # Parse scheduled date (used for both new and existing jobs)
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
                        except ValueError:
                            continue
                except Exception:
                    pass

            if existing_job:
                job = existing_job
                # Update existing job with latest status, billing, and date
                job.job_status = mapped_status
                if wo.get('total_pay'):
                    job.billing_amount = wo.get('total_pay')
                if scheduled_date:
                    job.job_date = scheduled_date
                if wo.get('title') and len(wo.get('title', '')) > len(job.description or ''):
                    job.description = wo['title'][:500]
                # Set completed_date if status changed to completed
                if mapped_status == 'completed' and not job.completed_date:
                    job.completed_date = datetime.utcnow().date()
                results['updated_jobs'] += 1
            else:
                # Create new job
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
                    job_date=scheduled_date,
                    job_status=mapped_status,
                    billing_amount=wo.get('total_pay', 0),
                    external_url=url,
                    platform_id=platform.platform_id,
                    platform_job_code=wo_id,
                    completed_date=datetime.utcnow().date() if mapped_status == 'completed' else None,
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

                    hours = te.get('hours', 0) or 0

                    # Generate source hash for duplicate detection
                    source_hash = generate_source_hash(
                        'FN',
                        wo_id,
                        entry_date.isoformat() if entry_date else '',
                        te.get('time_in', ''),
                        te.get('time_out', ''),
                        hours
                    )

                    # Check if this exact scraped entry already exists (by hash)
                    existing_by_hash = TimeEntry.query.filter_by(source_hash=source_hash).first()
                    if existing_by_hash:
                        results['skipped_entries'] += 1
                        continue

                    entry = TimeEntry(
                        job_id=job.job_id,
                        tech_id=None,  # Unassigned - needs manual assignment
                        date_worked=entry_date,
                        time_in=time_in,
                        time_out=time_out,
                        hours_worked=hours,
                        mileage=te.get('mileage', 0),
                        status='draft',
                        notes=f"Imported from Field Nation WO#{wo_id}",
                        source_hash=source_hash,
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


# =============================================================================
# WorkMarket Import Endpoints
# =============================================================================

def map_workmarket_status(wm_status):
    """Map WorkMarket status to internal job status."""
    if not wm_status:
        return 'pending'

    wm_status = wm_status.lower().strip()

    # WorkMarket statuses mapped to internal statuses
    # Based on actual WorkMarket UI: Paid, Invoiced, Pending Approval, Active, Available, Applied
    status_map = {
        # Pending/not started - seeking work
        'available': 'pending',
        'applied': 'pending',

        # Assigned but not started
        'active': 'assigned',
        'assigned': 'assigned',
        'confirmed': 'assigned',

        # Work in progress
        'in progress': 'in_progress',
        'on site': 'in_progress',

        # Awaiting payment
        'completed': 'completed',
        'paymentpending': 'completed',  # Pending Approval in WM
        'pending approval': 'completed',
        'invoiced': 'completed',  # Complete tab in WM (awaiting payment)
        'complete': 'completed',
        'approved': 'completed',

        # Paid
        'paid': 'completed',

        # Late (still completed, just flagged)
        'late': 'completed',

        # Cancelled
        'cancelled': 'cancelled',
        'canceled': 'cancelled',
        'declined': 'cancelled',
        'rejected': 'cancelled',
    }

    return status_map.get(wm_status, 'pending')


@imports_bp.route('/workmarket', methods=['POST'])
@jwt_required_with_user
@admin_required
def import_workmarket():
    """
    Import assignments and time entries from WorkMarket scraper.

    Expected JSON format:
    [
        {
            "assignment_id": "123456",
            "url": "https://www.workmarket.com/assignments/123456",
            "title": "Assignment Title",
            "company": "Client Name",
            "status": "Completed",
            "total_hours": 3.5,
            "total_pay": 150.00,
            "scheduled_date": "01/15/2026",
            "time_entries": [
                {
                    "hours": 3.5,
                    "date": "01/15/2026",
                    "time_in": "9:00 AM",
                    "time_out": "12:30 PM",
                    "mileage": 0
                }
            ]
        }
    ]
    """
    user = g.current_user
    data = request.get_json()

    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of assignments'}), 400

    results = {
        'imported_jobs': 0,
        'updated_jobs': 0,
        'imported_entries': 0,
        'skipped_entries': 0,
        'errors': []
    }

    for assignment in data:
        try:
            a_id = assignment.get('assignment_id', '')
            url = assignment.get('url', '')
            title = assignment.get('title', '')
            company = assignment.get('company', '')

            # Check if job already exists by external URL or ticket number
            existing_job = None
            if url:
                existing_job = Job.query.filter_by(external_url=url).first()
            if not existing_job and a_id:
                # Try matching by ticket number containing the assignment ID
                existing_job = Job.query.filter(Job.ticket_number.like(f'%WM-{a_id}%')).first()

            # Map WorkMarket status to internal status
            mapped_status = map_workmarket_status(assignment.get('status', ''))

            # Parse scheduled date (used for both new and existing jobs)
            scheduled_date = None
            if assignment.get('scheduled_date'):
                try:
                    for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y']:
                        try:
                            scheduled_date = datetime.strptime(
                                assignment['scheduled_date'].split()[0],
                                fmt
                            ).date()
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            if existing_job:
                job = existing_job
                # Update existing job with latest status, billing, and date
                job.job_status = mapped_status
                if assignment.get('total_pay'):
                    job.billing_amount = assignment.get('total_pay')
                if scheduled_date:
                    job.job_date = scheduled_date
                if assignment.get('title') and len(assignment.get('title', '')) > len(job.description or ''):
                    job.description = assignment['title'][:500]
                # Set completed_date if status changed to completed
                if mapped_status == 'completed' and not job.completed_date:
                    job.completed_date = datetime.utcnow().date()
                results['updated_jobs'] += 1
            else:
                # Create new job
                # Get or create WorkMarket platform
                platform = Platform.query.filter_by(name='WorkMarket').first()
                if not platform:
                    platform = Platform(name='WorkMarket', code='WM')
                    db.session.add(platform)
                    db.session.flush()

                job = Job(
                    ticket_number=f"WM-{a_id}",
                    description=title[:500] if title else f"WorkMarket #{a_id}",
                    client_name=company[:200] if company else 'WorkMarket',
                    job_date=scheduled_date,
                    job_status=mapped_status,
                    billing_amount=assignment.get('total_pay', 0),
                    external_url=url,
                    platform_id=platform.platform_id,
                    platform_job_code=a_id,
                    completed_date=datetime.utcnow().date() if mapped_status == 'completed' else None,
                )
                db.session.add(job)
                db.session.flush()  # Get the job_id
                results['imported_jobs'] += 1

            # Import time entries
            time_entries = assignment.get('time_entries', [])
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
                        entry_date = job.job_date or datetime.now().date()

                    # Parse times
                    time_in = None
                    time_out = None

                    if te.get('time_in'):
                        time_in = parse_time(te['time_in'])
                    if te.get('time_out'):
                        time_out = parse_time(te['time_out'])

                    hours = te.get('hours', 0) or 0

                    # Generate source hash for duplicate detection
                    source_hash = generate_source_hash(
                        'WM',
                        a_id,
                        entry_date.isoformat() if entry_date else '',
                        te.get('time_in', ''),
                        te.get('time_out', ''),
                        hours
                    )

                    # Check if this exact scraped entry already exists (by hash)
                    existing_by_hash = TimeEntry.query.filter_by(source_hash=source_hash).first()
                    if existing_by_hash:
                        results['skipped_entries'] += 1
                        continue

                    entry = TimeEntry(
                        job_id=job.job_id,
                        tech_id=None,  # Unassigned - needs manual assignment
                        date_worked=entry_date,
                        time_in=time_in,
                        time_out=time_out,
                        hours_worked=hours,
                        mileage=te.get('mileage', 0),
                        status='draft',
                        notes=f"Imported from WorkMarket #{a_id}",
                        source_hash=source_hash,
                        created_by=user.user_id,
                        updated_by=user.user_id
                    )
                    db.session.add(entry)
                    results['imported_entries'] += 1

                except Exception as e:
                    results['errors'].append(f"Time entry error for WM#{a_id}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"Assignment {a_id} error: {str(e)}")

    db.session.commit()

    return jsonify({
        'message': 'Import completed',
        'results': results
    })


@imports_bp.route('/workmarket/preview', methods=['POST'])
@jwt_required_with_user
@admin_required
def preview_workmarket_import():
    """
    Preview what would be imported without actually importing.
    """
    data = request.get_json()

    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of assignments'}), 400

    preview = {
        'new_jobs': [],
        'existing_jobs': [],
        'total_entries': 0
    }

    for assignment in data:
        a_id = assignment.get('assignment_id', '')
        url = assignment.get('url', '')

        # Check if job exists
        existing_job = None
        if url:
            existing_job = Job.query.filter_by(external_url=url).first()
        if not existing_job and a_id:
            existing_job = Job.query.filter(Job.ticket_number.like(f'%WM-{a_id}%')).first()

        entry_count = len(assignment.get('time_entries', []))
        preview['total_entries'] += entry_count

        if existing_job:
            preview['existing_jobs'].append({
                'assignment_id': a_id,
                'title': assignment.get('title', ''),
                'existing_job_id': existing_job.job_id,
                'time_entries': entry_count
            })
        else:
            preview['new_jobs'].append({
                'assignment_id': a_id,
                'title': assignment.get('title', ''),
                'company': assignment.get('company', ''),
                'time_entries': entry_count
            })

    return jsonify(preview)


@imports_bp.route('/backfill-hashes', methods=['POST'])
@jwt_required_with_user
@admin_required
def backfill_source_hashes():
    """
    Generate source_hash for existing time entries that were imported but don't have a hash.
    This is a one-time migration helper.
    """
    # Find all entries without a source_hash that have import-related notes
    entries = TimeEntry.query.filter(
        TimeEntry.source_hash.is_(None),
        db.or_(
            TimeEntry.notes.like('%Imported from Field Nation%'),
            TimeEntry.notes.like('%Imported from WorkMarket%')
        )
    ).all()

    updated = 0
    for entry in entries:
        # Extract platform and external ID from notes
        platform = None
        external_id = None

        if entry.notes:
            fn_match = re.search(r'Field Nation WO#(\d+)', entry.notes)
            wm_match = re.search(r'WorkMarket #(\d+)', entry.notes)

            if fn_match:
                platform = 'FN'
                external_id = fn_match.group(1)
            elif wm_match:
                platform = 'WM'
                external_id = wm_match.group(1)

        if platform and external_id:
            # Generate hash based on available data
            source_hash = generate_source_hash(
                platform,
                external_id,
                entry.date_worked.isoformat() if entry.date_worked else '',
                entry.time_in.strftime('%I:%M %p') if entry.time_in else '',
                entry.time_out.strftime('%I:%M %p') if entry.time_out else '',
                float(entry.hours_worked) if entry.hours_worked else 0
            )
            entry.source_hash = source_hash
            updated += 1

    db.session.commit()

    return jsonify({
        'message': f'Backfilled {updated} entries with source hashes',
        'updated': updated,
        'total_checked': len(entries)
    })


@imports_bp.route('/check-existing', methods=['POST'])
@jwt_required_with_user
def check_existing_jobs():
    """
    Check which job IDs already exist as completed jobs.
    Used by batch scraper to avoid re-scraping completed work orders.

    Request JSON:
    {
        "platform": "fieldnation" or "workmarket",
        "ids": ["12345", "67890", ...]
    }

    Response:
    {
        "already_completed": ["12345"],  # Skip these - already done
        "to_scrape": ["67890", ...]      # Scrape these - new or status changed
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    platform_name = data.get('platform', '').lower()
    ids = data.get('ids', [])

    if not platform_name:
        return jsonify({'error': 'Platform is required'}), 400

    if not ids:
        return jsonify({'already_completed': [], 'to_scrape': []})

    # Map platform name to code
    platform_map = {
        'fieldnation': 'FN',
        'field_nation': 'FN',
        'fn': 'FN',
        'workmarket': 'WM',
        'work_market': 'WM',
        'wm': 'WM',
    }

    platform_code = platform_map.get(platform_name)
    if not platform_code:
        return jsonify({'error': f'Unknown platform: {platform_name}'}), 400

    # Get platform
    platform = Platform.query.filter_by(code=platform_code).first()
    if not platform:
        # No jobs for this platform yet - all are new
        return jsonify({'already_completed': [], 'to_scrape': ids})

    # Query jobs for this platform with these IDs
    existing_jobs = Job.query.filter(
        Job.platform_id == platform.platform_id,
        Job.platform_job_code.in_(ids)
    ).all()

    # Separate into completed vs needs-update
    already_completed = []
    existing_not_completed = []

    for job in existing_jobs:
        if job.job_status == 'completed':
            already_completed.append(job.platform_job_code)
        else:
            existing_not_completed.append(job.platform_job_code)

    # IDs not in database at all
    existing_ids = set(j.platform_job_code for j in existing_jobs)
    new_ids = [id for id in ids if id not in existing_ids]

    # to_scrape = new + existing but not completed
    to_scrape = new_ids + existing_not_completed

    return jsonify({
        'already_completed': already_completed,
        'to_scrape': to_scrape,
        'summary': {
            'total_checked': len(ids),
            'already_completed': len(already_completed),
            'existing_needs_update': len(existing_not_completed),
            'new': len(new_ids)
        }
    })
