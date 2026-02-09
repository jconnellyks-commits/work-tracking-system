"""
Frontend routes to serve the web application.
"""
from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import ContactSubmission

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


@frontend_bp.route('/contact')
def contact():
    """Serve the contact form page (public, no auth required)."""
    return render_template('contact.html')


@frontend_bp.route('/api/contact', methods=['POST'])
def contact_submit():
    """Handle contact form submissions (public, rate limited)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    subject = (data.get('subject') or '').strip()
    message = (data.get('message') or '').strip()

    if not all([name, email, subject, message]):
        return jsonify({'error': 'All fields are required'}), 400

    if len(name) > 100 or len(email) > 100 or len(subject) > 200 or len(message) > 5000:
        return jsonify({'error': 'One or more fields exceed maximum length'}), 400

    submission = ContactSubmission(
        name=name,
        email=email,
        subject=subject,
        message=message
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify({'message': 'Message sent successfully'}), 200
