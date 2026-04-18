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

    # Worker classification
    worker_type = db.Column(db.String(20), nullable=False, default='contractor')

    # SMS opt-in tracking
    sms_opted_in = db.Column(db.Boolean, default=True, nullable=False)
    sms_opted_in_at = db.Column(db.DateTime, nullable=True)
    sms_opted_out_at = db.Column(db.DateTime, nullable=True)

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
            'sms_opted_in': self.sms_opted_in,
            'worker_type': self.worker_type,
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
    billing_rate = db.Column(db.Numeric(10, 2))
    billing_amount = db.Column(db.Numeric(10, 2))
    estimated_hours = db.Column(db.Numeric(8, 2))

    # Additional job financials
    expenses = db.Column(db.Numeric(10, 2), default=0)
    commissions = db.Column(db.Numeric(10, 2), default=0)

    # External platform URL
    external_url = db.Column(db.String(500))

    # Status
    job_status = db.Column(
        db.Enum('pending', 'assigned', 'in_progress', 'completed', 'cancelled'),
        default='pending'
    )

    # Dates
    job_date = db.Column(db.Date)
    scheduled_start_time = db.Column(db.Time, nullable=True)
    due_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    time_entries = db.relationship('TimeEntry', backref='job', lazy='dynamic')
    reimbursables = db.relationship('JobReimbursable', backref='job', lazy='dynamic', cascade='all, delete-orphan')

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
            'billing_rate': float(self.billing_rate) if self.billing_rate else None,
            'billing_amount': float(self.billing_amount) if self.billing_amount else None,
            'estimated_hours': float(self.estimated_hours) if self.estimated_hours else None,
            'expenses': float(self.expenses) if self.expenses else 0,
            'commissions': float(self.commissions) if self.commissions else 0,
            'external_url': self.external_url,
            'job_status': self.job_status,
            'job_date': self.job_date.isoformat() if self.job_date else None,
            'scheduled_start_time': self.scheduled_start_time.strftime('%H:%M') if self.scheduled_start_time else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def recalculate_hourly_billing(self):
        """Recalculate billing_amount for hourly jobs based on rate x total hours."""
        if self.billing_type != 'hourly' or not self.billing_rate:
            return
        from sqlalchemy import func as sqlfunc
        total_hours = db.session.query(
            sqlfunc.coalesce(sqlfunc.sum(TimeEntry.hours_worked), 0)
        ).filter_by(job_id=self.job_id).scalar()
        self.billing_amount = self.billing_rate * total_hours


class JobReimbursable(db.Model):
    """Reimbursable line item on a job (travel, parts, misc)."""
    __tablename__ = 'job_reimbursables'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.Enum('travel', 'parts', 'misc'), nullable=False, default='misc')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'description': self.description,
            'amount': float(self.amount) if self.amount else 0,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PayPeriod(db.Model):
    """Pay period model for organizing time entries."""
    __tablename__ = 'pay_periods'

    period_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    period_name = db.Column(db.String(50))
    status = db.Column(db.Enum('open', 'locked', 'closed', 'archived'), default='open')
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
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=True)
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
    source_hash = db.Column(db.String(64))  # For duplicate detection on imports

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
            'job_ticket': self.job.ticket_number if self.job else None,
            'job_title': self.job.description if self.job else None,
            'job_client': self.job.client_name if self.job else None,
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


class SystemSettings(db.Model):
    """System settings for global configuration values."""
    __tablename__ = 'system_settings'

    setting_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    setting_key = db.Column(db.String(50), nullable=False, unique=True)
    setting_value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    effective_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'setting_id': self.setting_id,
            'setting_key': self.setting_key,
            'setting_value': self.setting_value,
            'description': self.description,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
        }

    @staticmethod
    def get_value(key, default=None):
        """Get a setting value by key."""
        setting = SystemSettings.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default

    @staticmethod
    def get_float(key, default=0.0):
        """Get a setting value as float."""
        value = SystemSettings.get_value(key)
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default


class MileageRateHistory(db.Model):
    """Historical mileage rates for accurate pay calculation on past entries."""
    __tablename__ = 'mileage_rate_history'

    rate_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rate_per_mile = db.Column(db.Numeric(6, 4), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    description = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'rate_id': self.rate_id,
            'rate_per_mile': float(self.rate_per_mile),
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'description': self.description,
        }

    @staticmethod
    def get_rate_for_date(date):
        """Get the mileage rate effective for a specific date."""
        from sqlalchemy import and_
        rate = MileageRateHistory.query.filter(
            and_(
                MileageRateHistory.effective_date <= date,
                db.or_(
                    MileageRateHistory.end_date.is_(None),
                    MileageRateHistory.end_date >= date
                )
            )
        ).order_by(MileageRateHistory.effective_date.desc()).first()
        return float(rate.rate_per_mile) if rate else 0.67  # Default IRS rate


