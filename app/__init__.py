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
    CORS(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.jobs import jobs_bp
    from app.routes.time_entries import time_entries_bp
    from app.routes.reports import reports_bp
    from app.routes.technicians import technicians_bp
    from app.routes.settings import settings_bp
    from app.routes.imports import imports_bp
    from app.routes.frontend import frontend_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(time_entries_bp, url_prefix='/api/time-entries')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(technicians_bp, url_prefix='/api/technicians')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(imports_bp, url_prefix='/api/imports')
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

    logger.info("Application initialized successfully")
    return app
