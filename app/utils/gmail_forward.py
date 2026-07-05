import base64
import email
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GMAIL_TOKEN_FILE = os.environ.get('GMAIL_TOKEN_FILE', '/opt/email-parser/token.json')
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
]

_service = None


def _get_service():
    global _service
    if _service is not None:
        return _service

    if not os.path.exists(GMAIL_TOKEN_FILE):
        logger.warning(f"Gmail token file not found: {GMAIL_TOKEN_FILE}")
        return None

    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.error("Gmail credentials invalid and no refresh token available")
            return None

    _service = build('gmail', 'v1', credentials=creds)
    return _service


def is_available():
    return os.path.exists(GMAIL_TOKEN_FILE)


def forward_email(gmail_message_id, to_email):
    service = _get_service()
    if not service:
        return {'success': False, 'error': 'Gmail service not available'}

    try:
        original = service.users().messages().get(
            userId='me', id=gmail_message_id, format='raw'
        ).execute()

        raw_bytes = base64.urlsafe_b64decode(original['raw'])
        orig_msg = email.message_from_bytes(raw_bytes)

        orig_subject = orig_msg.get('Subject', '(no subject)')
        fwd_subject = orig_subject if orig_subject.startswith('Fwd:') else f"Fwd: {orig_subject}"

        fwd_msg = MIMEMultipart('mixed')
        fwd_msg['To'] = to_email
        fwd_msg['Subject'] = fwd_subject

        body_text = ''
        attachments = []

        if orig_msg.is_multipart():
            for part in orig_msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))

                if 'attachment' in content_disposition:
                    attachments.append(part)
                elif content_type == 'text/plain' and not body_text:
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
                elif content_type == 'text/html' and not body_text:
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
        else:
            body_text = orig_msg.get_payload(decode=True).decode('utf-8', errors='replace')

        fwd_msg.attach(MIMEText(body_text, 'plain'))

        for att in attachments:
            fwd_msg.attach(att)

        encoded = base64.urlsafe_b64encode(fwd_msg.as_bytes()).decode('ascii')
        result = service.users().messages().send(
            userId='me',
            body={'raw': encoded}
        ).execute()

        logger.info(f"Forwarded email {gmail_message_id} to {to_email}, new msg id: {result['id']}")
        return {'success': True, 'message_id': result['id']}

    except Exception as e:
        logger.error(f"Failed to forward email {gmail_message_id} to {to_email}: {e}")
        return {'success': False, 'error': str(e)}
