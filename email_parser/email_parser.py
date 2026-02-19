#!/usr/bin/env python3
"""
Email parser daemon.

Listens to Gmail via Pub/Sub StreamingPull, parses TST and TechLink dispatch
emails, and imports jobs into the Work Tracking system.

Run as: python email_parser.py
Or via systemd: see email_parser.service
"""

import base64
import json
import logging
import os
import sys
import time

from concurrent.futures import TimeoutError as FuturesTimeoutError
from google.cloud import pubsub_v1

import config
from api_client import WorkTrackingClient
from gmail_client import GmailClient
from parsers.tst import classify_tst_subject, parse_service_order, parse_special_update
from parsers.techlink import classify_techlink_subject, parse_techlink_email

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('email_parser')


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state():
    """Load last_history_id from state file."""
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE) as f:
                data = json.load(f)
                return data.get('last_history_id')
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
    return None


def save_state(history_id):
    """Persist last_history_id to state file."""
    try:
        os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
        with open(config.STATE_FILE, 'w') as f:
            json.dump({'last_history_id': history_id}, f)
    except Exception as e:
        logger.warning(f"Could not save state: {e}")


# ---------------------------------------------------------------------------
# Email classification helpers
# ---------------------------------------------------------------------------

def get_header(gmail_msg, name):
    """Extract a header value from a Gmail API message."""
    headers = gmail_msg.get('payload', {}).get('headers', [])
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''


def get_sender_domain(gmail_msg):
    """Return lowercase sender domain from 'From' header."""
    from_hdr = get_header(gmail_msg, 'From')
    m_email = None
    import re
    # Extract email address from "Name <email>" or bare "email"
    m = re.search(r'<([^>]+)>', from_hdr)
    if m:
        m_email = m.group(1)
    else:
        m_email = from_hdr.strip()
    if '@' in m_email:
        return m_email.split('@')[1].lower()
    return ''


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_message(gmail_client, api_client, msg_id):
    """Fetch and process a single Gmail message."""
    try:
        msg = gmail_client.get_message(msg_id)
    except Exception as e:
        logger.error(f"Failed to fetch message {msg_id}: {e}")
        return

    subject = get_header(msg, 'Subject')
    sender_domain = get_sender_domain(msg)
    logger.info(f"Processing message {msg_id}: from=@{sender_domain} subject={subject!r}")

    # --- TST ---
    if config.TST_SENDER_DOMAIN in sender_domain:
        email_type, ticket, client = classify_tst_subject(subject)

        if email_type == 'service_order':
            job = parse_service_order(msg, ticket, client)
            if job:
                try:
                    result = api_client.import_tst([job])
                    logger.info(f"TST import result: {result}")
                except Exception as e:
                    logger.error(f"Failed to import TST-{ticket}: {e}")
                    gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])
                    return
            gmail_client.apply_labels(
                msg_id,
                add_label_names=[config.LABEL_TST_PROCESSED],
                remove_label_ids=['INBOX'],
            )

        elif email_type == 'special_update':
            update = parse_special_update(msg, ticket)
            if update:
                try:
                    result = api_client.import_tst([update])
                    logger.info(f"TST update result: {result}")
                except Exception as e:
                    logger.error(f"Failed to import TST update {ticket}: {e}")
                    gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])
                    return
            gmail_client.apply_labels(
                msg_id,
                add_label_names=[config.LABEL_TST_PROCESSED],
                remove_label_ids=['INBOX'],
            )

        else:
            logger.info(f"TST email not recognized as SO or SU, flagging for review: {subject!r}")
            gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])

    # --- TechLink ---
    elif config.TECHLINK_SENDER_DOMAIN in sender_domain:
        ticket = classify_techlink_subject(subject)

        if ticket:
            job = parse_techlink_email(msg, ticket)
            if job:
                try:
                    result = api_client.import_techlink([job])
                    logger.info(f"TechLink import result: {result}")
                except Exception as e:
                    logger.error(f"Failed to import TL-{ticket}: {e}")
                    gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])
                    return
            gmail_client.apply_labels(
                msg_id,
                add_label_names=[config.LABEL_TL_PROCESSED],
                remove_label_ids=['INBOX'],
            )
        else:
            logger.info(f"TechLink email not recognized as Assigned, flagging for review: {subject!r}")
            gmail_client.apply_labels(msg_id, add_label_names=[config.LABEL_REVIEW])

    else:
        logger.debug(f"Message {msg_id} from unknown sender @{sender_domain}, ignoring")


# ---------------------------------------------------------------------------
# Pub/Sub listener
# ---------------------------------------------------------------------------

def run():
    gmail_client = GmailClient()
    api_client = WorkTrackingClient()

    # Register watch (valid ~7 days; cron renew_watch.py handles renewal)
    watch_result = gmail_client.register_watch()

    # Initialize history ID
    last_history_id = load_state() or str(watch_result['historyId'])
    save_state(last_history_id)
    logger.info(f"Starting from historyId={last_history_id}")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(
        config.GCP_PROJECT, config.PUBSUB_SUBSCRIPTION
    )

    def on_pubsub_message(pubsub_msg):
        nonlocal last_history_id
        try:
            # Gmail Pub/Sub notifications are base64-encoded JSON
            data = json.loads(base64.b64decode(pubsub_msg.data).decode('utf-8'))
            history_id = str(data.get('historyId', last_history_id))
            logger.debug(f"Pub/Sub notification: historyId={history_id}")

            new_msg_ids, latest_id = gmail_client.get_new_messages(last_history_id)
            if new_msg_ids:
                logger.info(f"Found {len(new_msg_ids)} new message(s)")
            for msg_id in new_msg_ids:
                process_message(gmail_client, api_client, msg_id)

            last_history_id = latest_id
            save_state(last_history_id)

        except Exception as e:
            logger.exception(f"Error processing Pub/Sub message: {e}")
        finally:
            pubsub_msg.ack()

    logger.info(f"Listening on {subscription_path}")
    streaming_pull = subscriber.subscribe(subscription_path, callback=on_pubsub_message)

    try:
        streaming_pull.result()  # Blocks forever
    except (KeyboardInterrupt, FuturesTimeoutError):
        streaming_pull.cancel()
        streaming_pull.result()
        logger.info("Shutting down")


if __name__ == '__main__':
    run()
