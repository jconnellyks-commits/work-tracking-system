"""
Import routes for external data sources like Field Nation.
"""

from flask import Blueprint, request, jsonify, g
from app.models import db, Job, TimeEntry, Technician, Platform, JobSchedule
from app.utils.auth import jwt_required_with_user, admin_required
from datetime import datetime
import re
import hashlib

imports_bp = Blueprint('imports', __name__)


# Scraper platform name -> (platform.name in the DB, codes it might carry).
#
# Resolving by code alone was a silent failure: the scrapers say 'workmarket'
# and this mapped that to the code 'WM', but the WorkMarket row's code is
# 'workmarket' (only Field Nation uses a short code, 'FN'). The lookup
# returned None, and check-existing then answered "nothing is completed, go
# scrape all of it" on every single run. Match on the name first, which is
# what the import endpoints themselves use to find or create the platform.
PLATFORM_ALIASES = {
    'fieldnation': ('Field Nation', ('FN', 'fieldnation', 'field_nation')),
    'field_nation': ('Field Nation', ('FN', 'fieldnation', 'field_nation')),
    'fn': ('Field Nation', ('FN', 'fieldnation', 'field_nation')),
    'workmarket': ('WorkMarket', ('workmarket', 'WM', 'work_market')),
    'work_market': ('WorkMarket', ('workmarket', 'WM', 'work_market')),
    'wm': ('WorkMarket', ('workmarket', 'WM', 'work_market')),
}


def resolve_platform(platform_name):
    """Look up a Platform from a scraper platform name.

    Returns (platform, known). `known` is False only when the name itself is
    not one we support, which callers answer with 400; a known name whose row
    does not exist yet yields (None, True).
    """
    entry = PLATFORM_ALIASES.get((platform_name or '').lower().strip())
    if not entry:
        return None, False

    display_name, codes = entry
    platform = Platform.query.filter_by(name=display_name).first()
    if platform:
        return platform, True

    for code in codes:
        platform = Platform.query.filter_by(code=code).first()
        if platform:
            return platform, True

    return None, True


def normalize_time_str(t):
    """Normalize a time string for consistent hashing.
    Converts various formats to 'HH:MM AM/PM' (e.g., '01:35 PM').
    Uses regex instead of strptime to avoid Windows Python bug where
    strptime('%I:%M %p') mishandles PM (parses 6:21 PM as 6:21 AM).
    """
    if not t:
        return ''
    t = t.strip().upper()
    t = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', t)
    t = re.sub(r'\s+(?!AM$|PM$)[A-Z]{2,4}\s*$', '', t)

    # Match 12-hour format: "6:21PM", "6:21 PM", "06:21 PM", "1:35:00 PM"
    m = re.match(r'^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)$', t)
    if m:
        hour, minute, ampm = int(m.group(1)), m.group(2), m.group(3)
        if hour == 12:
            hour = 0 if ampm == 'AM' else 12
        elif ampm == 'PM':
            hour += 12
        return f"{hour % 12 or 12:02d}:{minute} {ampm}"

    # Match 24-hour format: "14:30", "08:15"
    m = re.match(r'^(\d{1,2}):(\d{2})$', t)
    if m:
        hour, minute = int(m.group(1)), m.group(2)
        ampm = 'AM' if hour < 12 else 'PM'
        display_hour = hour % 12 or 12
        return f"{display_hour:02d}:{minute} {ampm}"

    return t


