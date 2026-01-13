"""
Comprehensive logging configuration for the Work Tracking System.
Provides structured logging with file and console handlers,
request logging, and audit trail integration.
"""
import logging
import os
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from functools import wraps
from flask import request, g, has_request_context


class RequestFormatter(logging.Formatter):
    """Custom formatter that includes request context information."""

    def format(self, record):
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
            record.method = request.method
            record.request_id = getattr(g, 'request_id', '-')
            record.user_id = getattr(g, 'user_id', '-')
        else:
            record.url = '-'
            record.remote_addr = '-'
            record.method = '-'
            record.request_id = '-'
            record.user_id = '-'

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        if has_request_context():
            log_data.update({
                'request_id': getattr(g, 'request_id', None),
                'user_id': getattr(g, 'user_id', None),
                'ip': request.remote_addr,
                'method': request.method,
                'url': request.url,
            })

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(app):
    """
    Configure application logging with file and console handlers.

    Args:
        app: Flask application instance
    """
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
    log_file = app.config.get('LOG_FILE', 'logs/app.log')
    max_bytes = app.config.get('LOG_MAX_BYTES', 10485760)
    backup_count = app.config.get('LOG_BACKUP_COUNT', 5)

    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Console handler with colored output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = RequestFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | [%(request_id)s] '
        '%(remote_addr)s %(method)s %(url)s | %(message)s'
    )
    console_handler.setFormatter(console_format)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    # Request logging
    @app.before_request
    def before_request():
        import uuid
        g.request_id = str(uuid.uuid4())[:8]
        g.request_start_time = datetime.utcnow()
        app.logger.debug(f"Request started: {request.method} {request.path}")

    @app.after_request
    def after_request(response):
        if hasattr(g, 'request_start_time'):
            duration = (datetime.utcnow() - g.request_start_time).total_seconds() * 1000
            app.logger.info(
                f"Request completed: {request.method} {request.path} "
                f"-> {response.status_code} ({duration:.2f}ms)"
            )
        return response


def get_logger(name):
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


def log_action(action_type, entity_type=None):
    """
    Decorator to log actions with audit trail.

    Args:
        action_type: Type of action (create, update, delete, etc.)
        entity_type: Type of entity being acted upon

    Usage:
        @log_action('create', 'job')
        def create_job():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            logger = get_logger(f.__module__)
            user_id = getattr(g, 'user_id', 'anonymous')

            logger.info(f"Action: {action_type} {entity_type or ''} by user {user_id}")

            try:
                result = f(*args, **kwargs)
                logger.info(f"Action completed: {action_type} {entity_type or ''}")
                return result
            except Exception as e:
                logger.error(
                    f"Action failed: {action_type} {entity_type or ''} - {str(e)}",
                    exc_info=True
                )
                raise

        return decorated_function
    return decorator


class AuditLogger:
    """
    Audit logger for recording system actions to the database.
    Integrates with the audit_logs table.
    """

    def __init__(self, app=None):
        self.app = app
        self.logger = get_logger('audit')

    def log(self, action_type, entity_type=None, entity_id=None,
            old_values=None, new_values=None, description=None, user_id=None):
        """
        Log an action to the audit trail.

        Args:
            action_type: Type of action performed
            entity_type: Type of entity affected
            entity_id: ID of the entity affected
            old_values: Previous values (for updates)
            new_values: New values
            description: Human-readable description
            user_id: ID of user performing action
        """
        from app.models import AuditLog
        from app import db

        if user_id is None and has_request_context():
            user_id = getattr(g, 'user_id', None)

        ip_address = None
        user_agent = None

        if has_request_context():
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent')

        audit_entry = AuditLog(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

        try:
            db.session.add(audit_entry)
            db.session.commit()
            self.logger.info(f"Audit: {action_type} {entity_type}:{entity_id} by user {user_id}")
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to write audit log: {e}")


# Global audit logger instance
audit_logger = AuditLogger()
