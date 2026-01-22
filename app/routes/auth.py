"""
Authentication routes for user login, registration, and token management.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from app import db, bcrypt
from app.models import User, Technician
from app.utils.logging import get_logger, audit_logger
from app.utils.auth import (
    jwt_required_with_user,
    admin_required,
    rate_limiter,
    validate_password_strength,
)

auth_bp = Blueprint('auth', __name__)
logger = get_logger(__name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT tokens.

    Request body:
        {
            "email": "user@example.com",
            "password": "password123"
        }

    Returns:
        {
            "access_token": "...",
            "refresh_token": "...",
            "user": {...}
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    # Check rate limiting
    client_ip = request.remote_addr
    if rate_limiter.is_rate_limited(f"login:{client_ip}"):
        logger.warning(f"Rate limited login attempt from {client_ip}")
        return jsonify({'error': 'Too many login attempts. Please try again later.'}), 429

    # Find user
    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        rate_limiter.record_attempt(f"login:{client_ip}")
        logger.warning(f"Failed login attempt for email: {email}")
        audit_logger.log(
            action_type='login_failed',
            description=f"Failed login attempt for {email}",
        )
        return jsonify({'error': 'Invalid email or password'}), 401

    if user.status != 'active':
        logger.warning(f"Login attempt for inactive account: {email}")
        return jsonify({'error': 'Account is not active'}), 403

    # Successful login
    rate_limiter.reset(f"login:{client_ip}")

    access_token = create_access_token(identity=str(user.user_id))
    refresh_token = create_refresh_token(identity=str(user.user_id))

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    logger.info(f"User {user.email} logged in successfully")
    audit_logger.log(
        action_type='login',
        entity_type='user',
        entity_id=user.user_id,
        description=f"User {email} logged in",
        user_id=user.user_id
    )

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/register', methods=['POST'])
@admin_required
def register():
    """
    Register a new user (admin only).

    Request body:
        {
            "email": "user@example.com",
            "password": "password123",
            "full_name": "John Doe",
            "role": "technician",
            "tech_id": 1  (optional)
        }
    """
    # Rate limit user registration (even for admin)
    client_ip = request.remote_addr
    if rate_limiter.is_rate_limited(f"register:{client_ip}", max_attempts=10, window_seconds=300):
        logger.warning(f"Rate limited user registration from {client_ip}")
        return jsonify({'error': 'Too many registration attempts. Please try again later.'}), 429

    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    role = data.get('role', 'technician')
    tech_id = data.get('tech_id')

    # Validation
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if role not in ('admin', 'manager', 'technician'):
        return jsonify({'error': 'Invalid role'}), 400

    # Password strength validation
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Check existing user
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    # Validate tech_id if provided
    if tech_id:
        technician = Technician.query.get(tech_id)
        if not technician:
            return jsonify({'error': 'Technician not found'}), 404
        if User.query.filter_by(tech_id=tech_id).first():
            return jsonify({'error': 'Technician already has an account'}), 409

    # Create user
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    user = User(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        role=role,
        tech_id=tech_id,
        password_changed_at=datetime.utcnow()
    )

    db.session.add(user)
    db.session.commit()

    logger.info(f"New user registered: {email} with role {role}")
    audit_logger.log(
        action_type='user_created',
        entity_type='user',
        entity_id=user.user_id,
        new_values={'email': email, 'role': role, 'tech_id': tech_id},
        description=f"User {email} created by admin",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token."""
    # Rate limit token refresh attempts
    client_ip = request.remote_addr
    if rate_limiter.is_rate_limited(f"refresh:{client_ip}", max_attempts=20, window_seconds=60):
        logger.warning(f"Rate limited token refresh from {client_ip}")
        return jsonify({'error': 'Too many refresh attempts. Please try again later.'}), 429

    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))

    if not user or user.status != 'active':
        rate_limiter.record_attempt(f"refresh:{client_ip}")
        return jsonify({'error': 'User not found or inactive'}), 401

    access_token = create_access_token(identity=str(current_user_id))

    return jsonify({'access_token': access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required_with_user
def get_current_user():
    """Get current authenticated user's profile."""
    user = g.current_user
    return jsonify({'user': user.to_dict(include_sensitive=True)}), 200


@auth_bp.route('/me', methods=['PUT'])
@jwt_required_with_user
def update_profile():
    """
    Update current user's profile.

    Request body:
        {
            "full_name": "New Name",
            "current_password": "...",
            "new_password": "..."  (optional)
        }
    """
    user = g.current_user
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = {'full_name': user.full_name}

    # Update name if provided
    if 'full_name' in data:
        user.full_name = data['full_name'].strip()

    # Handle password change
    if 'new_password' in data:
        # Rate limit password change attempts
        client_ip = request.remote_addr
        if rate_limiter.is_rate_limited(f"password_change:{user.user_id}:{client_ip}", max_attempts=5, window_seconds=300):
            logger.warning(f"Rate limited password change attempt for user {user.user_id} from {client_ip}")
            return jsonify({'error': 'Too many password change attempts. Please try again later.'}), 429

        current_password = data.get('current_password', '')

        if not bcrypt.check_password_hash(user.password_hash, current_password):
            rate_limiter.record_attempt(f"password_change:{user.user_id}:{client_ip}")
            return jsonify({'error': 'Current password is incorrect'}), 400

        is_valid, error_msg = validate_password_strength(data['new_password'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        user.password_hash = bcrypt.generate_password_hash(
            data['new_password']
        ).decode('utf-8')
        user.password_changed_at = datetime.utcnow()

    db.session.commit()

    audit_logger.log(
        action_type='profile_updated',
        entity_type='user',
        entity_id=user.user_id,
        old_values=old_values,
        new_values={'full_name': user.full_name},
        description='User updated their profile',
        user_id=user.user_id
    )

    return jsonify({
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    }), 200


@auth_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    """List all users (admin only)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    status_filter = request.args.get('status')
    role_filter = request.args.get('role')

    query = User.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if role_filter:
        query = query.filter_by(role=role_filter)

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@auth_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Get a specific user by ID (admin only)."""
    user = User.query.get_or_404(user_id)
    return jsonify({'user': user.to_dict(include_sensitive=True)}), 200


@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """
    Update a user (admin only).

    Request body:
        {
            "role": "manager",
            "status": "active"
        }
    """
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = {'role': user.role, 'status': user.status}

    if 'role' in data:
        if data['role'] not in ('admin', 'manager', 'technician'):
            return jsonify({'error': 'Invalid role'}), 400
        user.role = data['role']

    if 'status' in data:
        if data['status'] not in ('active', 'inactive', 'suspended'):
            return jsonify({'error': 'Invalid status'}), 400
        user.status = data['status']

    if 'full_name' in data:
        user.full_name = data['full_name'].strip()

    db.session.commit()

    audit_logger.log(
        action_type='user_updated',
        entity_type='user',
        entity_id=user.user_id,
        old_values=old_values,
        new_values={'role': user.role, 'status': user.status},
        description=f"User {user.email} updated by admin",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'User updated successfully',
        'user': user.to_dict()
    }), 200


@auth_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """
    Reset a user's password (admin only).

    Request body:
        {
            "new_password": "newpassword123"
        }
    """
    # Rate limit password resets (even for admin)
    client_ip = request.remote_addr
    if rate_limiter.is_rate_limited(f"admin_reset:{client_ip}", max_attempts=10, window_seconds=300):
        logger.warning(f"Rate limited admin password reset from {client_ip}")
        return jsonify({'error': 'Too many password reset attempts. Please try again later.'}), 429

    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if not data or 'new_password' not in data:
        return jsonify({'error': 'New password required'}), 400

    is_valid, error_msg = validate_password_strength(data['new_password'])
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    user.password_hash = bcrypt.generate_password_hash(
        data['new_password']
    ).decode('utf-8')
    user.password_changed_at = datetime.utcnow()

    db.session.commit()

    audit_logger.log(
        action_type='password_reset',
        entity_type='user',
        entity_id=user.user_id,
        description=f"Password reset for user {user.email} by admin",
        user_id=g.user_id
    )

    return jsonify({'message': 'Password reset successfully'}), 200
