# Work Tracking System - Project Context

## Overview
Flask-based work tracking and timesheet system for managing technician time entries, job billing, and payroll calculations.

## Tech Stack
- **Backend**: Flask + SQLAlchemy
- **Database**: MySQL (`work_tracking_db`)
- **Frontend**: Vanilla JavaScript (single-page app)
- **Server**: GCP Compute Engine with Gunicorn + systemd

## Server Access
- **IP**: 34.27.146.58
- **SSH Key**: `~/.ssh/gcp_work_tracking`
- **SSH Command**: `ssh -i "$HOME/.ssh/gcp_work_tracking" claude-code@34.27.146.58`
- **App Directory**: `/opt/work-tracking`
- **Service**: `work-tracking` (systemd)
- **Restart**: `sudo systemctl restart work-tracking`

## Deployment
```bash
# From local Windows machine:
git push origin main
ssh -i "$HOME/.ssh/gcp_work_tracking" claude-code@34.27.146.58 "cd /opt/work-tracking && sudo git pull && sudo systemctl restart work-tracking"
```

## Database
- **User**: `work_tracking`
- **Password**: stored in `/opt/work-tracking/.env` on server
- **Migrations**: `database/migrations/` directory (run manually with mysql client)

## Key Directories
```
app/
  routes/          # API endpoints
    auth.py        # Authentication, user management
    jobs.py        # Job CRUD
    time_entries.py # Time entry CRUD, submit/verify workflow
    technicians.py # Technician management
    reports.py     # Payroll, income/expense, dashboard reports
    settings.py    # System settings, mileage rates
  models.py        # SQLAlchemy models
  static/
    js/
      app.js       # Main frontend application
      api.js       # API client
    css/
      style.css    # All styles
  templates/       # HTML templates (login.html, index.html)
  utils/
    pay_calculator.py  # Pay calculation logic
    auth.py            # JWT auth utilities
    logging.py         # Logging and audit utilities
```

## Pay Calculation System
- 50% tech pool formula: `(billing - expenses - commissions) * 0.5`
- Weighted distribution by hours worked
- Minimum pay rate per technician (stored as `hourly_rate` on technician)
- Uses higher of: calculated rate vs minimum rate
- Adds: mileage pay, per diem, personal expenses

## Key Features
- **Time Entries**: Draft -> Submitted -> Verified -> Billed -> Paid workflow
- **Jobs**: Track billing, expenses, commissions, external platform URLs
- **Payroll Report**: Per-technician breakdown with job details, pay calculation, profit share
- **Income/Expense Report**: Job profitability analysis
- **Profit Share**: Proportional to technician's hours vs total job hours
- **Technician Management**: Create technicians, link to user accounts
- **Mileage Rate History**: Track IRS rates over time

## Recent Work (Jan 2026)
1. Added financial fields (mileage, per_diem, personal_expenses for entries; expenses, commissions for jobs)
2. Built pay calculation system with 50% tech pool formula
3. Added mileage rate history tracking
4. Rebuilt payroll reports with per-technician job breakdowns
5. Added external URL field to jobs for linking to platform pages
6. Added print and CSV export to payroll report
7. Replaced job billing report with income/expense report
8. Added profit column showing each tech's proportional share based on hours ratio
9. Added total profit share to technician totals row

## Database Migrations Run
- 001: Initial schema
- 002: Financial fields (mileage, per_diem, personal_expenses, expenses, commissions)
- 003: Mileage rate history table
- 004: External URL field on jobs

## User Roles
- **admin**: Full access
- **manager**: Can verify entries, view all reports, manage jobs
- **technician**: Can create/submit own time entries, view own data

## API Authentication
- JWT tokens stored in localStorage
- Access token + refresh token pattern
- Token refresh handled automatically in api.js
