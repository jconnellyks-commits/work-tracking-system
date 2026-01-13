#!/bin/bash
#
# Work Tracking System - Ubuntu Server Setup Script
# Run as root on a fresh Ubuntu 22.04/24.04 VM
#
set -e

echo "=========================================="
echo "Work Tracking System - Server Setup"
echo "=========================================="

# Variables - modify as needed
APP_DIR="/opt/work-tracking"
APP_USER="www-data"
DB_NAME="work_tracking_db"
DB_USER="worktracking"
REPO_URL="${1:-}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup.sh)"
    exit 1
fi

echo ""
echo "[1/7] Updating system packages..."
apt-get update
apt-get upgrade -y

echo ""
echo "[2/7] Installing required packages..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    mysql-server \
    git \
    curl

echo ""
echo "[3/7] Setting up MySQL..."
systemctl start mysql
systemctl enable mysql

# Generate random password for DB user
DB_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)

# Create database and user
mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
mysql -e "FLUSH PRIVILEGES;"

echo "Database created: ${DB_NAME}"
echo "Database user: ${DB_USER}"

echo ""
echo "[4/7] Setting up application directory..."
mkdir -p ${APP_DIR}
mkdir -p /var/log/work-tracking

# Clone repo or copy files
if [ -n "$REPO_URL" ]; then
    echo "Cloning from ${REPO_URL}..."
    git clone ${REPO_URL} ${APP_DIR}
else
    echo "No repo URL provided. Please copy your application files to ${APP_DIR}"
    echo "Or run: sudo ./setup.sh https://github.com/yourusername/work-tracking-system.git"
fi

# Set ownership
chown -R ${APP_USER}:${APP_USER} ${APP_DIR}
chown -R ${APP_USER}:${APP_USER} /var/log/work-tracking

echo ""
echo "[5/7] Setting up Python virtual environment..."
cd ${APP_DIR}
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

echo ""
echo "[6/7] Configuring application..."

# Generate secret keys
SECRET_KEY=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 32)

# Create .env file
cat > ${APP_DIR}/.env << EOF
# Flask Configuration
FLASK_APP=app.main:app
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=${SECRET_KEY}

# Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}

# JWT Configuration
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=604800

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/work-tracking/app.log

# Security
BCRYPT_LOG_ROUNDS=12
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True

# Application
APP_NAME=Work Tracking System
TIMEZONE=America/New_York
EOF

chown ${APP_USER}:${APP_USER} ${APP_DIR}/.env
chmod 600 ${APP_DIR}/.env

# Initialize database schema
if [ -f "${APP_DIR}/database/database/schema.sql" ]; then
    echo "Loading database schema..."
    mysql ${DB_NAME} < ${APP_DIR}/database/database/schema.sql
fi

# Create logs directory
mkdir -p ${APP_DIR}/logs
chown ${APP_USER}:${APP_USER} ${APP_DIR}/logs

echo ""
echo "[7/7] Configuring services..."

# Setup systemd service
cp ${APP_DIR}/deploy/app.service /etc/systemd/system/work-tracking.service
systemctl daemon-reload
systemctl enable work-tracking
systemctl start work-tracking

# Setup nginx
cp ${APP_DIR}/deploy/nginx.conf /etc/nginx/sites-available/work-tracking
ln -sf /etc/nginx/sites-available/work-tracking /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Application URL: http://$(curl -s ifconfig.me)"
echo ""
echo "Database credentials (save these!):"
echo "  Database: ${DB_NAME}"
echo "  Username: ${DB_USER}"
echo "  Password: ${DB_PASS}"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status work-tracking  # Check app status"
echo "  sudo systemctl restart work-tracking # Restart app"
echo "  sudo journalctl -u work-tracking -f  # View logs"
echo "  sudo tail -f /var/log/work-tracking/app.log"
echo ""
echo "Next steps:"
echo "  1. Create an admin user via the API or database"
echo "  2. Configure SSL with Let's Encrypt (recommended)"
echo "  3. Set up firewall rules (allow ports 80, 443, 22)"
echo ""
