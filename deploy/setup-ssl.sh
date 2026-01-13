#!/bin/bash
#
# SSL Setup Script for Work Tracking System
# Usage: sudo ./setup-ssl.sh yourdomain.com
#
set -e

DOMAIN="${1:-}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: sudo ./setup-ssl.sh yourdomain.com"
    echo "Example: sudo ./setup-ssl.sh worktracking.sleepybear.tech"
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup-ssl.sh $DOMAIN)"
    exit 1
fi

echo "=========================================="
echo "SSL Setup for ${DOMAIN}"
echo "=========================================="

# Check DNS first
echo ""
echo "[1/4] Checking DNS for ${DOMAIN}..."
SERVER_IP=$(curl -s ifconfig.me)
DNS_IP=$(dig +short ${DOMAIN} | tail -1)

echo "Server IP: ${SERVER_IP}"
echo "DNS resolves to: ${DNS_IP}"

if [ "$SERVER_IP" != "$DNS_IP" ]; then
    echo ""
    echo "WARNING: DNS does not point to this server yet!"
    echo "Please add an A record for ${DOMAIN} -> ${SERVER_IP}"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "[2/4] Installing certbot..."
apt-get update
apt-get install -y certbot python3-certbot-nginx

echo ""
echo "[3/4] Updating nginx configuration..."
sed -i "s/server_name .*;/server_name ${DOMAIN};/" /etc/nginx/sites-available/work-tracking
nginx -t
systemctl reload nginx

echo ""
echo "[4/4] Obtaining SSL certificate..."
certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos --register-unsafely-without-email --redirect

echo ""
echo "=========================================="
echo "SSL Setup Complete!"
echo "=========================================="
echo ""
echo "Your site is now available at: https://${DOMAIN}"
echo ""
echo "Certificate auto-renewal is enabled."
echo "Test renewal with: sudo certbot renew --dry-run"
echo ""