class JobAssignment(db.Model):
    """Job assignment model for tracking technician assignments to jobs."""
    __tablename__ = 'job_assignments'

    assignment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'), nullable=False)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=False)
    status = db.Column(
        db.Enum('invited', 'accepted', 'declined', 'expired', 'cancelled'),
        default='accepted'
    )
    is_primary = db.Column(db.Boolean, default=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    sms_sent = db.Column(db.Boolean, default=False)
    sms_sent_at = db.Column(db.DateTime)
    sms_delivery_status = db.Column(db.String(50), default='pending')
    availability_response = db.Column(db.Enum('pending', 'yes', 'no'), nullable=True)
    availability_responded_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = db.relationship('Job', backref=db.backref('assignments', lazy='dynamic'))
    technician = db.relationship('Technician', backref=db.backref('job_assignments', lazy='dynamic'))
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])

    def to_dict(self):
        return {
            'assignment_id': self.assignment_id,
            'job_id': self.job_id,
            'job_ticket': self.job.ticket_number if self.job else None,
            'job_description': self.job.description if self.job else None,
            'job_client': self.job.client_name if self.job else None,
            'job_location': self.job.location if self.job else None,
            'job_date': self.job.job_date.isoformat() if self.job and self.job.job_date else None,
            'job_status': self.job.job_status if self.job else None,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'tech_phone': self.technician.phone if self.technician else None,
            'status': self.status,
            'is_primary': self.is_primary,
            'assigned_by': self.assigned_by,
            'assigned_by_name': self.assigned_by_user.full_name if self.assigned_by_user else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'sms_sent': self.sms_sent,
            'sms_sent_at': self.sms_sent_at.isoformat() if self.sms_sent_at else None,
            'sms_delivery_status': self.sms_delivery_status,
            'availability_response': self.availability_response,
            'availability_responded_at': self.availability_responded_at.isoformat() if self.availability_responded_at else None,
            'notes': self.notes,
        }


class SMSNotification(db.Model):
    """SMS notification audit log."""
    __tablename__ = 'sms_notifications'

    notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    notification_type = db.Column(
        db.Enum('job_assignment', 'invitation', 'reminder', 'cancellation', 'update', 'other'),
        nullable=False
    )
    assignment_id = db.Column(db.Integer, db.ForeignKey('job_assignments.assignment_id'))
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'))
    phone_number = db.Column(db.String(20), nullable=False)
    message_body = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum('pending', 'sent', 'delivered', 'failed'),
        default='pending'
    )
    provider_message_id = db.Column(db.String(100))
    provider_response = db.Column(db.Text)
    error_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    is_spam = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    assignment = db.relationship('JobAssignment', backref=db.backref('sms_notifications', lazy='dynamic'))
    technician = db.relationship('Technician', backref=db.backref('sms_notifications', lazy='dynamic'))

    def to_dict(self):
        return {
            'notification_id': self.notification_id,
            'notification_type': self.notification_type,
            'assignment_id': self.assignment_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'phone_number': self.phone_number or '',
            'message_body': self.message_body,
            'status': self.status,
            'provider_message_id': self.provider_message_id,
            'error_message': self.error_message,
            'is_spam': self.is_spam,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ContactSubmission(db.Model):
    """Contact form submissions from the public contact page."""
    __tablename__ = 'contact_submissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'subject': self.subject,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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


class Payout(db.Model):
    """Payout record — one per tech per pay period, created at lock time."""
    __tablename__ = 'payouts'

    payout_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    period_id = db.Column(db.Integer, db.ForeignKey('pay_periods.period_id'), nullable=False)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=False)
    status = db.Column(db.Enum('locked', 'paid'), nullable=False, default='locked')
    total_hours = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_base_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_mileage_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_per_diem = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_personal_expenses = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_bonuses = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_deductions = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_advance_repayment = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    net_payout = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    locked_at = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime)
    paid_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    notes = db.Column(db.Text)

    # Relationships
    pay_period = db.relationship('PayPeriod', backref=db.backref('payouts', lazy='dynamic'))
    technician = db.relationship('Technician', backref=db.backref('payouts', lazy='dynamic'))
    job_details = db.relationship('PayoutJobDetail', backref='payout', lazy='dynamic', cascade='all, delete-orphan')
    line_items = db.relationship('PayoutLineItem', backref='payout', lazy='dynamic', cascade='all, delete-orphan')
    advance_repayments = db.relationship('AdvanceRepayment', backref='payout', lazy='dynamic', cascade='all, delete-orphan')
    adjustments = db.relationship('PayoutAdjustment', backref='payout', lazy='dynamic', cascade='all, delete-orphan')

    def recalculate_net(self):
        """Recalculate net_payout from component fields. Call after line item changes."""
        bonus_sum = sum(li.amount for li in self.line_items.filter_by(type='bonus').all())
        deduction_sum = sum(li.amount for li in self.line_items.filter_by(type='deduction').all())
        self.total_bonuses = bonus_sum
        self.total_deductions = deduction_sum
        self.net_payout = (
            self.total_base_pay + self.total_mileage_pay + self.total_per_diem
            + self.total_personal_expenses + self.total_bonuses
            - self.total_deductions - self.total_advance_repayment
        )

    def to_dict(self):
        return {
            'payout_id': self.payout_id,
            'period_id': self.period_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'worker_type': self.technician.worker_type if self.technician else None,
            'status': self.status,
            'total_hours': float(self.total_hours or 0),
            'total_base_pay': float(self.total_base_pay or 0),
            'total_mileage_pay': float(self.total_mileage_pay or 0),
            'total_per_diem': float(self.total_per_diem or 0),
            'total_personal_expenses': float(self.total_personal_expenses or 0),
            'total_bonuses': float(self.total_bonuses or 0),
            'total_deductions': float(self.total_deductions or 0),
            'total_advance_repayment': float(self.total_advance_repayment or 0),
            'net_payout': float(self.net_payout or 0),
            'locked_at': self.locked_at.isoformat() if self.locked_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'paid_by': self.paid_by,
            'notes': self.notes,
        }


