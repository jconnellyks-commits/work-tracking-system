"""
Parser for Tech Service Today (TST) dispatch emails.

Two email types:
  - Service Order: subject "TST NNNNN for <client> Service Order"
  - Special Update: subject "TST NNNNN for <client> Special Update"

The Service Order body is base64-encoded text/plain.
The Special Update body is quoted-printable text/plain.
"""

import base64
import logging
import quopri
import re
from datetime import datetime
from email import message_from_bytes, message_from_string
from email.policy import default as email_default

logger = logging.getLogger(__name__)

# Subject patterns
_RE_SERVICE_ORDER = re.compile(
    r'TST\s+(\d+)\s+for\s+(.+?)\s+Service\s+Order', re.IGNORECASE
)
_RE_SPECIAL_UPDATE = re.compile(
    r'TST\s+(\d+)\s+for\s+(.+?)\s+Special\s+Update', re.IGNORECASE
)

# Body patterns
_RE_BODY_CLIENT = re.compile(
    r'TST\s*#\s*(\d+)\s+for\s+(.+)', re.IGNORECASE
)
_RE_APPOINTMENT = re.compile(
    r'Appointment\s+Date:\s*(.+)', re.IGNORECASE
)
_RE_DESCRIPTION = re.compile(
    r'Description:\s*(.+)', re.IGNORECASE
)
# Special Update rate patterns
_RE_TRIP_CHARGE = re.compile(
    r'trip\s+charge\s+for\s+this\s+incident\s+only\s*\((\d+(?:\.\d+)?)\)', re.IGNORECASE
)
_RE_LABOR_RATE = re.compile(
    r'onsite\s+labor\s+rate\s*\((\d+(?:\.\d+)?)\)', re.IGNORECASE
)


def _get_text_body(gmail_msg):
    """
    Extract decoded plain-text body from a Gmail API full message.
    Gmail API returns parts with body.data as base64url-encoded.
    """
    payload = gmail_msg.get('payload', {})

    def _decode_data(data):
        """base64url decode Gmail payload data."""
        if not data:
            return ''
        padded = data + '=='
        try:
            return base64.urlsafe_b64decode(padded).decode('utf-8', errors='replace')
        except Exception:
            return ''

    def _find_text_plain(part):
        mime = part.get('mimeType', '')
        if mime == 'text/plain':
            data = part.get('body', {}).get('data', '')
            return _decode_data(data)
        for sub in part.get('parts', []):
            result = _find_text_plain(sub)
            if result:
                return result
        return ''

    return _find_text_plain(payload)


def _parse_tst_date(date_str):
    """
    Parse TST appointment date strings like '2/27/2026 9:30:00 AM'.
    Returns (job_date_iso, scheduled_start_time_hhmm) or (None, None).
    """
    date_str = date_str.strip()
    for fmt in [
        '%m/%d/%Y %I:%M:%S %p',
        '%m/%d/%Y %I:%M %p',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M',
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')
        except ValueError:
            continue
    logger.warning(f"Could not parse TST date: {date_str!r}")
    return None, None


def classify_tst_subject(subject):
    """
    Returns ('service_order', ticket, client), ('special_update', ticket, client),
    or (None, None, None) if not a TST email.
    """
    m = _RE_SERVICE_ORDER.search(subject)
    if m:
        return 'service_order', m.group(1), m.group(2).strip()
    m = _RE_SPECIAL_UPDATE.search(subject)
    if m:
        return 'special_update', m.group(1), m.group(2).strip()
    return None, None, None


def parse_service_order(gmail_msg, subject_ticket, subject_client):
    """
    Parse a TST Service Order email.
    Returns a job dict or None on failure.
    """
    body = _get_text_body(gmail_msg)
    if not body:
        logger.warning(f"TST Service Order TST-{subject_ticket}: empty body")
        return None

    # Extract client from body (more reliable than subject for site name)
    client = subject_client
    m = _RE_BODY_CLIENT.search(body)
    if m:
        client = m.group(2).strip()

    # Appointment date
    job_date = None
    scheduled_start_time = None
    m = _RE_APPOINTMENT.search(body)
    if m:
        job_date, scheduled_start_time = _parse_tst_date(m.group(1))

    # Description
    description = ''
    m = _RE_DESCRIPTION.search(body)
    if m:
        description = m.group(1).strip()

    result = {
        'ticket_number': subject_ticket,
        'client_name': client,
        'job_date': job_date,
        'scheduled_start_time': scheduled_start_time,
        'description': description,
        'billing_rate': None,
        'trip_charge': None,
        'status': 'assigned',
    }
    logger.info(f"Parsed TST Service Order: TST-{subject_ticket} / {client} / {job_date}")
    return result


def parse_special_update(gmail_msg, subject_ticket):
    """
    Parse a TST Special Update email.
    Returns a partial job dict with rate/trip info, for merging into an existing job.
    """
    body = _get_text_body(gmail_msg)
    if not body:
        logger.warning(f"TST Special Update TST-{subject_ticket}: empty body")
        return None

    billing_rate = None
    trip_charge = None

    m = _RE_TRIP_CHARGE.search(body)
    if m:
        trip_charge = float(m.group(1))

    m = _RE_LABOR_RATE.search(body)
    if m:
        billing_rate = float(m.group(1))

    result = {
        'ticket_number': subject_ticket,
        'billing_rate': billing_rate,
        'trip_charge': trip_charge,
        'status': 'assigned',
    }
    logger.info(f"Parsed TST Special Update: TST-{subject_ticket} / rate={billing_rate} / trip={trip_charge}")
    return result