def generate_source_hash(platform, external_id, date, time_in=None, time_out=None, hours=None):
    """
    Generate a unique hash for a scraped time entry.
    Used for duplicate detection regardless of how entries are split between technicians.

    Time strings are normalized before hashing to prevent scraper formatting
    differences from creating different hashes for the same entry.

    Format: {platform}:{external_id}:{date}:{time_in}:{time_out}
    If no times, uses hours: {platform}:{external_id}:{date}:hours:{hours}
    """
    norm_in = normalize_time_str(time_in)
    norm_out = normalize_time_str(time_out)

    if norm_in and norm_out:
        source = f"{platform}:{external_id}:{date}:{norm_in}:{norm_out}"
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
        'start time set': 'assigned',

        # Work in progress
        'in progress': 'in_progress',
        'on my way': 'in_progress',
        'checked in': 'in_progress',
        'checked out': 'in_progress',
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
                existing_job = Job.query.filter(Job.ticket_number == f"FN-{wo_id}").first()
                if not existing_job:
                    existing_job = Job.query.filter(Job.ticket_number == wo_id).first()

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

            # Parse scheduled_start_time if provided
            scheduled_start_time = None
            if wo.get('scheduled_start_time'):
                try:
                    scheduled_start_time = datetime.strptime(
                        str(wo['scheduled_start_time']).strip(), '%H:%M'
                    ).time()
                except (ValueError, AttributeError):
                    pass

            # Parse scheduled_latest_start_time if provided
            scheduled_latest_start_time = None
            if wo.get('scheduled_latest_start_time'):
                try:
                    scheduled_latest_start_time = datetime.strptime(
                        str(wo['scheduled_latest_start_time']).strip(), '%H:%M'
                    ).time()
                except (ValueError, AttributeError):
                    pass

            if existing_job:
                job = existing_job
                # Update existing job with latest status, billing, and date.
                # Only overwrite status when the scrape actually reported one:
                # an empty status maps to 'pending' (see map_fieldnation_status)
                # and would silently downgrade a job already in progress or
                # completed. Blank scrapes happen when the browser window is
                # unrendered and page text comes back empty.
                if wo.get('status'):
                    job.job_status = mapped_status
                if mapped_status == 'cancelled':
                    job.billing_amount = 0
                elif wo.get('total_pay'):
                    job.billing_amount = wo.get('total_pay')
                if scheduled_date:
                    job.job_date = scheduled_date
                if scheduled_start_time:
                    job.scheduled_start_time = scheduled_start_time
                if wo.get('title') and len(wo.get('title', '')) > len(job.description or ''):
                    job.description = wo['title'][:500]
                # Only set when the scrape reported one. Field Nation hides the
                # site address once a work order is submitted for approval, so a
                # later completed-pass scrape sends nothing - this must not blank
                # out an address captured while the job was assigned.
                if wo.get('location'):
                    job.location = wo['location'][:255]
                # Same placeholder repair as WorkMarket below - client_name was
                # only ever written at creation, so a job first scraped without
                # a company kept the literal 'Field Nation' permanently.
                incoming_company = (wo.get('company') or '').strip()
                if incoming_company and incoming_company != 'Field Nation':
                    if not job.client_name or job.client_name == 'Field Nation':
                        job.client_name = incoming_company[:200]
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
                    scheduled_start_time=scheduled_start_time,
                    job_status=mapped_status,
                    billing_amount=0 if mapped_status == 'cancelled' else wo.get('total_pay', 0),
                    external_url=url,
                    location=(wo.get('location') or None) and wo['location'][:255],
                    platform_id=platform.platform_id,
                    platform_job_code=wo_id,
                    completed_date=datetime.utcnow().date() if mapped_status == 'completed' else None,
                )
                db.session.add(job)
                db.session.flush()  # Get the job_id
                results['imported_jobs'] += 1

            # Create/update JobSchedule entry with arrival window times
            if scheduled_date and (scheduled_start_time or scheduled_latest_start_time):
                existing_sched = JobSchedule.query.filter_by(
                    job_id=job.job_id, scheduled_date=scheduled_date
                ).first()
                if existing_sched:
                    if scheduled_start_time:
                        existing_sched.start_time = scheduled_start_time
                    if scheduled_latest_start_time:
                        existing_sched.latest_start_time = scheduled_latest_start_time
                else:
                    sched_entry = JobSchedule(
                        job_id=job.job_id,
                        scheduled_date=scheduled_date,
                        start_time=scheduled_start_time,
                        latest_start_time=scheduled_latest_start_time
                    )
                    db.session.add(sched_entry)

            # Skip time entries for cancelled jobs
            if mapped_status == 'cancelled':
                continue

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

                    # Skip zero-duration entries (e.g., identical check-in/check-out)
                    if hours <= 0 and time_in and time_out and time_in == time_out:
                        continue

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

                    # Fallback: check by job + date + hours (catches entries with old/missing hashes)
                    existing_by_fields = TimeEntry.query.filter_by(
                        job_id=job.job_id,
                        date_worked=entry_date,
                        hours_worked=hours
                    ).first()
                    if existing_by_fields:
                        if not existing_by_fields.source_hash:
                            existing_by_fields.source_hash = source_hash
                        results['skipped_entries'] += 1
                        continue

                    # Fallback: check by job + date + parsed times (catches rounding differences)
                    if time_in and time_out:
                        existing_by_times = TimeEntry.query.filter_by(
                            job_id=job.job_id,
                            date_worked=entry_date,
                            time_in=time_in,
                            time_out=time_out
                        ).first()
                        if existing_by_times:
                            if not existing_by_times.source_hash:
                                existing_by_times.source_hash = source_hash
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
            existing_job = Job.query.filter(Job.ticket_number == f"FN-{wo_id}").first()
            if not existing_job:
                existing_job = Job.query.filter(Job.ticket_number == wo_id).first()

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
        # 'void' is what the embedded workEncoded JSON reports for a cancelled
        # assignment - the rendered page says "cancelled or voided" instead, so
        # which one a scrape sees depends on whether it took the text path or
        # the JSON fallback. Without this it fell through to the 'pending'
        # default and would have downgraded a cancelled job.
        'void': 'cancelled',
        'voided': 'cancelled',
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

            # Parse scheduled_start_time if provided
            scheduled_start_time = None
            if assignment.get('scheduled_start_time'):
                try:
                    scheduled_start_time = datetime.strptime(
                        str(assignment['scheduled_start_time']).strip(), '%H:%M'
                    ).time()
                except (ValueError, AttributeError):
                    pass

            # Parse scheduled_latest_start_time if provided
            scheduled_latest_start_time = None
            if assignment.get('scheduled_latest_start_time'):
                try:
                    scheduled_latest_start_time = datetime.strptime(
                        str(assignment['scheduled_latest_start_time']).strip(), '%H:%M'
                    ).time()
                except (ValueError, AttributeError):
                    pass

            if existing_job:
                job = existing_job
                # Update existing job with latest status, billing, and date.
                # Only overwrite status when the scrape actually reported one:
                # an empty status maps to 'pending' (see map_workmarket_status)
                # and would silently downgrade a job already in progress or
                # completed. Blank scrapes happen when the browser window is
                # unrendered and page text comes back empty.
                if assignment.get('status'):
                    job.job_status = mapped_status
                if mapped_status == 'cancelled':
                    # Cancelling zeroes the billing. That is right for a job
                    # nobody worked, but if hours were already logged it
                    # rewrites revenue for work that actually happened and
                    # feeds the income/expense report. Surface it rather than
                    # silently changing the number.
                    logged = TimeEntry.query.filter_by(job_id=job.job_id).count()
                    if logged and job.billing_amount:
                        results['errors'].append(
                            f"{job.ticket_number}: cancelled on WorkMarket but has "
                            f"{logged} time entr{'y' if logged == 1 else 'ies'} - "
                            f"billing of ${float(job.billing_amount):.2f} was zeroed, "
                            f"please review"
                        )
                    job.billing_amount = 0
                elif assignment.get('total_pay'):
                    job.billing_amount = assignment.get('total_pay')
                if scheduled_date:
                    job.job_date = scheduled_date
                if scheduled_start_time:
                    job.scheduled_start_time = scheduled_start_time
                if assignment.get('title') and len(assignment.get('title', '')) > len(job.description or ''):
                    job.description = assignment['title'][:500]
                if assignment.get('location'):
                    job.location = assignment['location'][:255]
                # Repair a placeholder client. client_name used to be written
                # only at creation, so a job first scraped without a company
                # (a list-page pass, or a scrape that came back blank) kept the
                # literal 'WorkMarket' forever even though later scrapes carry
                # the real buyer. Only overwrite the placeholder or an empty
                # value - never a name that has already been established.
                incoming_company = (assignment.get('company') or '').strip()
                if incoming_company and incoming_company != 'WorkMarket':
                    if not job.client_name or job.client_name == 'WorkMarket':
                        job.client_name = incoming_company[:200]
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
                    scheduled_start_time=scheduled_start_time,
                    job_status=mapped_status,
                    billing_amount=0 if mapped_status == 'cancelled' else assignment.get('total_pay', 0),
                    external_url=url,
                    location=(assignment.get('location') or None) and assignment['location'][:255],
                    platform_id=platform.platform_id,
                    platform_job_code=a_id,
                    completed_date=datetime.utcnow().date() if mapped_status == 'completed' else None,
                )
                db.session.add(job)
                db.session.flush()  # Get the job_id
                results['imported_jobs'] += 1

            # A pending reschedule means the date above is the time the tech
            # has ASKED for, which WorkMarket has not approved yet. Taking it
            # is the right call (the old behaviour kept the stale original and
            # put WM-1228008224 three days out), but the calendar should not
            # present a provisional date as settled.
            if assignment.get('schedule_pending'):
                when = str(job.job_date)
                if job.scheduled_start_time:
                    when += f" {job.scheduled_start_time.strftime('%I:%M %p')}"
                results['errors'].append(
                    f"{job.ticket_number}: reschedule request pending on WorkMarket - "
                    f"{when} is the requested time, not yet approved"
                )

            # Create/update JobSchedule entry with arrival window times
            if scheduled_date and (scheduled_start_time or scheduled_latest_start_time):
                existing_sched = JobSchedule.query.filter_by(
                    job_id=job.job_id, scheduled_date=scheduled_date
                ).first()
                if existing_sched:
                    if scheduled_start_time:
                        existing_sched.start_time = scheduled_start_time
                    if scheduled_latest_start_time:
                        existing_sched.latest_start_time = scheduled_latest_start_time
                else:
                    sched_entry = JobSchedule(
                        job_id=job.job_id,
                        scheduled_date=scheduled_date,
                        start_time=scheduled_start_time,
                        latest_start_time=scheduled_latest_start_time
                    )
                    db.session.add(sched_entry)

            # Skip time entries for cancelled jobs
            if mapped_status == 'cancelled':
                continue

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

                    # Skip zero-duration entries (e.g., identical check-in/check-out)
                    if hours <= 0 and time_in and time_out and time_in == time_out:
                        continue

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

                    # Fallback: check by job + date + hours (catches entries with old/missing hashes)
                    existing_by_fields = TimeEntry.query.filter_by(
                        job_id=job.job_id,
                        date_worked=entry_date,
                        hours_worked=hours
                    ).first()
                    if existing_by_fields:
                        if not existing_by_fields.source_hash:
                            existing_by_fields.source_hash = source_hash
                        results['skipped_entries'] += 1
                        continue

                    # Fallback: check by job + date + parsed times (catches rounding differences)
                    if time_in and time_out:
                        existing_by_times = TimeEntry.query.filter_by(
                            job_id=job.job_id,
                            date_worked=entry_date,
                            time_in=time_in,
                            time_out=time_out
                        ).first()
                        if existing_by_times:
                            if not existing_by_times.source_hash:
                                existing_by_times.source_hash = source_hash
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