class PayoutJobDetail(db.Model):
    """Snapshot of pay per job per tech per payout."""
    __tablename__ = 'payout_job_details'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'), nullable=False)
    date_worked = db.Column(db.Date, nullable=True)
    hours = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    base_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    mileage_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    per_diem = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    personal_expenses = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    effective_rate = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    profit_share = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    job = db.relationship('Job', backref=db.backref('payout_details', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'payout_id': self.payout_id,
            'job_id': self.job_id,
            'date_worked': self.date_worked.isoformat() if self.date_worked else None,
            'date_display': self.date_worked.isoformat() if self.date_worked else None,
            'job_ticket': self.job.ticket_number if self.job else None,
            'job_description': self.job.description if self.job else None,
            'job_client': self.job.client_name if self.job else None,
            'external_url': self.job.external_url if self.job else None,
            'hours': float(self.hours or 0),
            'base_pay': float(self.base_pay or 0),
            'mileage_pay': float(self.mileage_pay or 0),
            'per_diem': float(self.per_diem or 0),
            'personal_expenses': float(self.personal_expenses or 0),
            'effective_rate': float(self.effective_rate or 0),
            'profit_share': float(self.profit_share or 0),
        }


class PayoutLineItem(db.Model):
    """Bonus or deduction line item on a payout."""
    __tablename__ = 'payout_line_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.Enum('bonus', 'deduction'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'payout_id': self.payout_id,
            'type': self.type,
            'description': self.description,
            'amount': float(self.amount or 0),
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Advance(db.Model):
    """Advance given to a technician — carries balance across pay periods."""
    __tablename__ = 'advances'

    advance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tech_id = db.Column(db.Integer, db.ForeignKey('technicians.tech_id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    original_amount = db.Column(db.Numeric(10, 2), nullable=False)
    remaining_balance = db.Column(db.Numeric(10, 2), nullable=False)
    max_per_period = db.Column(db.Numeric(10, 2))
    status = db.Column(db.Enum('active', 'repaid', 'cancelled'), nullable=False, default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    repaid_at = db.Column(db.DateTime)

    technician = db.relationship('Technician', backref=db.backref('advances', lazy='dynamic'))
    repayments = db.relationship('AdvanceRepayment', backref='advance', lazy='dynamic')

    def to_dict(self):
        return {
            'advance_id': self.advance_id,
            'tech_id': self.tech_id,
            'tech_name': self.technician.name if self.technician else None,
            'description': self.description,
            'original_amount': float(self.original_amount or 0),
            'remaining_balance': float(self.remaining_balance or 0),
            'max_per_period': float(self.max_per_period) if self.max_per_period else None,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'repaid_at': self.repaid_at.isoformat() if self.repaid_at else None,
        }


class AdvanceRepayment(db.Model):
    """Tracks each deduction against an advance per payout period."""
    __tablename__ = 'advance_repayments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    advance_id = db.Column(db.Integer, db.ForeignKey('advances.advance_id'), nullable=False)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'advance_id': self.advance_id,
            'payout_id': self.payout_id,
            'amount': float(self.amount or 0),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PayoutAdjustment(db.Model):
    """Post-lock change detection record."""
    __tablename__ = 'payout_adjustments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payout_id = db.Column(db.Integer, db.ForeignKey('payouts.payout_id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.job_id'))
    entry_id = db.Column(db.Integer, db.ForeignKey('time_entries.entry_id'))
    description = db.Column(db.Text, nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    amount_diff = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    resolution = db.Column(db.Enum('pending', 'carried_forward', 'dismissed'), nullable=False, default='pending')
    resolved_to_period_id = db.Column(db.Integer, db.ForeignKey('pay_periods.period_id'))
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    job = db.relationship('Job', backref=db.backref('payout_adjustments', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'payout_id': self.payout_id,
            'type': self.type,
            'job_id': self.job_id,
            'job_ticket': self.job.ticket_number if self.job else None,
            'entry_id': self.entry_id,
            'description': self.description,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'amount_diff': float(self.amount_diff or 0),
            'resolution': self.resolution,
            'resolved_to_period_id': self.resolved_to_period_id,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
