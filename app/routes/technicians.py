"""
Technician management routes.
Every technician can have a linked user account.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db, bcrypt
from app.models import Technician, User
from app.utils.logging import get_logger, audit_logger
from app.utils.auth import jwt_required_with_user, admin_required, validate_password_strength

technicians_bp = Blueprint('technicians', __name__)
logger = get_logger(__name__)


@technicians_bp.route('', methods=['GET'])
@jwt_required_with_user
def list_technicians():
    """List all technicians with optional filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status')
    search = request.args.get('search', '').strip()

    query = Technician.query

    if status:
        query = query.filter_by(status=status)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Technician.name.ilike(search_term),
                Technician.email.ilike(search_term)
            )
        )

    query = query.order_by(Technician.name)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Include linked user info
    technicians_data = []
    for tech in pagination.items:
        tech_dict = tech.to_dict()
        # Check if technician has a linked user
        linked_user = User.query.filter_by(tech_id=tech.tech_id).first()
        tech_dict['has_user_account'] = linked_user is not None
        if linked_user:
            tech_dict['user_email'] = linked_user.email
            tech_dict['user_id'] = linked_user.user_id
        technicians_data.append(tech_dict)

    return jsonify({
        'technicians': technicians_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@technicians_bp.route('/<int:tech_id>', methods=['GET'])
@jwt_required_with_user
def get_technician(tech_id):
    """Get a specific technician."""
    tech = Technician.query.get_or_404(tech_id)
    tech_dict = tech.to_dict()

    # Include linked user info
    linked_user = User.query.filter_by(tech_id=tech.tech_id).first()
    tech_dict['has_user_account'] = linked_user is not None
    if linked_user:
        tech_dict['user_email'] = linked_user.email
        tech_dict['user_id'] = linked_user.user_id
        tech_dict['user_status'] = linked_user.status

    return jsonify({'technician': tech_dict}), 200


@technicians_bp.route('', methods=['POST'])
@admin_required
def create_technician():
    """
    Create a new technician, optionally with a user account.

    Request body:
        {
            "name": "John Smith",
            "email": "john@example.com",
            "phone": "555-0101",
            "hourly_rate": 25.00,
            "create_user_account": true,
            "password": "Password123"  (required if create_user_account is true)
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()

    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Check for duplicate email in technicians
    if email:
        existing_tech = Technician.query.filter_by(email=email).first()
        if existing_tech:
            return jsonify({'error': 'A technician with this email already exists'}), 409

    # Create technician
    tech = Technician(
        name=name,
        email=email or None,
        phone=data.get('phone', '').strip() or None,
        hourly_rate=data.get('hourly_rate') or None,
        status=data.get('status', 'active')
    )

    db.session.add(tech)
    db.session.flush()  # Get the tech_id

    # Optionally create user account
    user = None
    if data.get('create_user_account'):
        if not email:
            db.session.rollback()
            return jsonify({'error': 'Email is required to create a user account'}), 400

        password = data.get('password', '')
        if not password:
            db.session.rollback()
            return jsonify({'error': 'Password is required to create a user account'}), 400

        # Validate password
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            db.session.rollback()
            return jsonify({'error': error_msg}), 400

        # Check if user with this email exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            db.session.rollback()
            return jsonify({'error': 'A user with this email already exists'}), 409

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        user = User(
            email=email,
            password_hash=password_hash,
            full_name=name,
            role='technician',
            tech_id=tech.tech_id,
            password_changed_at=datetime.utcnow()
        )
        db.session.add(user)

    db.session.commit()

    logger.info(f"Technician created: {tech.tech_id} - {tech.name}")
    audit_logger.log(
        action_type='technician_created',
        entity_type='technician',
        entity_id=tech.tech_id,
        new_values=tech.to_dict(),
        description=f"Technician {tech.name} created",
        user_id=g.user_id
    )

    response_data = {
        'message': 'Technician created successfully',
        'technician': tech.to_dict()
    }

    if user:
        response_data['user'] = user.to_dict()
        response_data['message'] = 'Technician and user account created successfully'

    return jsonify(response_data), 201


@technicians_bp.route('/<int:tech_id>', methods=['PUT'])
@admin_required
def update_technician(tech_id):
    """
    Update a technician.

    Request body:
        {
            "name": "John Smith",
            "email": "john@example.com",
            "phone": "555-0101",
            "hourly_rate": 30.00,
            "status": "active"
        }
    """
    tech = Technician.query.get_or_404(tech_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    old_values = tech.to_dict()

    # Update fields
    if 'name' in data:
        tech.name = data['name'].strip()

    if 'email' in data:
        new_email = data['email'].strip().lower() if data['email'] else None
        if new_email and new_email != tech.email:
            existing = Technician.query.filter(
                Technician.email == new_email,
                Technician.tech_id != tech_id
            ).first()
            if existing:
                return jsonify({'error': 'A technician with this email already exists'}), 409
        tech.email = new_email

    if 'phone' in data:
        tech.phone = data['phone'].strip() or None

    if 'hourly_rate' in data:
        tech.hourly_rate = data['hourly_rate'] or None

    if 'status' in data:
        if data['status'] not in ('active', 'inactive'):
            return jsonify({'error': 'Invalid status'}), 400
        tech.status = data['status']

    db.session.commit()

    logger.info(f"Technician updated: {tech.tech_id}")
    audit_logger.log(
        action_type='technician_updated',
        entity_type='technician',
        entity_id=tech.tech_id,
        old_values=old_values,
        new_values=tech.to_dict(),
        description=f"Technician {tech.name} updated",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'Technician updated successfully',
        'technician': tech.to_dict()
    }), 200


@technicians_bp.route('/<int:tech_id>', methods=['DELETE'])
@admin_required
def delete_technician(tech_id):
    """
    Deactivate a technician (soft delete).
    """
    tech = Technician.query.get_or_404(tech_id)

    old_values = tech.to_dict()
    tech.status = 'inactive'

    # Also deactivate linked user if exists
    linked_user = User.query.filter_by(tech_id=tech_id).first()
    if linked_user:
        linked_user.status = 'inactive'

    db.session.commit()

    logger.info(f"Technician deactivated: {tech.tech_id}")
    audit_logger.log(
        action_type='technician_deactivated',
        entity_type='technician',
        entity_id=tech.tech_id,
        old_values=old_values,
        new_values={'status': 'inactive'},
        description=f"Technician {tech.name} deactivated",
        user_id=g.user_id
    )

    return jsonify({'message': 'Technician deactivated successfully'}), 200


@technicians_bp.route('/<int:tech_id>/create-user', methods=['POST'])
@admin_required
def create_user_for_technician(tech_id):
    """
    Create a user account for an existing technician.

    Request body:
        {
            "password": "Password123",
            "email": "override@example.com"  (optional, uses technician email by default)
        }
    """
    tech = Technician.query.get_or_404(tech_id)

    # Check if technician already has a user account
    existing_user = User.query.filter_by(tech_id=tech_id).first()
    if existing_user:
        return jsonify({'error': 'Technician already has a user account'}), 409

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email = data.get('email', '').strip().lower() or tech.email
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    password = data.get('password', '')
    if not password:
        return jsonify({'error': 'Password is required'}), 400

    # Validate password
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Check if user with this email exists
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'A user with this email already exists'}), 409

    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    user = User(
        email=email,
        password_hash=password_hash,
        full_name=tech.name,
        role='technician',
        tech_id=tech.tech_id,
        password_changed_at=datetime.utcnow()
    )

    db.session.add(user)
    db.session.commit()

    logger.info(f"User account created for technician: {tech.tech_id}")
    audit_logger.log(
        action_type='user_created_for_technician',
        entity_type='user',
        entity_id=user.user_id,
        new_values={'email': email, 'tech_id': tech_id},
        description=f"User account created for technician {tech.name}",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'User account created successfully',
        'user': user.to_dict()
    }), 201


@technicians_bp.route('/<int:tech_id>/link-user', methods=['POST'])
@admin_required
def link_user_to_technician(tech_id):
    """
    Link an existing user to a technician.

    Request body:
        {
            "user_id": 5
        }
    """
    tech = Technician.query.get_or_404(tech_id)

    # Check if technician already has a linked user
    existing_link = User.query.filter_by(tech_id=tech_id).first()
    if existing_link:
        return jsonify({'error': 'Technician already has a linked user account'}), 409

    data = request.get_json()
    if not data or 'user_id' not in data:
        return jsonify({'error': 'user_id is required'}), 400

    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.tech_id:
        return jsonify({'error': 'User is already linked to another technician'}), 409

    user.tech_id = tech_id

    db.session.commit()

    audit_logger.log(
        action_type='user_linked_to_technician',
        entity_type='technician',
        entity_id=tech_id,
        new_values={'user_id': user.user_id},
        description=f"User {user.email} linked to technician {tech.name}",
        user_id=g.user_id
    )

    return jsonify({
        'message': 'User linked to technician successfully',
        'technician': tech.to_dict(),
        'user': user.to_dict()
    }), 200
