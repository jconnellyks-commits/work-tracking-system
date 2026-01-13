"""
Authentication and authorization utilities.
Provides role-based access control (RBAC) and JWT token handling.
"""
from functools import wraps
from flask import request, jsonify, g
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt_identity,
    get_jwt,
)
from app.utils.logging import get_logger, audit_logger

logger = get_logger(__name__)

# Role hierarchy: admin > manager > technician
ROLE_HIERARCHY = {
    'admin': 3,
    'manager': 2,
    'technician': 1,
}


def get_current_user():
    """
    Get the current authenticated user from the database.

    Returns:
        User: Current user object or None
    """
    from app.models import User

    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        return User.query.get(int(user_id))
    except Exception:
        return None


def jwt_required_with_user(fn):
    """
    Decorator that verifies JWT and loads user into g.current_user.
    Also sets g.user_id for logging purposes.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from app.models import User

        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id))

            if not user:
                logger.warning(f"JWT valid but user {user_id} not found")
                return jsonify({'error': 'User not found'}), 404

            if user.status != 'active':
                logger.warning(f"Inactive user {user_id} attempted access")
                return jsonify({'error': 'Account is not active'}), 403

            g.current_user = user
            g.user_id = user.user_id

            return fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return jsonify({'error': 'Authentication required'}), 401

    return wrapper


def role_required(*allowed_roles):
    """
    Decorator to require specific roles for access.

    Args:
        *allowed_roles: Role names that are allowed (e.g., 'admin', 'manager')

    Usage:
        @role_required('admin', 'manager')
        def admin_only_route():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from app.models import User

            try:
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                user = User.query.get(int(user_id))

                if not user:
                    return jsonify({'error': 'User not found'}), 404

                if user.status != 'active':
                    return jsonify({'error': 'Account is not active'}), 403

                if user.role not in allowed_roles:
                    logger.warning(
                        f"User {user_id} with role {user.role} "
                        f"attempted to access route requiring {allowed_roles}"
                    )
                    audit_logger.log(
                        action_type='access_denied',
                        description=f"User role {user.role} not in {allowed_roles}",
                        user_id=user_id
                    )
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'required_roles': list(allowed_roles)
                    }), 403

                g.current_user = user
                g.user_id = user.user_id

                return fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"Authorization error: {str(e)}")
                return jsonify({'error': 'Authentication required'}), 401

        return wrapper
    return decorator


def admin_required(fn):
    """Shortcut decorator for admin-only routes."""
    return role_required('admin')(fn)


def manager_required(fn):
    """Shortcut decorator for manager and admin routes."""
    return role_required('admin', 'manager')(fn)


def check_permission(user, action, resource, resource_owner_id=None):
    """
    Check if a user has permission to perform an action on a resource.

    Args:
        user: User object
        action: Action to perform (view, create, update, delete)
        resource: Resource type (job, time_entry, user, etc.)
        resource_owner_id: ID of the user who owns the resource (for ownership checks)

    Returns:
        bool: True if permitted, False otherwise
    """
    if not user or user.status != 'active':
        return False

    # Admins can do everything
    if user.role == 'admin':
        return True

    # Define permission matrix
    permissions = {
        'manager': {
            'job': ['view', 'create', 'update', 'delete'],
            'time_entry': ['view', 'create', 'update', 'delete', 'verify'],
            'technician': ['view'],
            'report': ['view', 'generate'],
            'pay_period': ['view', 'close'],
            'invoice': ['view', 'create', 'update'],
        },
        'technician': {
            'job': ['view'],
            'time_entry': ['view', 'create', 'update'],
            'technician': ['view_own'],
            'report': ['view_own'],
        },
    }

    role_permissions = permissions.get(user.role, {})
    resource_permissions = role_permissions.get(resource, [])

    # Check for ownership-based permissions
    if f'{action}_own' in resource_permissions:
        if resource_owner_id and resource_owner_id == user.tech_id:
            return True

    return action in resource_permissions


def can_access_technician_data(user, tech_id):
    """
    Check if a user can access another technician's data.

    Args:
        user: Current user
        tech_id: Target technician ID

    Returns:
        bool: True if access is allowed
    """
    if not user:
        return False

    # Admins and managers can see all technicians
    if user.role in ('admin', 'manager'):
        return True

    # Technicians can only see their own data
    return user.tech_id == tech_id


def can_modify_time_entry(user, time_entry):
    """
    Check if a user can modify a specific time entry.

    Args:
        user: Current user
        time_entry: TimeEntry object

    Returns:
        bool: True if modification is allowed
    """
    if not user:
        return False

    # Admins can modify anything
    if user.role == 'admin':
        return True

    # Managers can modify any entry that's not paid
    if user.role == 'manager':
        return time_entry.status not in ('paid',)

    # Technicians can only modify their own draft/submitted entries
    if user.role == 'technician':
        if user.tech_id != time_entry.tech_id:
            return False
        return time_entry.status in ('draft', 'submitted')

    return False


def can_verify_time_entry(user, time_entry):
    """
    Check if a user can verify a time entry.

    Args:
        user: Current user
        time_entry: TimeEntry object

    Returns:
        bool: True if verification is allowed
    """
    if not user:
        return False

    # Only admins and managers can verify
    if user.role not in ('admin', 'manager'):
        return False

    # Can only verify submitted entries
    return time_entry.status == 'submitted'


class RateLimiter:
    """
    Simple in-memory rate limiter for authentication endpoints.
    For production, use Redis-based rate limiting.
    """

    def __init__(self):
        self._attempts = {}

    def is_rate_limited(self, key, max_attempts=5, window_seconds=300):
        """
        Check if an action is rate limited.

        Args:
            key: Identifier (e.g., IP address or username)
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds

        Returns:
            bool: True if rate limited
        """
        import time

        current_time = time.time()
        if key not in self._attempts:
            self._attempts[key] = []

        # Clean old attempts
        self._attempts[key] = [
            t for t in self._attempts[key]
            if current_time - t < window_seconds
        ]

        return len(self._attempts[key]) >= max_attempts

    def record_attempt(self, key):
        """Record an attempt for rate limiting."""
        import time

        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(time.time())

    def reset(self, key):
        """Reset attempts for a key (e.g., after successful login)."""
        if key in self._attempts:
            del self._attempts[key]


# Global rate limiter instance
rate_limiter = RateLimiter()


def validate_password_strength(password):
    """
    Validate password meets security requirements.

    Args:
        password: Password string to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

    return True, None
