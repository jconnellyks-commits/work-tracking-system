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
