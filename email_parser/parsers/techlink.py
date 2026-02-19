"""
Parser for TechLink Services dispatch emails.

Email type: subject "TechLink Work Order #NNNNN Assigned"
Body is text/plain (quoted-printable).

Body structure:
  Hello SleepyBear LLC (jeremiah connelly),

  Work Order #NNNNN from TechLink Services has been assigned ...

  SITE INFORMATION
  <Client Name>:
  <Client Name (repeated)>
  <Address Line 1>
  <City, State ZIP>
  <Contact Name>
  <Phone Number>

  WORK ORDER DETAILS
  Client PO: <description>
  Scheduled Install Time: <date/time>

  Summary: <description>
"""

import base64
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

_RE_SUBJECT = re.compile(r'TechLink\s+Work\s+Order\s+#(\d+)\s+Assigned', re.IGNORECASE)

_RE_SCHEDULED = re.compile(r'Scheduled\s+Install\s+Time:\s*(.+)', re.IGNORECASE)
_RE_SUMMARY = re.compile(r'Summary:\s*(.+)', re.IGNORECASE)
_RE_CLIENT_PO = re.compile(r'Client\s+PO:\s*(.+)', re.IGNORECASE)
_RE_PHONE = re.compile(r'^\s*(\d{10})\s*$')  # bare 10-digit phone line


def classify_techlink_subject(subject):
    """Returns ticket number string or None."""
    m = _RE_SUBJECT.search(subject)
    return m.group(1) if m else None


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
    Parse TechLink date strings like 'Feb 20, 2026 9:30 AM'.
    Returns (job_date_iso, scheduled_start_time_hhmm) or (None, None).
    """
    date_str = date_str.strip()
    for fmt in [
        '%b %d, %Y %I:%M %p',
        '%b %d, %Y %I:%M%p',
        '%B %d, %Y %I:%M %p',
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
        # Next non-empty line is "<ClientName>:" or "<ClientName>"
        i = site_idx + 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines):
            # Client name — strip trailing colon
            client_name = lines[i].strip().rstrip(':')
            i += 1
            # Next might be client name repeated — skip if same
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and lines[i].strip().rstrip(':') == client_name:
                i += 1

            # Collect address lines until we hit a blank line, WORK ORDER DETAILS, or phone
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                if line.upper().startswith('WORK ORDER'):
                    break
                # Phone number line
                phone_m = _RE_PHONE.match(line)
                if phone_m:
                    contact_phone = phone_m.group(1)
                    i += 1
                    continue
                # Contact name (non-empty, non-address, comes after address)
                # Heuristic: if it looks like a name (no digits, not a state/zip pattern)
                if address_parts and not re.search(r'\d', line) and ',' not in line:
                    contact_name = line
                    i += 1
                    continue
                address_parts.append(line)
                i += 1

    # Scheduled install time
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

    result = {
        'ticket_number': ticket_number,
        'client_name': client_name or 'TechLink',
        'job_date': job_date,
        'scheduled_start_time': scheduled_start_time,
        'description': description,
        'address': address,
        'contact': contact,
        'status': 'assigned',
    }
    logger.info(f"Parsed TechLink WO#{ticket_number} / {client_name} / {job_date}")
    return result