# =============================================================================
# TST (Tech Service Today) Import Endpoints
# =============================================================================

@imports_bp.route('/tst', methods=['POST'])
@jwt_required_with_user
@admin_required
def import_tst():
    """
    Import jobs from Tech Service Today email parser.

    Expected JSON format:
    [
        {
            "ticket_number": "502861",
            "client_name": "Altoona Quarry (Altoona, KS)",
            "job_date": "2026-02-27",
            "scheduled_start_time": "09:30",
            "description": "Onsite Support for Site Migration",
            "billing_rate": 75.00,
            "trip_charge": 130.00,
            "status": "assigned"
        }
    ]
    """
    user = g.current_user
    data = request.get_json()

    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of jobs'}), 400

    results = {
        'imported_jobs': 0,
        'updated_jobs': 0,
        'errors': []
    }

    platform = Platform.query.filter_by(name='Tech Service Today').first()
    if not platform:
        platform = Platform(name='Tech Service Today', code='TST')
        db.session.add(platform)
        db.session.flush()

    for job_data in data:
        try:
            ticket_number = job_data.get('ticket_number', '').strip()
            if not ticket_number:
                results['errors'].append('Missing ticket_number')
                continue

            full_ticket = f"TST-{ticket_number}"

            # Duplicate check — exact match on full ticket to avoid cross-platform collisions
            existing_job = Job.query.filter(
                Job.ticket_number == full_ticket
            ).first()

            billing_rate = float(job_data.get('billing_rate') or 0)
            trip_charge = float(job_data.get('trip_charge') or 0)

            # Build description: append rate info if available
            description = job_data.get('description', '').strip()
            if billing_rate or trip_charge:
                rate_parts = []
                if billing_rate:
                    rate_parts.append(f"Rate: ${billing_rate:.2f}/hr")
                if trip_charge:
                    rate_parts.append(f"Trip: ${trip_charge:.2f}")
                description = f"{description} [{', '.join(rate_parts)}]" if description else f"[{', '.join(rate_parts)}]"

            # Parse job_date
            job_date = None
            if job_data.get('job_date'):
                try:
                    job_date = datetime.strptime(job_data['job_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Parse scheduled_start_time
            scheduled_start_time = None
            if job_data.get('scheduled_start_time'):
                try:
                    scheduled_start_time = datetime.strptime(
                        str(job_data['scheduled_start_time']).strip(), '%H:%M'
                    ).time()
                except (ValueError, AttributeError):
                    pass

            # Billing floor: trip charge + 1hr at rate
            billing_amount = trip_charge + billing_rate if (billing_rate or trip_charge) else 0

            mapped_status = job_data.get('status', 'assigned')

            if existing_job:
                # Update status and rate info if changed
                existing_job.job_status = mapped_status
                if billing_amount and billing_amount > float(existing_job.billing_amount or 0):
                    existing_job.billing_amount = billing_amount
                # Append rate to description if not already present
                if billing_rate and f"Rate: ${billing_rate:.2f}" not in (existing_job.description or ''):
                    rate_parts = []
                    if billing_rate:
                        rate_parts.append(f"Rate: ${billing_rate:.2f}/hr")
                    if trip_charge:
                        rate_parts.append(f"Trip: ${trip_charge:.2f}")
                    existing_job.description = f"{existing_job.description or ''} [{', '.join(rate_parts)}]".strip()
                if job_date and not existing_job.job_date:
                    existing_job.job_date = job_date
                if scheduled_start_time and not existing_job.scheduled_start_time:
                    existing_job.scheduled_start_time = scheduled_start_time
                results['updated_jobs'] += 1
            else:
                job = Job(
                    ticket_number=full_ticket,
                    description=description[:500] if description else f"TST #{ticket_number}",
                    client_name=(job_data.get('client_name', '') or 'Tech Service Today')[:200],
                    job_date=job_date,
                    scheduled_start_time=scheduled_start_time,
                    job_status=mapped_status,
                    billing_amount=billing_amount,
                    billing_type='hourly',
                    platform_id=platform.platform_id,
                    platform_job_code=ticket_number,
                )
                db.session.add(job)
                results['imported_jobs'] += 1

        except Exception as e:
            results['errors'].append(f"TST job error: {str(e)}")

    db.session.commit()

    return jsonify({
        'message': 'TST import completed',
        'results': results
    })


# =============================================================================
# TechLink Import Endpoints
# =============================================================================

@imports_bp.route('/techlink', methods=['POST'])
@jwt_required_with_user
@admin_required
def import_techlink():
    """
    Import jobs from TechLink email parser.

    Expected JSON format:
    [
        {
            "ticket_number": "398586",
            "client_name": "Wichita Dwight D. Eisenhower Natl Airport",
            "job_date": "2026-02-20",
            "scheduled_start_time": "09:30",
            "description": "Filter Change",
            "address": "1980 S. Airport Road, Wichita, KS 67209",
            "contact": "Robert Halbleib, 3167558870",
            "status": "assigned"
        }
    ]
    """
    user = g.current_user
    data = request.get_json()

    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of jobs'}), 400

    results = {
        'imported_jobs': 0,
        'updated_jobs': 0,
        'errors': []
    }

    platform = Platform.query.filter_by(name='TechLink').first()
    if not platform:
        platform = Platform(name='TechLink', code='TL')
        db.session.add(platform)
        db.session.flush()

    for job_data in data:
        try:
            ticket_number = job_data.get('ticket_number', '').strip()
            if not ticket_number:
                results['errors'].append('Missing ticket_number')
                continue

            full_ticket = f"TL-{ticket_number}"

            # Duplicate check — exact match on full ticket to avoid cross-platform collisions
            existing_job = Job.query.filter(
                Job.ticket_number == full_ticket
            ).first()

            # Build description: collapse available fields
            parts = [p for p in [
                job_data.get('description', '').strip(),
                job_data.get('address', '').strip(),
                job_data.get('contact', '').strip(),
            ] if p]
            description = ' | '.join(parts)

            # Parse job_date
            job_date = None
            if job_data.get('job_date'):
                try:
                    job_date = datetime.strptime(job_data['job_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Parse scheduled_start_time
            scheduled_start_time = None
            if job_data.get('scheduled_start_time'):
                try:
                    scheduled_start_time = datetime.strptime(
                        str(job_data['scheduled_start_time']).strip(), '%H:%M'
                    ).time()
                except (ValueError, AttributeError):
                    pass

            external_url = job_data.get('external_url', '').strip() or None
            mapped_status = job_data.get('status')

            if existing_job:
                if mapped_status:
                    existing_job.job_status = mapped_status
                if job_date:
                    existing_job.job_date = job_date
                if scheduled_start_time:
                    existing_job.scheduled_start_time = scheduled_start_time
                if external_url and not existing_job.external_url:
                    existing_job.external_url = external_url
                if job_data.get('address'):
                    existing_job.location = job_data['address'].strip()[:255]
                if description and not existing_job.description.startswith(description.split(' | ')[0][:20] if description else ''):
                    pass  # Don't overwrite richer description from Assigned email
                results['updated_jobs'] += 1
            else:
                job = Job(
                    ticket_number=full_ticket,
                    description=description[:500] if description else f"TechLink #{ticket_number}",
                    client_name=(job_data.get('client_name', '') or 'TechLink')[:200],
                    job_date=job_date,
                    scheduled_start_time=scheduled_start_time,
                    external_url=external_url,
                    location=(job_data.get('address') or '').strip()[:255] or None,
                    job_status=mapped_status or 'assigned',
                    billing_amount=0,
                    billing_type='hourly',
                    platform_id=platform.platform_id,
                    platform_job_code=ticket_number,
                )
                db.session.add(job)
                results['imported_jobs'] += 1

        except Exception as e:
            results['errors'].append(f"TechLink job error: {str(e)}")

    db.session.commit()

    return jsonify({
        'message': 'TechLink import completed',
        'results': results
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

    platform, known = resolve_platform(platform_name)
    if not known:
        return jsonify({'error': f'Unknown platform: {platform_name}'}), 400
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


# Statuses that mean a job still needs watching. Anything else is finished and
# does not need re-scraping.
OPEN_JOB_STATUSES = ('pending', 'assigned', 'in_progress')


@imports_bp.route('/open-jobs', methods=['GET'])
@jwt_required_with_user
@admin_required
def list_open_jobs():
    """Platform job codes for jobs still open in our database.

    The batch scraper walks the platform's status tabs, so a job only gets
    updated while it is listed in a tab the scraper visits. If a detail scrape
    is dropped - an exception, or an invitation false positive - nothing
    notices, and the job keeps whatever status, date and hours it had. That is
    how WM-1228008224 stayed 'assigned' on the wrong date with no time entry
    after it had been worked, approved and paid.

    The scraper reconciles against this list and re-scrapes by ID anything
    that did not arrive, regardless of which tab the job now lives in.

    Query params:
        platform  'fieldnation' or 'workmarket' (required)

    Response:
        {"platform": "workmarket", "statuses": [...], "job_codes": [...]}
    """
    platform_name = (request.args.get('platform') or '').lower()
    if not platform_name:
        return jsonify({'error': 'platform is required'}), 400

    platform, known = resolve_platform(platform_name)
    if not known:
        return jsonify({'error': f'Unknown platform: {platform_name}'}), 400
    if not platform:
        return jsonify({
            'platform': platform_name,
            'statuses': list(OPEN_JOB_STATUSES),
            'job_codes': [],
        })

    jobs = Job.query.filter(
        Job.platform_id == platform.platform_id,
        Job.job_status.in_(OPEN_JOB_STATUSES),
        Job.platform_job_code.isnot(None),
    ).all()

    return jsonify({
        'platform': platform_name,
        'statuses': list(OPEN_JOB_STATUSES),
        'job_codes': [j.platform_job_code for j in jobs if j.platform_job_code],
    })
