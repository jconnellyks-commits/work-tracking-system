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
from decimal import Decimal, ROUND_HALF_UP
from app.models import Job, TimeEntry, Technician, MileageRateHistory


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
            'technicians': [],
            'totals': {
                'total_hours': 0,
                'total_base_pay': 0,
                'total_mileage_pay': 0,
                'total_per_diem': 0,
                'total_personal_expenses': 0,
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
            tech_data[tech_id] = {
                'tech_id': tech_id,
                'tech_name': tech.name if tech else f'Tech #{tech_id}',
                'min_pay': Decimal(str(tech.hourly_rate or 0)) if tech else Decimal('0'),
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

        total_pay = base_pay + data['mileage_pay'] + data['per_diem'] + data['personal_expenses']
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
        'technicians': technicians,
        'totals': {
            'total_hours': float(total_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_base_pay': float(total_base_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_mileage_pay': float(total_mileage_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_per_diem': float(total_per_diem.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_personal_expenses': float(total_personal_expenses.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'total_pay': float((total_base_pay + total_mileage_pay + total_per_diem + total_personal_expenses).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
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
