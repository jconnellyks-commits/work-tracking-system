"""
SMS Service for sending notifications via VoIP Innovations SOAP API.
"""
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import current_app
from app import db
from app.models import SystemSettings, SMSNotification


class SMSService:
    """Service for sending SMS messages via VoIP Innovations SOAP API."""

    # System settings keys for SMS configuration
    SETTINGS_KEYS = {
        'enabled': 'sms_enabled',
        'api_key': 'sms_api_key',        # VoIP Innovations API username
        'api_secret': 'sms_api_secret',  # VoIP Innovations API password
        'from_number': 'sms_from_number',
        'api_endpoint': 'sms_api_endpoint',
    }

    # Default VoIP Innovations endpoint
    DEFAULT_ENDPOINT = 'https://backoffice.voipinnovations.com/Services/APIService.asmx'

    # SOAP namespace
    SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
    VI_NS = 'http://tempuri.org/'

    def __init__(self):
        """Initialize SMS service with settings from database."""
        self._load_config()

    def _load_config(self):
        """Load SMS configuration from SystemSettings."""
        self.enabled = SystemSettings.get_value(self.SETTINGS_KEYS['enabled'], 'false').lower() == 'true'
        self.api_key = SystemSettings.get_value(self.SETTINGS_KEYS['api_key'], '')  # Username
        self.api_secret = SystemSettings.get_value(self.SETTINGS_KEYS['api_secret'], '')  # Password
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
            'from_number': self.from_number[-4:] if self.from_number else None,
            'api_endpoint': self.api_endpoint,
        }

    @staticmethod
    def format_phone_number(phone, include_country_code=True):
        """
        Format phone number.

        Args:
            phone: Phone number in various formats
            include_country_code: If True, return E.164 format (+1...), else just 10 digits

        Returns:
            Formatted phone number
        """
        if not phone:
            return None

        # Remove all non-numeric characters
        cleaned = re.sub(r'[^\d]', '', phone)

        # Handle various formats - normalize to 10 digits for US
        if cleaned.startswith('1') and len(cleaned) == 11:
            cleaned = cleaned[1:]  # Remove leading 1

        if len(cleaned) != 10:
            # Not a valid US number, return as-is
            if include_country_code:
                return f'+1{cleaned}' if len(cleaned) == 10 else f'+{cleaned}'
            return cleaned

        if include_country_code:
            return f'+1{cleaned}'
        return cleaned

    def _build_soap_envelope(self, sender, recipient, message):
        """
        Build SOAP XML envelope for SendSMSWithDLR method (with delivery reports).

        Args:
            sender: Source DID (10 digits)
            recipient: Destination number (10 digits)
            message: SMS message text

        Returns:
            XML string
        """
        return f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <SendSMSWithDLR xmlns="http://tempuri.org/">
      <login>{self.api_key}</login>
      <secret>{self.api_secret}</secret>
      <sender>{sender}</sender>
      <recipient>{recipient}</recipient>
      <message>{message}</message>
    </SendSMSWithDLR>
  </soap:Body>
