"""
Pay calculation service for technician compensation.

Technician Pay Formula:
1. Job Net = Billing Amount - Expenses - Commissions
2. Total Deductions = Mileage Pay + Per Diem + Personal Expenses (all techs)
3. Tech Pool = (Job Net - Total Deductions) / 2

Single Tech:
  - Calculated Rate = Tech Pool / Total Hours
  - If Calculated Rate < Min Pay: use Min Pay
  - Base Pay = Hours × Rate

Multiple Techs:
  - Weight = (Tech Min Pay × Tech Hours) / Σ(All Min Pay × Hours)
  - Base Pay = Tech Pool × Weight (subject to minimum)

Four Payouts per Tech per Job:
1. Base Pay (calculated above)
2. Mileage Reimbursement (mileage × per_mile_rate)
3. Per Diem
4. Personal Expenses
"""
from datetime import date as date_type
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func
from app.models import Job, JobBundle, TimeEntry, Technician, MileageRateHistory, TechPayRateHistory, PayPeriod, JobReimbursable


def calculate_job_pay(job_id):
    """
    Calculate pay breakdown for all technicians on a job.

    Returns:
        dict: {
            'job': {...},
            'job_net': float,
            'tech_pool': float,
            'total_deductions': float,
            'technicians': [
                {
                    'tech_id': int,
                    'tech_name': str,
                    'hours': float,
                    'min_pay': float,
                    'weight': float,
                    'base_pay': float,
                    'mileage': float,
                    'mileage_pay': float,
                    'per_diem': float,
                    'personal_expenses': float,
                    'total_pay': float,
                    'effective_rate': float,
                    'entries': [...]
                }
            ],
            'totals': {...}
        }
    """
    job = Job.query.get(job_id)
    if not job:
        return None

    # Get all time entries for this job
    entries = TimeEntry.query.filter_by(job_id=job_id).all()
    if not entries:
        return {
            'job': job.to_dict(),
            'job_net': 0,
            'tech_pool': 0,
            'total_deductions': 0,
            'total_reimbursables': 0,
            'reimbursables': [],
            'technicians': [],
            'totals': {
                'total_hours': 0,
                'total_base_pay': 0,
                'total_mileage_pay': 0,
                'total_per_diem': 0,
                'total_personal_expenses': 0,
                'total_reimbursables': 0,
                'total_pay': 0
            }
        }

    # Calculate job net
    billing_amount = Decimal(str(job.billing_amount or 0))
    expenses = Decimal(str(job.expenses or 0))
    commissions = Decimal(str(job.commissions or 0))
    job_net = billing_amount - expenses - commissions

    # Group entries by technician
    tech_data = {}
    for entry in entries:
        tech_id = entry.tech_id
        if tech_id not in tech_data:
            tech = Technician.query.get(tech_id)
            min_pay = Decimal(str(TechPayRateHistory.get_rate_for_date(tech_id, entry.date_worked))) if tech else Decimal('0')
            tech_data[tech_id] = {
                'tech_id': tech_id,
                'tech_name': tech.name if tech else f'Tech #{tech_id}',
                'min_pay': min_pay,
                'hours': Decimal('0'),
                'mileage': Decimal('0'),
                'per_diem': Decimal('0'),
                'personal_expenses': Decimal('0'),
                'entries': []
            }

        # Get mileage rate for the date worked
        mileage_rate = MileageRateHistory.get_rate_for_date(entry.date_worked)

        entry_data = entry.to_dict()
        entry_data['mileage_rate'] = mileage_rate
        entry_data['mileage_pay'] = float(Decimal(str(entry.mileage or 0)) * Decimal(str(mileage_rate)))

        tech_data[tech_id]['entries'].append(entry_data)
        tech_data[tech_id]['hours'] += Decimal(str(entry.hours_worked or 0))
        tech_data[tech_id]['mileage'] += Decimal(str(entry.mileage or 0))
        tech_data[tech_id]['per_diem'] += Decimal(str(entry.per_diem or 0))
        tech_data[tech_id]['personal_expenses'] += Decimal(str(entry.personal_expenses or 0))

    # Calculate total deductions (mileage pay + per diem + personal expenses for all techs)
    total_mileage_pay = Decimal('0')
    total_per_diem = Decimal('0')
    total_personal_expenses = Decimal('0')

    for tech_id, data in tech_data.items():
        # Calculate mileage pay for this tech
        mileage_pay = Decimal('0')
        for entry in data['entries']:
            mileage_pay += Decimal(str(entry['mileage_pay']))
        data['mileage_pay'] = mileage_pay
        total_mileage_pay += mileage_pay
        total_per_diem += data['per_diem']
        total_personal_expenses += data['personal_expenses']

    total_deductions = total_mileage_pay + total_per_diem + total_personal_expenses

    # Get reimbursables for this job
    reimbursables = JobReimbursable.query.filter_by(job_id=job_id).all()
    total_reimbursables = sum((Decimal(str(r.amount)) for r in reimbursables), Decimal('0'))

    # Tech pool is half of (job net - deductions)
    tech_pool = (job_net - total_deductions) / 2
    if tech_pool < 0:
        tech_pool = Decimal('0')

    # Calculate total hours and weighted sum
    total_hours = sum(data['hours'] for data in tech_data.values())
    weighted_sum = sum(data['min_pay'] * data['hours'] for data in tech_data.values())

    # Calculate base pay for each tech
    technicians = []
    total_base_pay = Decimal('0')

    for tech_id, data in tech_data.items():
        using_minimum = False
        if total_hours == 0:
            weight = Decimal('0')
            base_pay = Decimal('0')
            effective_rate = Decimal('0')
        elif len(tech_data) == 1:
            # Single tech case
            weight = Decimal('1')
            if data['hours'] > 0:
                calculated_rate = tech_pool / data['hours']
                # Use higher of calculated rate or minimum pay
                if calculated_rate < data['min_pay']:
                    using_minimum = True
                    effective_rate = data['min_pay']
                else:
                    effective_rate = calculated_rate
                base_pay = data['hours'] * effective_rate
            else:
                effective_rate = data['min_pay']
                base_pay = Decimal('0')
        else:
            # Multiple techs - weight by min_pay × hours
            if weighted_sum > 0:
                weight = (data['min_pay'] * data['hours']) / weighted_sum
            else:
                weight = Decimal('1') / len(tech_data)

            weighted_base = tech_pool * weight

            # Ensure minimum pay is met
            min_pay_amount = data['hours'] * data['min_pay']
            if weighted_base < min_pay_amount:
                using_minimum = True
                base_pay = min_pay_amount
            else:
                base_pay = weighted_base

            if data['hours'] > 0:
                effective_rate = base_pay / data['hours']
            else:
                effective_rate = data['min_pay']

        # Add reimbursable share (distributed by hours ratio)
        if total_hours > 0 and total_reimbursables > 0:
            reimbursable_share = total_reimbursables * (data['hours'] / total_hours)
        else:
            reimbursable_share = Decimal('0')

        total_pay = base_pay + data['mileage_pay'] + data['per_diem'] + data['personal_expenses'] + reimbursable_share
        total_base_pay += base_pay

        technicians.append({
            'tech_id': tech_id,
            'tech_name': data['tech_name'],
            'hours': float(data['hours'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'min_pay': float(data['min_pay'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'weight': float(weight.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)) if len(tech_data) > 1 else 1.0,
            'base_pay': float(base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'mileage': float(data['mileage'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'mileage_pay': float(data['mileage_pay'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'per_diem': float(data['per_diem'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'personal_expenses': float(data['personal_expenses'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'reimbursable_share': float(reimbursable_share.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float(total_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'effective_rate': float(effective_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'using_minimum': using_minimum,
            'entries': data['entries']
        })

    return {
        'job': job.to_dict(),
        'job_net': float(job_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'tech_pool': float(tech_pool.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_deductions': float(total_deductions.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'reimbursables': [r.to_dict() for r in reimbursables],
        'technicians': technicians,
        'totals': {
            'total_hours': float(total_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_base_pay': float(total_base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_mileage_pay': float(total_mileage_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_per_diem': float(total_per_diem.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_personal_expenses': float(total_personal_expenses.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float((total_base_pay + total_mileage_pay + total_per_diem + total_personal_expenses + total_reimbursables).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        }
    }


def calculate_bundle_pay(bundle_id):
    """
    Calculate pay breakdown for all technicians across a job bundle.

    Pools billing/expenses/commissions from all bundled jobs and gathers
    all time entries (on bundled jobs via job_id + entries directly on
    the bundle via bundle_id).  Applies the same pay formula as
    calculate_job_pay.

    Returns:
        dict: Same shape as calculate_job_pay plus 'bundle' and 'jobs' keys.
    """
    from app import db

    bundle = JobBundle.query.get(bundle_id)
    if not bundle:
        return None

    jobs = bundle.jobs.all()
    job_ids = [j.job_id for j in jobs]

    # Gather ALL entries: on bundled jobs OR directly on the bundle
    if job_ids:
        entries = TimeEntry.query.filter(
            db.or_(
                TimeEntry.job_id.in_(job_ids),
                TimeEntry.bundle_id == bundle_id
            )
        ).all()
    else:
        entries = TimeEntry.query.filter_by(bundle_id=bundle_id).all()

    # Pool financials from all jobs
    billing_amount = sum((Decimal(str(j.billing_amount or 0)) for j in jobs), Decimal('0'))
    expenses = sum((Decimal(str(j.expenses or 0)) for j in jobs), Decimal('0'))
    commissions = sum((Decimal(str(j.commissions or 0)) for j in jobs), Decimal('0'))
    job_net = billing_amount - expenses - commissions

    if not entries:
        return {
            'bundle': bundle.to_dict(),
            'jobs': [j.to_dict() for j in jobs],
            'job': {
                'job_id': f'bundle:{bundle_id}',
                'ticket_number': bundle.display_name,
                'description': bundle.display_name,
                'billing_amount': float(billing_amount),
                'expenses': float(expenses),
                'commissions': float(commissions),
            },
            'job_net': 0,
            'tech_pool': 0,
            'total_deductions': 0,
            'total_reimbursables': 0,
            'reimbursables': [],
            'technicians': [],
            'totals': {
                'total_hours': 0,
                'total_base_pay': 0,
                'total_mileage_pay': 0,
                'total_per_diem': 0,
                'total_personal_expenses': 0,
                'total_reimbursables': 0,
                'total_pay': 0
            }
        }

    # Group entries by technician
    tech_data = {}
    for entry in entries:
        tech_id_val = entry.tech_id
        if tech_id_val not in tech_data:
            tech = Technician.query.get(tech_id_val)
            min_pay = Decimal(str(TechPayRateHistory.get_rate_for_date(tech_id_val, entry.date_worked))) if tech else Decimal('0')
            tech_data[tech_id_val] = {
                'tech_id': tech_id_val,
                'tech_name': tech.name if tech else f'Tech #{tech_id_val}',
                'min_pay': min_pay,
                'hours': Decimal('0'),
                'mileage': Decimal('0'),
                'per_diem': Decimal('0'),
                'personal_expenses': Decimal('0'),
                'entries': []
            }

        mileage_rate = MileageRateHistory.get_rate_for_date(entry.date_worked)
        entry_data = entry.to_dict()
        entry_data['mileage_rate'] = mileage_rate
        entry_data['mileage_pay'] = float(Decimal(str(entry.mileage or 0)) * Decimal(str(mileage_rate)))

        tech_data[tech_id_val]['entries'].append(entry_data)
        tech_data[tech_id_val]['hours'] += Decimal(str(entry.hours_worked or 0))
        tech_data[tech_id_val]['mileage'] += Decimal(str(entry.mileage or 0))
        tech_data[tech_id_val]['per_diem'] += Decimal(str(entry.per_diem or 0))
        tech_data[tech_id_val]['personal_expenses'] += Decimal(str(entry.personal_expenses or 0))

    # Calculate total deductions
    total_mileage_pay = Decimal('0')
    total_per_diem = Decimal('0')
    total_personal_expenses = Decimal('0')

    for tid, data in tech_data.items():
        mileage_pay = Decimal('0')
        for entry in data['entries']:
            mileage_pay += Decimal(str(entry['mileage_pay']))
        data['mileage_pay'] = mileage_pay
        total_mileage_pay += mileage_pay
        total_per_diem += data['per_diem']
        total_personal_expenses += data['personal_expenses']

    total_deductions = total_mileage_pay + total_per_diem + total_personal_expenses

    # Gather reimbursables from all bundled jobs
    reimbursables = []
    total_reimbursables = Decimal('0')
    for j in jobs:
        job_reimb = JobReimbursable.query.filter_by(job_id=j.job_id).all()
        reimbursables.extend(job_reimb)
        total_reimbursables += sum((Decimal(str(r.amount)) for r in job_reimb), Decimal('0'))

    # Tech pool
    tech_pool = (job_net - total_deductions) / 2
    if tech_pool < 0:
        tech_pool = Decimal('0')

    total_hours = sum(data['hours'] for data in tech_data.values())
    weighted_sum = sum(data['min_pay'] * data['hours'] for data in tech_data.values())

    # Calculate base pay for each tech
    technicians = []
    total_base_pay = Decimal('0')

    for tid, data in tech_data.items():
        using_minimum = False
        if total_hours == 0:
            weight = Decimal('0')
            base_pay = Decimal('0')
            effective_rate = Decimal('0')
        elif len(tech_data) == 1:
            weight = Decimal('1')
            if data['hours'] > 0:
                calculated_rate = tech_pool / data['hours']
                if calculated_rate < data['min_pay']:
                    using_minimum = True
                    effective_rate = data['min_pay']
                else:
                    effective_rate = calculated_rate
                base_pay = data['hours'] * effective_rate
            else:
                effective_rate = data['min_pay']
                base_pay = Decimal('0')
        else:
            if weighted_sum > 0:
                weight = (data['min_pay'] * data['hours']) / weighted_sum
            else:
                weight = Decimal('1') / len(tech_data)

            weighted_base = tech_pool * weight
            min_pay_amount = data['hours'] * data['min_pay']
            if weighted_base < min_pay_amount:
                using_minimum = True
                base_pay = min_pay_amount
            else:
                base_pay = weighted_base

            if data['hours'] > 0:
                effective_rate = base_pay / data['hours']
            else:
                effective_rate = data['min_pay']

        # Reimbursable share
        if total_hours > 0 and total_reimbursables > 0:
            reimbursable_share = total_reimbursables * (data['hours'] / total_hours)
        else:
            reimbursable_share = Decimal('0')

        total_pay = base_pay + data['mileage_pay'] + data['per_diem'] + data['personal_expenses'] + reimbursable_share
        total_base_pay += base_pay

        technicians.append({
            'tech_id': tid,
            'tech_name': data['tech_name'],
            'hours': float(data['hours'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'min_pay': float(data['min_pay'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'weight': float(weight.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)) if len(tech_data) > 1 else 1.0,
            'base_pay': float(base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'mileage': float(data['mileage'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'mileage_pay': float(data['mileage_pay'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'per_diem': float(data['per_diem'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'personal_expenses': float(data['personal_expenses'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'reimbursable_share': float(reimbursable_share.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float(total_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'effective_rate': float(effective_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'using_minimum': using_minimum,
            'entries': data['entries']
        })

    return {
        'bundle': bundle.to_dict(),
        'jobs': [j.to_dict() for j in jobs],
        'job': {
            'job_id': f'bundle:{bundle_id}',
            'ticket_number': bundle.display_name,
            'description': bundle.display_name,
            'billing_amount': float(billing_amount),
            'expenses': float(expenses),
            'commissions': float(commissions),
        },
        'job_net': float(job_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'tech_pool': float(tech_pool.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_deductions': float(total_deductions.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'reimbursables': [r.to_dict() for r in reimbursables],
        'technicians': technicians,
        'totals': {
            'total_hours': float(total_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_base_pay': float(total_base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_mileage_pay': float(total_mileage_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_per_diem': float(total_per_diem.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_personal_expenses': float(total_personal_expenses.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_reimbursables': float(total_reimbursables.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float((total_base_pay + total_mileage_pay + total_per_diem + total_personal_expenses + total_reimbursables).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        }
    }


def calculate_tech_pay_summary(tech_id, start_date=None, end_date=None):
    """
    Calculate pay summary for a technician over a date range.

    Args:
        tech_id: Technician ID
        start_date: Start date filter (optional)
        end_date: End date filter (optional)

    Returns:
        dict: Summary of all pay for the technician
    """
    from sqlalchemy import and_

    query = TimeEntry.query.filter_by(tech_id=tech_id)

    if start_date:
        query = query.filter(TimeEntry.date_worked >= start_date)
    if end_date:
        query = query.filter(TimeEntry.date_worked <= end_date)

    entries = query.all()

    # Group by job
    job_ids = set(entry.job_id for entry in entries)

    jobs_pay = []
    totals = {
        'total_hours': Decimal('0'),
        'total_base_pay': Decimal('0'),
        'total_mileage_pay': Decimal('0'),
        'total_per_diem': Decimal('0'),
        'total_personal_expenses': Decimal('0'),
        'total_pay': Decimal('0')
    }

    for job_id in job_ids:
        job_pay = calculate_job_pay(job_id)
        if job_pay:
            # Find this tech's data in the job pay breakdown
            for tech in job_pay['technicians']:
                if tech['tech_id'] == tech_id:
                    jobs_pay.append({
                        'job': job_pay['job'],
                        'tech_pay': tech
                    })
                    totals['total_hours'] += Decimal(str(tech['hours']))
                    totals['total_base_pay'] += Decimal(str(tech['base_pay']))
                    totals['total_mileage_pay'] += Decimal(str(tech['mileage_pay']))
                    totals['total_per_diem'] += Decimal(str(tech['per_diem']))
                    totals['total_personal_expenses'] += Decimal(str(tech['personal_expenses']))
                    totals['total_pay'] += Decimal(str(tech['total_pay']))
                    break

    return {
        'tech_id': tech_id,
        'jobs': jobs_pay,
        'totals': {k: float(v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) for k, v in totals.items()}
    }


def _accumulate_tech_result(tech_results, tid, tech, job, td,
                            base_pay, effective_rate, using_minimum,
                            tech_hours_ratio, total_pay, profit_share):
    """Accumulate per-entry results into per-tech report structure.

    Creates one row per time entry instead of one row per job.
    Each entry gets the job's effective_rate applied to its individual hours.
    """
    if tid not in tech_results:
        tech_results[tid] = {
            'tech_id': tid,
            'tech_name': tech.name,
            'worker_type': tech.worker_type,
            'min_pay': float(Decimal(str(tech.hourly_rate or 0))),
            'total_hours': Decimal('0'),
            'total_base_pay': Decimal('0'),
            'total_mileage_pay': Decimal('0'),
            'total_per_diem': Decimal('0'),
            'total_personal_expenses': Decimal('0'),
            'total_pay': Decimal('0'),
            'total_profit_share': Decimal('0'),
            'jobs': [],
        }

    tr = tech_results[tid]
    job_dict = job.to_dict()

    # Create one row per entry, distributing the job-level rate to each
    for entry in td['raw_entries']:
        e_hours = Decimal(str(entry.hours_worked or 0))
        e_mileage = Decimal(str(entry.mileage or 0))
        e_mileage_rate = Decimal(str(MileageRateHistory.get_rate_for_date(entry.date_worked)))
        e_mileage_pay = e_mileage * e_mileage_rate
        e_per_diem = Decimal(str(entry.per_diem or 0))
        e_personal_expenses = Decimal(str(entry.personal_expenses or 0))

        e_base_pay = e_hours * effective_rate
        e_deductions = e_mileage_pay + e_per_diem + e_personal_expenses
        e_total_pay = e_base_pay + e_deductions

        # Profit share proportional to this entry's hours
        if td['hours'] > 0:
            e_profit_share = profit_share * (e_hours / td['hours'])
        else:
            e_profit_share = Decimal('0')

        date_str = entry.date_worked.isoformat() if entry.date_worked else None

        entry_data = {
            'job_id': job.job_id,
            'job': job_dict,
            'ticket_number': job.ticket_number,
            'description': job.description,
            'date_worked': date_str,
            'date_display': date_str,
            'entry_dates': [date_str] if date_str else [],
            'external_url': job.external_url,
            'hours': float(e_hours.quantize(Decimal('0.01'))),
            'hours_ratio': float(tech_hours_ratio.quantize(Decimal('0.0001'))) if tech_hours_ratio > 0 else 0,
            'base_pay': float(e_base_pay.quantize(Decimal('0.01'))),
            'mileage': float(e_mileage.quantize(Decimal('0.01'))),
            'mileage_pay': float(e_mileage_pay.quantize(Decimal('0.01'))),
            'per_diem': float(e_per_diem.quantize(Decimal('0.01'))),
            'personal_expenses': float(e_personal_expenses.quantize(Decimal('0.01'))),
            'effective_rate': float(effective_rate.quantize(Decimal('0.01'))),
            'using_minimum': using_minimum,
            'profit_share': float(e_profit_share.quantize(Decimal('0.01'))),
            'total_pay': float(e_total_pay.quantize(Decimal('0.01'))),
        }
        tr['jobs'].append(entry_data)

        # Accumulate tech totals
        tr['total_hours'] += e_hours
        tr['total_base_pay'] += e_base_pay
        tr['total_mileage_pay'] += e_mileage_pay
        tr['total_per_diem'] += e_per_diem
        tr['total_personal_expenses'] += e_personal_expenses
        tr['total_pay'] += e_total_pay
        tr['total_profit_share'] += e_profit_share


def calculate_period_pay(period_id=None, start_date=None, end_date=None, tech_ids=None):
    """
    Calculate pay for all technicians in a pay period or date range.

    Uses shared-pool weighted distribution for multi-tech jobs:
    - Pool all deductions across all techs on a job
    - 50/50 split of (prorated_net - pooled_deductions)
    - Distribute by weight = (min_pay * hours) / weighted_sum
    - Minimum rate enforcement per tech

    Args:
        period_id: PayPeriod ID (uses period's start/end dates)
        start_date: Override start date (for ad-hoc reports)
        end_date: Override end date (for ad-hoc reports)
        tech_ids: Optional list of tech IDs to filter (None = all)

    Returns:
        dict with 'period', 'technicians', 'grand_totals' keys
    """
    from app import db

    # Resolve date range
    period = None
    if period_id:
        period = PayPeriod.query.get(period_id)
        if not period:
            return None
        start_date = period.start_date
        end_date = period.end_date
    elif not start_date or not end_date:
        return None

    # Get all verified+ entries in the date range
    entry_query = TimeEntry.query.filter(
        TimeEntry.date_worked >= start_date,
        TimeEntry.date_worked <= end_date,
        TimeEntry.status.in_(['verified', 'billed', 'paid'])
    )

    if tech_ids:
        entry_query = entry_query.filter(TimeEntry.tech_id.in_(tech_ids))

    entries = entry_query.all()

    # Group entries by unit (job or bundle) → tech
    # For bundled jobs, entries merge under "bundle:<id>" key
    # For standalone jobs, entries stay under job_id key
    # {unit_key: {tech_id: [entries]}}
    job_tech_entries = {}
    seen_entry_ids = set()

    for entry in entries:
        # Determine unit key: bundle or standalone job
        if entry.bundle_id and not entry.job_id:
            # Bundle-only entry (no job)
            unit_key = f"bundle:{entry.bundle_id}"
        elif entry.job_id:
            job = Job.query.get(entry.job_id)
            if job and job.bundle_id:
                unit_key = f"bundle:{job.bundle_id}"
            else:
                unit_key = entry.job_id
        else:
            continue  # skip entries with neither job nor bundle

        if unit_key not in job_tech_entries:
            job_tech_entries[unit_key] = {}
        if entry.tech_id not in job_tech_entries[unit_key]:
            job_tech_entries[unit_key][entry.tech_id] = []
        job_tech_entries[unit_key][entry.tech_id].append(entry)
        seen_entry_ids.add(entry.entry_id)

    # Also pick up bundle-only entries (bundle_id set, job_id NULL) not already found
    bundle_only_query = TimeEntry.query.filter(
        TimeEntry.date_worked >= start_date,
        TimeEntry.date_worked <= end_date,
        TimeEntry.status.in_(['verified', 'billed', 'paid']),
        TimeEntry.bundle_id.isnot(None),
        TimeEntry.job_id.is_(None),
    )
    if tech_ids:
        bundle_only_query = bundle_only_query.filter(TimeEntry.tech_id.in_(tech_ids))

    for entry in bundle_only_query.all():
        if entry.entry_id in seen_entry_ids:
            continue
        unit_key = f"bundle:{entry.bundle_id}"
        if unit_key not in job_tech_entries:
            job_tech_entries[unit_key] = {}
        if entry.tech_id not in job_tech_entries[unit_key]:
            job_tech_entries[unit_key][entry.tech_id] = []
        job_tech_entries[unit_key][entry.tech_id].append(entry)

    # Precompute total hours (ALL entries, not just period) for each unit
    job_total_hours = {}
    for unit_key in job_tech_entries:
        if isinstance(unit_key, str) and unit_key.startswith("bundle:"):
            bid = int(unit_key.split(":")[1])
            bundle_obj = JobBundle.query.get(bid)
            if bundle_obj:
                bundled_job_ids = [j.job_id for j in bundle_obj.jobs.all()]
                if bundled_job_ids:
                    total = db.session.query(func.sum(TimeEntry.hours_worked)).filter(
                        db.or_(
                            TimeEntry.job_id.in_(bundled_job_ids),
                            TimeEntry.bundle_id == bid
                        )
                    ).scalar()
                else:
                    total = db.session.query(func.sum(TimeEntry.hours_worked)).filter_by(bundle_id=bid).scalar()
            else:
                total = Decimal('0')
            job_total_hours[unit_key] = Decimal(str(total or 0))
        else:
            total = db.session.query(func.sum(TimeEntry.hours_worked)).filter_by(job_id=unit_key).scalar()
            job_total_hours[unit_key] = Decimal(str(total or 0))

    # Process each unit (job or bundle), distribute pay across techs
    # Accumulate results per tech: {tech_id: {tech_data}}
    tech_results = {}

    for unit_key, tech_entries_map in job_tech_entries.items():
        # Build the job object: real Job for standalone, virtual object for bundles
        if isinstance(unit_key, str) and unit_key.startswith("bundle:"):
            bid = int(unit_key.split(":")[1])
            bundle_obj = JobBundle.query.get(bid)
            if not bundle_obj:
                continue
            bundled_jobs = bundle_obj.jobs.all()

            # Create a virtual job object with pooled financials
            class _VirtualBundleJob:
                pass
            job = _VirtualBundleJob()
            job.job_id = unit_key
            job.ticket_number = bundle_obj.display_name
            job.description = bundle_obj.display_name
            job.external_url = None
            job.billing_amount = float(sum(Decimal(str(j.billing_amount or 0)) for j in bundled_jobs))
            job.expenses = float(sum(Decimal(str(j.expenses or 0)) for j in bundled_jobs))
            job.commissions = float(sum(Decimal(str(j.commissions or 0)) for j in bundled_jobs))
            # to_dict for _accumulate_tech_result
            _bundle_dict = {
                'job_id': unit_key,
                'ticket_number': bundle_obj.display_name,
                'description': bundle_obj.display_name,
                'billing_amount': job.billing_amount,
                'expenses': job.expenses,
                'commissions': job.commissions,
                'external_url': None,
                'bundle_id': bid,
                'bundle_name': bundle_obj.display_name,
            }
            job.to_dict = lambda _d=_bundle_dict: _d
        else:
            job_id = unit_key
            job = Job.query.get(job_id)
            if not job:
                continue

        # --- Aggregate per-tech data for this unit ---
        job_techs = {}
        job_period_hours = Decimal('0')
        pooled_deductions = Decimal('0')

        for tid, tent_entries in tech_entries_map.items():
            tech = Technician.query.get(tid)
            if not tech:
                continue

            t_hours = Decimal('0')
            t_mileage_pay = Decimal('0')
            t_mileage = Decimal('0')
            t_per_diem = Decimal('0')
            t_personal_expenses = Decimal('0')
            t_entry_dates = set()

            for entry in tent_entries:
                hours = Decimal(str(entry.hours_worked or 0))
                mileage = Decimal(str(entry.mileage or 0))
                mileage_rate = Decimal(str(MileageRateHistory.get_rate_for_date(entry.date_worked)))

                t_hours += hours
                t_mileage += mileage
                t_mileage_pay += mileage * mileage_rate
                t_per_diem += Decimal(str(entry.per_diem or 0))
                t_personal_expenses += Decimal(str(entry.personal_expenses or 0))
                if entry.date_worked:
                    t_entry_dates.add(entry.date_worked.isoformat())

            t_deductions = t_mileage_pay + t_per_diem + t_personal_expenses
            pooled_deductions += t_deductions
            job_period_hours += t_hours

            earliest_date = min(t_entry_dates) if t_entry_dates else None
            rate_date = date_type.fromisoformat(earliest_date) if earliest_date else None
            min_pay_rate = Decimal(str(TechPayRateHistory.get_rate_for_date(tid, rate_date))) if rate_date else Decimal(str(tech.hourly_rate or 0))

            job_techs[tid] = {
                'tech': tech,
                'hours': t_hours,
                'mileage': t_mileage,
                'mileage_pay': t_mileage_pay,
                'per_diem': t_per_diem,
                'personal_expenses': t_personal_expenses,
                'deductions': t_deductions,
                'entry_dates': t_entry_dates,
                'raw_entries': tent_entries,
                'min_pay_rate': min_pay_rate,
            }

        if not job_techs:
            continue

        # --- Prorate job-level amounts by period share ---
        total_hours_for_job = job_total_hours.get(unit_key, Decimal('0'))
        if total_hours_for_job > 0:
            job_period_ratio = job_period_hours / total_hours_for_job
        else:
            job_period_ratio = Decimal('0')

        billing = Decimal(str(job.billing_amount or 0))
        job_expenses = Decimal(str(job.expenses or 0))
        job_commissions = Decimal(str(job.commissions or 0))

        prorated_billing = billing * job_period_ratio
        prorated_expenses = job_expenses * job_period_ratio
        prorated_commissions = job_commissions * job_period_ratio
        prorated_net = prorated_billing - prorated_expenses - prorated_commissions

        # --- Shared pool calculation ---
        tech_pool = (prorated_net - pooled_deductions) / 2
        if tech_pool < 0:
            tech_pool = Decimal('0')

        # --- Weighted distribution ---
        if len(job_techs) == 1:
            # Single tech on this unit in this period
            tid = next(iter(job_techs))
            td = job_techs[tid]
            min_pay_rate = td['min_pay_rate']

            if td['hours'] > 0:
                calculated_rate = tech_pool / td['hours']
                if calculated_rate < min_pay_rate:
                    effective_rate = min_pay_rate
                    using_minimum = True
                else:
                    effective_rate = calculated_rate
                    using_minimum = False
                base_pay = td['hours'] * effective_rate
            else:
                effective_rate = min_pay_rate
                base_pay = Decimal('0')
                using_minimum = False

            tech_hours_ratio = td['hours'] / total_hours_for_job if total_hours_for_job > 0 else Decimal('0')
            total_pay = base_pay + td['deductions']
            profit_share = prorated_net - total_pay

            _accumulate_tech_result(
                tech_results, tid, td['tech'], job, td,
                base_pay, effective_rate, using_minimum,
                tech_hours_ratio, total_pay, profit_share,
            )
        else:
            # Multiple techs — weight by min_pay * hours
            weighted_sum = Decimal('0')
            for tid, td in job_techs.items():
                weighted_sum += td['min_pay_rate'] * td['hours']

            for tid, td in job_techs.items():
                min_pay_rate = td['min_pay_rate']

                if weighted_sum > 0:
                    weight = (min_pay_rate * td['hours']) / weighted_sum
                else:
                    weight = Decimal('1') / len(job_techs)

                weighted_base = tech_pool * weight
                min_pay_amount = td['hours'] * min_pay_rate

                if weighted_base < min_pay_amount:
                    using_minimum = True
                    base_pay = min_pay_amount
                else:
                    using_minimum = False
                    base_pay = weighted_base

                if td['hours'] > 0:
                    effective_rate = base_pay / td['hours']
                else:
                    effective_rate = min_pay_rate

                tech_hours_ratio = td['hours'] / total_hours_for_job if total_hours_for_job > 0 else Decimal('0')
                total_pay = base_pay + td['deductions']
                profit_share = (prorated_net * (td['hours'] / job_period_hours)) - total_pay if job_period_hours > 0 else Decimal('0')

                _accumulate_tech_result(
                    tech_results, tid, td['tech'], job, td,
                    base_pay, effective_rate, using_minimum,
                    tech_hours_ratio, total_pay, profit_share,
                )

    # Build output sorted by tech name
    technicians_report = []
    grand_totals = {
        'total_hours': Decimal('0'),
        'total_base_pay': Decimal('0'),
        'total_mileage_pay': Decimal('0'),
        'total_per_diem': Decimal('0'),
        'total_personal_expenses': Decimal('0'),
        'total_pay': Decimal('0'),
    }

    for tid, tr in tech_results.items():
        for key in ['total_hours', 'total_base_pay', 'total_mileage_pay', 'total_per_diem',
                     'total_personal_expenses', 'total_pay', 'total_profit_share']:
            tr[key] = float(tr[key].quantize(Decimal('0.01')))

        for key in grand_totals:
            grand_totals[key] += Decimal(str(tr[key]))

        technicians_report.append(tr)

    technicians_report.sort(key=lambda t: t['tech_name'])

    return {
        'period': period.to_dict() if period else {'start_date': str(start_date), 'end_date': str(end_date)},
        'technicians': technicians_report,
        'grand_totals': {k: float(v.quantize(Decimal('0.01'))) for k, v in grand_totals.items()},
    }
