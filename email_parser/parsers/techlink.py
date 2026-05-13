"""
Parser for TechLink Services dispatch emails.

Handles two email types:
1. "TechLink Work Order #NNNNN Assigned" — creates new job
2. "TechLink Install Reminder: WO #NNNNN, ..." — updates schedule on existing job
"""

import base64
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

_RE_SUBJECT_ASSIGNED = re.compile(r'TechLink\s+Work\s+Order\s+#(\d+)\s+Assigned', re.IGNORECASE)
_RE_SUBJECT_REMINDER = re.compile(r'TechLink\s+Install\s+Reminder:\s*WO\s+#(\d+)', re.IGNORECASE)

_RE_SCHEDULED = re.compile(r'Scheduled\s+Install\s+Time:\s*(.+)', re.IGNORECASE)
_RE_SUMMARY = re.compile(r'Summary:\s*(.+)', re.IGNORECASE)
_RE_CLIENT_PO = re.compile(r'Client\s+PO:\s*(.+)', re.IGNORECASE)
_RE_PHONE = re.compile(r'^\s*(?:1\s*)?[\(\s]*\d{3}[\)\s\-]*\d{3}[\s\-]*\d{4}\s*$')
_RE_PORTAL_URL = re.compile(r'http[s]?://portal\.techlinksvc\.net/admin/\?mod=workorders&act=edit&id=(\d+)')

PORTAL_URL_TEMPLATE = 'https://portal.techlinksvc.net/admin/?mod=workorders&act=edit&id={}'


def classify_techlink_subject(subject):
    """Returns (email_type, ticket_number) or (None, None).
    email_type is 'assigned' or 'reminder'."""
    m = _RE_SUBJECT_ASSIGNED.search(subject)
    if m:
        return 'assigned', m.group(1)
    m = _RE_SUBJECT_REMINDER.search(subject)
    if m:
        return 'reminder', m.group(1)
    return None, None


def _get_text_body(gmail_msg):
    """Extract decoded plain-text body from a Gmail API full message."""
    payload = gmail_msg.get('payload', {})

    def _decode_data(data):
        if not data:
            return ''
        try:
            return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
        except Exception:
            return ''

    def _find_text_plain(part):
        mime = part.get('mimeType', '')
        if mime == 'text/plain':
            return _decode_data(part.get('body', {}).get('data', ''))
        for sub in part.get('parts', []):
            result = _find_text_plain(sub)
            if result:
                return result
        return ''

    return _find_text_plain(payload)


def _parse_techlink_date(date_str):
    """
    Parse TechLink date strings.
    Handles: 'MAY 14, 2026 12:30 PM (CDT)', 'Feb 20, 2026 9:30 AM', etc.
    Returns (job_date_iso, scheduled_start_time_hhmm) or (None, None).
    """
    date_str = date_str.strip()
    # Strip timezone in parens like (CDT), (CST), (EST)
    date_str = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', date_str).strip()

    for fmt in [
        '%b %d, %Y %I:%M %p',
        '%b %d, %Y %I:%M%p',
        '%B %d, %Y %I:%M %p',
        '%B %d, %Y %I:%M%p',
        '%m/%d/%Y %I:%M %p',
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')
        except ValueError:
            continue
    logger.warning(f"Could not parse TechLink date: {date_str!r}")
    return None, None


def parse_techlink_email(gmail_msg, ticket_number):
    """
    Parse a TechLink Assigned email.
    Returns a job dict or None on failure.
    """
    body = _get_text_body(gmail_msg)
    if not body:
        logger.warning(f"TechLink WO#{ticket_number}: empty body")
        return None

    lines = [l.rstrip() for l in body.splitlines()]

    # Find SITE INFORMATION block
    client_name = ''
    address_parts = []
    contact_name = ''
    contact_phone = ''

    site_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper() == 'SITE INFORMATION':
            site_idx = i
            break

    if site_idx is not None:
        i = site_idx + 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines):
            client_name = lines[i].strip().rstrip(':')
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and lines[i].strip().rstrip(':') == client_name:
                i += 1

            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                if line.upper().startswith('WORK ORDER'):
                    break
                if _RE_PHONE.match(line):
                    contact_phone = line.strip()
                    i += 1
                    continue
                if address_parts and not re.search(r'\d', line) and ',' not in line:
                    contact_name = line
                    i += 1
                    continue
                address_parts.append(line)
                i += 1

    # Scheduled install time (may not be present in Assigned emails)
    job_date = None
    scheduled_start_time = None
    m = _RE_SCHEDULED.search(body)
    if m:
        job_date, scheduled_start_time = _parse_techlink_date(m.group(1).strip())

    # Description: prefer Summary, fall back to Client PO
    description = ''
    m = _RE_SUMMARY.search(body)
    if m:
        description = m.group(1).strip()
    if not description:
        m = _RE_CLIENT_PO.search(body)
        if m:
            description = m.group(1).strip()

    # Build address string
    address = ', '.join(p for p in address_parts if p)
    # Build contact string
    contact_parts = [p for p in [contact_name, contact_phone] if p]
    contact = ', '.join(contact_parts)

    # External URL — construct from ticket number
    external_url = PORTAL_URL_TEMPLATE.format(ticket_number)

    result = {
        'ticket_number': ticket_number,
        'client_name': client_name or 'TechLink',
        'job_date': job_date,
        'scheduled_start_time': scheduled_start_time,
        'description': description,
        'address': address,
        'contact': contact,
        'status': 'assigned',
        'external_url': external_url,
    }
    logger.info(f"Parsed TechLink WO#{ticket_number} / {client_name} / {job_date}")
    return result


def parse_techlink_reminder(gmail_msg, ticket_number):
    """
    Parse a TechLink Install Reminder email.
    Returns a dict with schedule update fields or None on failure.
    """
    body = _get_text_body(gmail_msg)
    if not body:
        logger.warning(f"TechLink Reminder WO#{ticket_number}: empty body")
        return None

    # Extract scheduled install time
    job_date = None
    scheduled_start_time = None
    m = _RE_SCHEDULED.search(body)
    if m:
        job_date, scheduled_start_time = _parse_techlink_date(m.group(1).strip())

    # Extract portal URL from body (or construct it)
    external_url = PORTAL_URL_TEMPLATE.format(ticket_number)
    m = _RE_PORTAL_URL.search(body)
    if m:
        external_url = f"https://portal.techlinksvc.net/admin/?mod=workorders&act=edit&id={m.group(1)}"

    # Also grab updated summary if present
    description = None
    m = _RE_SUMMARY.search(body)
    if m:
        description = m.group(1).strip()

    result = {
        'ticket_number': ticket_number,
        'job_date': job_date,
        'scheduled_start_time': scheduled_start_time,
        'external_url': external_url,
        'description': description,
    }
    logger.info(f"Parsed TechLink Reminder WO#{ticket_number} / {job_date} {scheduled_start_time}")
    return result
