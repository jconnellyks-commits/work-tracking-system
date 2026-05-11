"""
Work Tracking System - Flask Application Factory

This module creates and configures the Flask application using the
application factory pattern for flexibility and testing.
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS

from app.config import get_config
from app.utils.logging import setup_logging, get_logger

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()

logger = get_logger(__name__)


def create_app(config_class=None):
    """
    Application factory for creating Flask app instances.

    Args:
        config_class: Configuration class to use. If None, uses environment-based config.

    Returns:
        Flask: Configured Flask application instance.
    """
    app = Flask(__name__)

    # Load configuration
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Setup logging
    setup_logging(app)
    logger.info(f"Starting {app.config.get('APP_NAME', 'Work Tracking System')}")

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # Configure CORS - restrict to specified origins
    cors_origins = app.config.get('CORS_ORIGINS', [])
    if cors_origins:
        CORS(app, origins=cors_origins,
             supports_credentials=app.config.get('CORS_SUPPORTS_CREDENTIALS', True))
        logger.info(f"CORS enabled for origins: {cors_origins}")
    else:
        # No origins configured - allow same-origin only (default secure behavior)
        CORS(app, origins=[],
             supports_credentials=app.config.get('CORS_SUPPORTS_CREDENTIALS', True))
        logger.info("CORS configured for same-origin only (no external origins allowed)")

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.jobs import jobs_bp
    from app.routes.time_entries import time_entries_bp
    from app.routes.reports import reports_bp
    from app.routes.technicians import technicians_bp
    from app.routes.settings import settings_bp
    from app.routes.imports import imports_bp
    from app.routes.frontend import frontend_bp
    from app.routes.assignments import assignments_bp
    from app.routes.sms_webhook import sms_webhook_bp
    from app.routes.payouts import payouts_bp
    from app.routes.advances import advances_bp
    from app.routes.payout_adjustments import payout_adjustments_bp
    from app.routes.my import my_bp
    from app.routes.email_parser import email_parser_bp
    from app.routes.bundles import bundles_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(time_entries_bp, url_prefix='/api/time-entries')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(technicians_bp, url_prefix='/api/technicians')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(imports_bp, url_prefix='/api/imports')
    app.register_blueprint(assignments_bp, url_prefix='/api/assignments')
    app.register_blueprint(payouts_bp, url_prefix='/api/payouts')
    app.register_blueprint(advances_bp, url_prefix='/api/advances')
    app.register_blueprint(payout_adjustments_bp, url_prefix='/api/payout-adjustments')
    app.register_blueprint(my_bp, url_prefix='/api/my')
    app.register_blueprint(email_parser_bp, url_prefix='/api/email-parser')
    app.register_blueprint(bundles_bp, url_prefix='/api/bundles')
    app.register_blueprint(sms_webhook_bp)  # No prefix — route is /sms/inbound
    app.register_blueprint(frontend_bp)

    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'app': app.config.get('APP_NAME')}

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'error': 'Token has expired', 'code': 'token_expired'}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'error': 'Invalid token', 'code': 'invalid_token'}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {'error': 'Authorization token required', 'code': 'token_required'}, 401

    # Security headers
    @app.after_request
    def add_security_headers(response):
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # XSS protection (legacy, but still useful for older browsers)
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Referrer policy - don't leak referrer to other origins
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions policy - restrict browser features
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        # Content Security Policy - restrict resource loading
        # Note: unsafe-inline required for this vanilla JS app with inline scripts/styles
        # CDNs allowed: jsdelivr (Chart.js), cdnjs (Font Awesome)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com",
            "img-src 'self' data:",
            "font-src 'self' https://cdnjs.cloudflare.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers['Content-Security-Policy'] = '; '.join(csp_directives)

        # HSTS - only enable in production with valid SSL
        if app.config.get('SESSION_COOKIE_SECURE', False):
            # 1 year max-age, include subdomains
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    logger.info("Application initialized successfully")
    return app
