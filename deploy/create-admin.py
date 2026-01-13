#!/usr/bin/env python3
"""
Create the first admin user for the Work Tracking System.
Run from the application directory with the virtual environment activated:
    cd /opt/work-tracking
    source venv/bin/activate
    python deploy/create-admin.py
"""
import sys
import os

# Add the app to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from getpass import getpass
from app import create_app, db, bcrypt
from app.models import User


def create_admin():
    app = create_app()

    with app.app_context():
        print("\n=== Create Admin User ===\n")

        email = input("Email: ").strip()
        if not email:
            print("Email is required")
            return

        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f"User with email {email} already exists")
            return

        full_name = input("Full name: ").strip()

        password = getpass("Password: ")
        password_confirm = getpass("Confirm password: ")

        if password != password_confirm:
            print("Passwords do not match")
            return

        if len(password) < 8:
            print("Password must be at least 8 characters")
            return

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role='admin',
            status='active'
        )

        db.session.add(user)
        db.session.commit()

        print(f"\nAdmin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Role: admin")
        print(f"  User ID: {user.user_id}")


if __name__ == '__main__':
    create_admin()
