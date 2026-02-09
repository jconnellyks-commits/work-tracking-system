"""
Frontend routes to serve the web application.
"""
from flask import Blueprint, render_template

frontend_bp = Blueprint('frontend', __name__)


@frontend_bp.route('/')
def index():
    """Serve the main application."""
    return render_template('index.html')


@frontend_bp.route('/login')
def login():
    """Serve the login page."""
    return render_template('login.html')


@frontend_bp.route('/privacy')
def privacy():
    """Serve the privacy policy page (public, no auth required)."""
    return render_template('privacy.html')


@frontend_bp.route('/sms-terms')
def sms_terms():
    """Serve the SMS terms and conditions page (public, no auth required)."""
    return render_template('sms_terms.html')
