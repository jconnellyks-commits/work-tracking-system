"""
SQLAlchemy models for the Work Tracking System.
Maps to the MySQL database schema defined in database/schema.sql.
"""
from datetime import datetime
from app import db


class Technician(db.Model):
    """Technician/team member model."""
    __tablename__ = 'technicians'

    tech_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    hourly_rate = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.Enum('active', 'inactive'), default='active')
    hire_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    time_entries = db.relationship('TimeEntry', backref='technician', lazy='dynamic')
    user = db.relationship('User', backref='technician', uselist=False)

    def to_dict(self):
        return {
            'tech_id': self.tech_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'hourly_rate': float(self.hourly_rate) if self.hourly_rate else 0,
            'status': self.status,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Platform(db.Model):
    """Job platform model (WorkMarket, FieldNation, etc.)."""
    __tablename__ = 'platforms'

    platform_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.Text)
    api_endpoint = db.Column(db.String(255))
    status = db.Column(db.Enum('active', 'inactive'), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    jobs = db.relationship('Job', backref='platform', lazy='dynamic')

    def to_dict(self):
        return {
            'platform_id': self.platform_id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'status': self.status,
        }


class Job(db.Model):
    """Job/work order model."""
    __tablename__ = 'jobs'

    job_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platforms.platform_id'), nullable=False)
    platform_job_code = db.Column(db.String(50))
    ticket_number = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(255), nullable=False)
    client_name = db.Column(db.String(100))
    job_type = db.Column(db.String(100))
    location = db.Column(db.String(255))

    # Billing
    billing_type = db.Column(db.Enum('flat_rate', 'hourly', 'per_task'), default='flat_rate')
    billing_amount = db.Column(db.Numeric(10, 2))
    estimated_hours = db.Column(db.Numeric(8, 2))

    # Additional job financials
    expenses = db.Column(db.Numeric(10, 2), default=0)
    commissions = db.Column(db.Numeric(10, 2), default=0)

    # Status
    job_status = db.Column(
        db.Enum('pending', 'assigned', 'in_progress', 'completed', 'cancelled'),
        default='pending'
    )

    # Dates
    job_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    time_entries = db.relationship('TimeEntry', backref='job', lazy='dynamic')

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'platform_id': self.platform_id,
            'platform_name': self.platform.name if self.platform else None,
            'platform_job_code': self.platform_job_code,
            'ticket_number': self.ticket_number,
            'description': self.description,
            'client_name': self.client_name,
            'job_type': self.job_type,
            'location': self.location,
            'billing_type': self.billing_type,
            'billing_amount': float(self.billing_amount) if self.billing_amount else None,
            'estimated_hours': float(self.estimated_hours) if self.estimated_hours else None,
            'expenses': float(self.expenses) if self.expenses else 0,
            'commissions': float(self.commissions) if self.commissions else 0,
            'job_status': self.job_status,
            'job_date': self.job_date.isoformat() if self.job_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PayPeriod(db.Model):
    """Pay period model for organizing time entries."""
    __tablename__ = 'pay_periods'

    period_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    period_name = db.Column(db.String(50))
    status = db.Column(db.Enum('open', 'closed', 'archived'), default='open')
    total_hours = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    # Relationships
    time_entries = db.relationship('TimeEntry', backref='pay_period', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='pay_period', lazy='dynamic')

    def to_dict(self):
        return {
            'period_id': self.period_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'period_name': self.period_name,
            'status': self.status,
            'total_hours': float(self.total_hours) if self.total_hours else None,
        }


class TimeEntry(db.Model):
    """Time entry model for tracking work hours."""
    __tablename__ = 'time_entries'

    entry_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'), nullable=False)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey('pay_periods.period_id'))

    # Time information
    date_worked = db.Column(db.Date, nullable=False)
    time_in = db.Column(db.Time)
    time_out = db.Column(db.Time)
    hours_worked = db.Column(db.Numeric(8, 2))

    # Technician expenses/reimbursements
    mileage = db.Column(db.Numeric(8, 2), default=0)
    personal_expenses = db.Column(db.Numeric(10, 2), default=0)
    per_diem = db.Column(db.Numeric(10, 2), default=0)

    # Status
    status = db.Column(
        db.Enum('draft', 'submitted', 'verified', 'billed', 'paid'),
        default='draft'
    )
    notes = db.Column(db.Text)

    # Verification
    verified_by = db.Column(db.Integer)
    verified_at = db.Column(db.DateTime)

    # Audit fields
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'entry_id': self.entry_id,
            'job_id': self.job_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'period_id': self.period_id,
            'date_worked': self.date_worked.isoformat() if self.date_worked else None,
            'time_in': self.time_in.isoformat() if self.time_in else None,
            'time_out': self.time_out.isoformat() if self.time_out else None,
            'hours_worked': float(self.hours_worked) if self.hours_worked else None,
            'mileage': float(self.mileage) if self.mileage else 0,
            'personal_expenses': float(self.personal_expenses) if self.personal_expenses else 0,
            'per_diem': float(self.per_diem) if self.per_diem else 0,
            'status': self.status,
            'notes': self.notes,
            'verified_by': self.verified_by,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class User(db.Model):
    """System user model with authentication and roles."""
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'))
    email = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.Enum('admin', 'manager', 'technician'), default='technician')
    status = db.Column(db.Enum('active', 'inactive', 'suspended'), default='active')
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    password_changed_at = db.Column(db.DateTime)

    # Relationships
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def to_dict(self, include_sensitive=False):
        data = {
            'user_id': self.user_id,
            'tech_id': self.tech_id,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'status': self.status,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        if include_sensitive:
            data['created_at'] = self.created_at.isoformat() if self.created_at else None
        return data

    def is_admin(self):
        return self.role == 'admin'

    def is_manager(self):
        return self.role in ('admin', 'manager')


class Invoice(db.Model):
    """Invoice model for billing."""
    __tablename__ = 'invoices'

    invoice_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_number = db.Column(db.String(50), unique=True)
    period_id = db.Column(db.Integer, db.ForeignKey('pay_periods.period_id'))

    # Totals
    subtotal = db.Column(db.Numeric(10, 2))
    tax = db.Column(db.Numeric(10, 2))
    total_amount = db.Column(db.Numeric(10, 2))

    # Status
    status = db.Column(
        db.Enum('draft', 'sent', 'partially_paid', 'paid', 'overdue', 'cancelled'),
        default='draft'
    )

    # Dates
    issue_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'invoice_id': self.invoice_id,
            'invoice_number': self.invoice_number,
            'period_id': self.period_id,
            'subtotal': float(self.subtotal) if self.subtotal else None,
            'tax': float(self.tax) if self.tax else None,
            'total_amount': float(self.total_amount) if self.total_amount else None,
            'status': self.status,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_date': self.paid_date.isoformat() if self.paid_date else None,
        }


class AuditLog(db.Model):
    """Audit log model for tracking all system actions."""
    __tablename__ = 'audit_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    action_type = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)

    # Change tracking
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)

    # Details
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'log_id': self.log_id,
            'user_id': self.user_id,
            'user_email': self.user.email if self.user else None,
            'action_type': self.action_type,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'description': self.description,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
