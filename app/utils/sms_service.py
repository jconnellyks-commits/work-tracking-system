"""
SMS Service for sending notifications via Sangoma/Apidaze API.
"""
import re
import requests
from datetime import datetime
from flask import current_app
from app import db
from app.models import SystemSettings, SMSNotification


class SMSService:
    """Service for sending SMS messages via Apidaze API."""

    # System settings keys for SMS configuration
    SETTINGS_KEYS = {
        'enabled': 'sms_enabled',
        'api_key': 'sms_api_key',
        'api_secret': 'sms_api_secret',
        'from_number': 'sms_from_number',
        'api_endpoint': 'sms_api_endpoint',
    }

    # Default Apidaze endpoint
    DEFAULT_ENDPOINT = 'https://api.apidaze.io'

    def __init__(self):
        """Initialize SMS service with settings from database."""
        self._load_config()

    def _load_config(self):
        """Load SMS configuration from SystemSettings."""
        self.enabled = SystemSettings.get_value(self.SETTINGS_KEYS['enabled'], 'false').lower() == 'true'
        self.api_key = SystemSettings.get_value(self.SETTINGS_KEYS['api_key'], '')
        self.api_secret = SystemSettings.get_value(self.SETTINGS_KEYS['api_secret'], '')
        self.from_number = SystemSettings.get_value(self.SETTINGS_KEYS['from_number'], '')
        self.api_endpoint = SystemSettings.get_value(
            self.SETTINGS_KEYS['api_endpoint'],
            self.DEFAULT_ENDPOINT
        )

    def reload_config(self):
        """Reload configuration from database."""
        self._load_config()

    def is_configured(self):
        """Check if SMS service is properly configured."""
        return bool(
            self.enabled and
            self.api_key and
            self.api_secret and
            self.from_number
        )

    def get_config_status(self):
        """Get configuration status for admin display."""
        return {
            'enabled': self.enabled,
            'configured': self.is_configured(),
            'has_api_key': bool(self.api_key),
            'has_api_secret': bool(self.api_secret),
            'has_from_number': bool(self.from_number),
            'from_number': self.from_number[-4:] if self.from_number else None,  # Last 4 digits only
            'api_endpoint': self.api_endpoint,
        }

    @staticmethod
    def format_phone_number(phone):
        """
        Format phone number to E.164 format for Apidaze.

        Args:
            phone: Phone number in various formats

        Returns:
            Phone number in E.164 format (e.g., +15551234567)
        """
        if not phone:
            return None

        # Remove all non-numeric characters except leading +
        cleaned = re.sub(r'[^\d+]', '', phone)

        # Handle various formats
        if cleaned.startswith('+'):
            # Already has country code
            return cleaned
        elif cleaned.startswith('1') and len(cleaned) == 11:
            # US number with country code but no +
            return f'+{cleaned}'
        elif len(cleaned) == 10:
            # US number without country code
            return f'+1{cleaned}'
        else:
            # Return as-is with + prefix if not already there
            return f'+{cleaned}' if not cleaned.startswith('+') else cleaned

    def send_sms(self, to_number, message, notification_type='other', assignment_id=None, tech_id=None):
        """
        Send an SMS message via Apidaze API.

        Args:
            to_number: Destination phone number
            message: Message content (will be truncated to 160 chars)
            notification_type: Type of notification for logging
            assignment_id: Optional assignment ID for linking
            tech_id: Optional technician ID for linking

        Returns:
            dict with success status and notification record
        """
        # Format phone number
        formatted_number = self.format_phone_number(to_number)
        if not formatted_number:
            return {
                'success': False,
                'error': 'Invalid phone number',
                'notification': None
            }

        # Truncate message to 160 characters for single SMS
        truncated_message = message[:160] if len(message) > 160 else message

        # Create notification record
        notification = SMSNotification(
            notification_type=notification_type,
            assignment_id=assignment_id,
            tech_id=tech_id,
            phone_number=formatted_number,
            message_body=truncated_message,
            status='pending'
        )
        db.session.add(notification)
        db.session.flush()  # Get the ID

        # Check if service is configured
        if not self.is_configured():
            notification.status = 'failed'
            notification.error_message = 'SMS service not configured'
            db.session.commit()
            return {
                'success': False,
                'error': 'SMS service not configured',
                'notification': notification
            }

        # Send via Apidaze API
        try:
            url = f'{self.api_endpoint}/{self.api_key}/sms/send'
            payload = {
                'api_secret': self.api_secret,
                'from': self.from_number,
                'to': formatted_number,
                'body': truncated_message
            }

            response = requests.post(url, data=payload, timeout=30)
            response_data = response.json() if response.content else {}

            if response.status_code == 200 and response_data.get('ok'):
                notification.status = 'sent'
                notification.sent_at = datetime.utcnow()
                notification.provider_message_id = response_data.get('message_id')
                notification.provider_response = str(response_data)
                db.session.commit()

                return {
                    'success': True,
                    'message_id': response_data.get('message_id'),
                    'notification': notification
                }
            else:
                error_msg = response_data.get('message') or response_data.get('error') or f'HTTP {response.status_code}'
                notification.status = 'failed'
                notification.error_message = error_msg
                notification.provider_response = str(response_data)
                db.session.commit()

                return {
                    'success': False,
                    'error': error_msg,
                    'notification': notification
                }

        except requests.exceptions.Timeout:
            notification.status = 'failed'
            notification.error_message = 'Request timeout'
            db.session.commit()
            return {
                'success': False,
                'error': 'Request timeout',
                'notification': notification
            }
        except requests.exceptions.RequestException as e:
            notification.status = 'failed'
            notification.error_message = str(e)
            db.session.commit()
            return {
                'success': False,
                'error': str(e),
                'notification': notification
            }
        except Exception as e:
            notification.status = 'failed'
            notification.error_message = str(e)
            db.session.commit()
            return {
                'success': False,
                'error': str(e),
                'notification': notification
            }

    def send_job_assignment_notification(self, assignment):
        """
        Send a job assignment notification SMS.

        Args:
            assignment: JobAssignment object with related job and technician

        Returns:
            dict with success status
        """
        if not assignment.technician or not assignment.technician.phone:
            return {
                'success': False,
                'error': 'Technician has no phone number'
            }

        job = assignment.job
        if not job:
            return {
                'success': False,
                'error': 'Assignment has no associated job'
            }

        # Format the message (keep under 160 chars)
        # Format: "New job assigned: FN-12345678\nDate: 02/15\nLocation: 123 Main St...\nClient: Example Corp"
        ticket = job.ticket_number or f'Job #{job.job_id}'
        date_str = job.job_date.strftime('%m/%d') if job.job_date else 'TBD'

        # Truncate location to fit
        location = job.location or 'TBD'
        if len(location) > 30:
            location = location[:27] + '...'

        client = job.client_name or 'Unknown'
        if len(client) > 20:
            client = client[:17] + '...'

        message = f"New job assigned: {ticket}\nDate: {date_str}\nLocation: {location}\nClient: {client}"

        result = self.send_sms(
            to_number=assignment.technician.phone,
            message=message,
            notification_type='job_assignment',
            assignment_id=assignment.assignment_id,
            tech_id=assignment.tech_id
        )

        # Update assignment SMS tracking
        if result['success']:
            assignment.sms_sent = True
            assignment.sms_sent_at = datetime.utcnow()
            assignment.sms_delivery_status = 'sent'
        else:
            assignment.sms_delivery_status = 'failed'

        db.session.commit()

        return result


# Singleton instance
_sms_service = None


def get_sms_service():
    """Get or create the SMS service singleton."""
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSService()
    return _sms_service


def reload_sms_service():
    """Reload the SMS service configuration."""
    global _sms_service
    if _sms_service:
        _sms_service.reload_config()
    else:
        _sms_service = SMSService()
    return _sms_service
