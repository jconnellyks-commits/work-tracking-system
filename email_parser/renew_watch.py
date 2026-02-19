#!/usr/bin/env python3
"""
Renew Gmail push watch.
Gmail watches expire after ~7 days. Run this daily via cron:

  0 6 * * * /opt/email-parser/venv/bin/python /opt/email-parser/renew_watch.py >> /var/log/email-parser-watch.log 2>&1
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger('renew_watch')

from gmail_client import GmailClient

if __name__ == '__main__':
    client = GmailClient()
    result = client.register_watch()
    logger.info(f"Watch renewed: historyId={result['historyId']}, expiration={result['expiration']}")