</soap:Envelope>'''

    def _parse_soap_response(self, response_text):
        """
        Parse SOAP response from VoIP Innovations.

        Args:
            response_text: XML response string

        Returns:
            dict with success status and details
        """
        try:
            # Parse XML
            root = ET.fromstring(response_text)

            # Check for SOAP Fault first
            fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
            if fault is not None:
                fault_string = fault.find('faultstring')
                error_msg = fault_string.text if fault_string is not None else 'SOAP Fault'
                return {'success': False, 'error': error_msg}

            # Find the SendSMSWithDLRResult element - VoIP Innovations returns nested structure
            # <SendSMSWithDLRResult><responseCode>100</responseCode><responseMessage>Success</responseMessage>...</SendSMSWithDLRResult>
            result = root.find('.//{http://tempuri.org/}SendSMSWithDLRResult')
            if result is None:
                result = root.find('.//SendSMSWithDLRResult')
            if result is None:
                # Fall back to SendSMSResult for compatibility
                result = root.find('.//{http://tempuri.org/}SendSMSResult')
            if result is None:
                result = root.find('.//SendSMSResult')

            if result is not None:
                # Check for nested responseCode and responseMessage
                response_code = result.find('.//{http://tempuri.org/}responseCode')
                if response_code is None:
                    response_code = result.find('.//responseCode')

                response_message = result.find('.//{http://tempuri.org/}responseMessage')
                if response_message is None:
                    response_message = result.find('.//responseMessage')

                # Get the status from MsgDetails if available
                status_elem = result.find('.//{http://tempuri.org/}status')
                if status_elem is None:
                    status_elem = result.find('.//status')

                # Get UUID if available
                uuid_elem = result.find('.//{http://tempuri.org/}uuid')
                if uuid_elem is None:
                    uuid_elem = result.find('.//uuid')

                code = response_code.text if response_code is not None else ''
                message = response_message.text if response_message is not None else ''
                status = status_elem.text if status_elem is not None else ''
                uuid = uuid_elem.text if uuid_elem is not None else ''

                # Success if responseCode is 100 or status is SENT
                if code == '100' or status.upper() == 'SENT' or message.lower() == 'success':
                    return {
                        'success': True,
                        'message': message,
                        'uuid': uuid,
                        'response_code': code
                    }
                else:
                    return {
                        'success': False,
                        'error': message or f'Response code: {code}',
                        'response_code': code
                    }

            # If we can't parse the result, return the raw response
            return {'success': False, 'error': f'Unable to parse response: {response_text[:200]}'}

        except ET.ParseError as e:
            return {'success': False, 'error': f'XML parse error: {str(e)}'}

    def send_sms(self, to_number, message, notification_type='other', assignment_id=None, tech_id=None, bypass_opt_in_check=False):
        """
        Send an SMS message via VoIP Innovations SOAP API.

        Args:
            to_number: Destination phone number
            message: Message content (will be truncated to 160 chars)
            notification_type: Type of notification for logging
            assignment_id: Optional assignment ID for linking
            tech_id: Optional technician ID for linking

        Returns:
            dict with success status and notification record
        """
        # Check opt-in status unless bypassed (e.g. for STOP confirmation replies)
        if not bypass_opt_in_check:
            from app.models import Technician
            tech_check = None
            if tech_id:
                tech_check = Technician.query.get(tech_id)
            else:
                # Normalize the destination number and look up by phone
                lookup_number = re.sub(r'[^\d]', '', to_number)
                if lookup_number.startswith('1') and len(lookup_number) == 11:
                    lookup_number = lookup_number[1:]
                for t in Technician.query.all():
                    if t.phone and re.sub(r'[^\d]', '', t.phone)[-10:] == lookup_number[-10:]:
                        tech_check = t
                        break
            if tech_check and not tech_check.sms_opted_in:
                return {
                    'success': False,
                    'error': 'Technician has opted out of SMS',
                    'notification': None
                }

        # Format phone numbers (10 digits only for VoIP Innovations)
        formatted_to = self.format_phone_number(to_number, include_country_code=False)
        formatted_from = self.format_phone_number(self.from_number, include_country_code=False)

        if not formatted_to:
            return {
                'success': False,
                'error': 'Invalid destination phone number',
                'notification': None
            }

        if not formatted_from:
            return {
                'success': False,
                'error': 'Invalid from phone number',
                'notification': None
            }

        # Truncate message to 160 characters for single SMS
        truncated_message = message[:160] if len(message) > 160 else message

        # Escape XML special characters in message
        escaped_message = (truncated_message
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

        # Create notification record
        notification = SMSNotification(
            notification_type=notification_type,
            assignment_id=assignment_id,
            tech_id=tech_id,
            phone_number=f'+1{formatted_to}',  # Store in E.164 format
            message_body=truncated_message,
            status='pending'
        )
        db.session.add(notification)
        db.session.flush()

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

        # Build and send SOAP request
        try:
            soap_body = self._build_soap_envelope(formatted_from, formatted_to, escaped_message)

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '"http://tempuri.org/SendSMSWithDLR"'
            }

            response = requests.post(
                self.api_endpoint,
                data=soap_body.encode('utf-8'),
                headers=headers,
                timeout=30
            )

            # Log the raw response for debugging
            response_text = response.text

            # Parse response
            result = self._parse_soap_response(response_text)

            if result['success']:
                notification.status = 'sent'
                notification.sent_at = datetime.utcnow()
                notification.provider_message_id = result.get('uuid')
                notification.provider_response = response_text[:500]
                db.session.commit()

                return {
                    'success': True,
                    'message_id': result.get('uuid'),
                    'notification': notification
                }
            else:
                notification.status = 'failed'
                notification.error_message = result.get('error', 'Unknown error')
                notification.provider_response = response_text[:500]
                db.session.commit()

                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
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
        ticket = job.ticket_number or f'Job #{job.job_id}'
        date_str = job.job_date.strftime('%m/%d') if job.job_date else 'TBD'

        # Append start time if available
        if job.scheduled_start_time:
            start_str = job.scheduled_start_time.strftime('%I:%M %p').lstrip('0')
            date_str = f"{date_str} at {start_str}"

        client = job.client_name or 'Unknown'
        if len(client) > 20:
            client = client[:17] + '...'

        if job.external_url:
            # Include platform link; omit location to stay under 160 chars
            message = f"New job assigned: {ticket}\nDate: {date_str}\nClient: {client}\n{job.external_url}"
        else:
            location = job.location or 'TBD'
            if len(location) > 25:
                location = location[:22] + '...'
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


    def send_availability_request(self, assignment):
        """
        Send an availability request SMS for a job.

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

        ticket = job.ticket_number or f'Job #{job.job_id}'
        date_str = job.job_date.strftime('%m/%d') if job.job_date else 'TBD'

        message = (
            f"SleepyBear LLC: Are you available for {ticket} on {date_str}? "
            f"Reply Y or N. STOP to opt out."
        )

        result = self.send_sms(
            to_number=assignment.technician.phone,
            message=message,
            notification_type='invitation',
            assignment_id=assignment.assignment_id,
            tech_id=assignment.tech_id
        )

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
