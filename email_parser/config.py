"""
Configuration for the email parser service.
All settings read from environment variables.
"""

import os


def get_required(key):
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Required environment variable {key!r} is not set")
    return val


API_URL = get_required('API_URL')          # e.g. https://worktracking.sleepybear.tech/api
API_EMAIL = get_required('API_EMAIL')      # admin login email
API_PASSWORD = get_required('API_PASSWORD')

GCP_PROJECT = get_required('GCP_PROJECT')             # e.g. remoteworkstation
PUBSUB_SUBSCRIPTION = get_required('PUBSUB_SUBSCRIPTION')  # e.g. gmail-dispatch-sub
PUBSUB_TOPIC = os.environ.get('PUBSUB_TOPIC', 'gmail-dispatch-notifications')

# Gmail topic full name for watch registration
GMAIL_TOPIC = f"projects/{GCP_PROJECT}/topics/{PUBSUB_TOPIC}"

# Senders to watch
TST_SENDER_DOMAIN = os.environ.get('TST_SENDER_DOMAIN', 'techservicetoday.com')
TECHLINK_SENDER_DOMAIN = os.environ.get('TECHLINK_SENDER_DOMAIN', 'techlinksvc.net')

# Labels applied to processed emails (created automatically if missing)
LABEL_TST_PROCESSED = 'work-orders/tst/processed'
LABEL_TL_PROCESSED = 'work-orders/techlink/processed'
LABEL_REVIEW = 'work-orders/review'

# State file - tracks last historyId seen
STATE_FILE = os.environ.get('STATE_FILE', '/opt/email-parser/state.json')

# Token / credentials files
TOKEN_FILE = os.environ.get('TOKEN_FILE', '/opt/email-parser/token.json')
CREDENTIALS_FILE = os.environ.get('CREDENTIALS_FILE', '/opt/email-parser/credentials.json')

# Gmail OAuth scopes
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # read + label + archive
]
