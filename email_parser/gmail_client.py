"""
Gmail API client: watch registration, history polling, message fetch, labeling.
"""

import json
import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

logger = logging.getLogger(__name__)


class GmailClient:
    def __init__(self):
        self.service = self._authenticate()
        self._label_cache = {}  # name -> id

    def _authenticate(self):
        creds = None
        if os.path.exists(config.TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.GMAIL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.refresh_token:
                # Refresh using embedded client_id/secret (works for ADC and InstalledApp tokens)
                creds.refresh(Request())
            elif os.path.exists(config.CREDENTIALS_FILE):
                # Fall back to interactive OAuth flow (first-time setup without ADC)
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.CREDENTIALS_FILE, config.GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            else:
                raise RuntimeError(
                    "No valid credentials. Run auth_setup.py or set TOKEN_FILE to ADC credentials."
                )
            with open(config.TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())

        # Gmail API requires a quota project when using ADC user credentials.
        # Explicitly set it so the x-goog-user-project header is sent.
        if not getattr(creds, 'quota_project_id', None):
            creds = creds.with_quota_project(config.GCP_PROJECT)

        return build('gmail', 'v1', credentials=creds)

    def register_watch(self):
        """Register Gmail push notifications via Pub/Sub. Valid for ~7 days."""
        body = {
            'labelIds': ['INBOX'],
            'topicName': config.GMAIL_TOPIC,
        }
        result = self.service.users().watch(userId='me', body=body).execute()
        logger.info(f"Watch registered: historyId={result['historyId']}, expiration={result['expiration']}")
        return result

    def get_new_messages(self, start_history_id):
        """
        Return list of message IDs added since start_history_id.
        Also returns the latest historyId seen (for next call).
        """
        new_msg_ids = []
        latest_history_id = start_history_id

        try:
            response = self.service.users().history().list(
                userId='me',
                startHistoryId=start_history_id,
                historyTypes=['messageAdded'],
                labelId='INBOX',
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                # historyId too old - reset by getting current historyId
                logger.warning("historyId expired, resetting to current")
                profile = self.service.users().getProfile(userId='me').execute()
                return [], str(profile['historyId'])
            raise

        histories = response.get('history', [])
        for history in histories:
            latest_history_id = str(history['id'])
            for msg_added in history.get('messagesAdded', []):
                new_msg_ids.append(msg_added['message']['id'])

        # Handle pagination
        next_page = response.get('nextPageToken')
        while next_page:
            response = self.service.users().history().list(
                userId='me',
                startHistoryId=start_history_id,
                historyTypes=['messageAdded'],
                labelId='INBOX',
                pageToken=next_page,
            ).execute()
            for history in response.get('history', []):
                latest_history_id = str(history['id'])
                for msg_added in history.get('messagesAdded', []):
                    new_msg_ids.append(msg_added['message']['id'])
            next_page = response.get('nextPageToken')

        return new_msg_ids, latest_history_id

    def get_message(self, msg_id):
        """Fetch a full message with payload."""
        return self.service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full',
        ).execute()

    def get_or_create_label(self, label_name):
        """Get label ID by name, creating it if it doesn't exist."""
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # Fetch all labels
        result = self.service.users().labels().list(userId='me').execute()
        for label in result.get('labels', []):
            self._label_cache[label['name']] = label['id']

        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # Create it (nested labels use '/' separator)
        new_label = self.service.users().labels().create(
            userId='me',
            body={
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show',
            }
        ).execute()
        self._label_cache[label_name] = new_label['id']
        logger.info(f"Created Gmail label: {label_name}")
        return new_label['id']

    def apply_labels(self, msg_id, add_label_names=None, remove_label_ids=None):
        """Add/remove labels. Archives by removing INBOX."""
        add_label_ids = [self.get_or_create_label(n) for n in (add_label_names or [])]
        body = {
            'addLabelIds': add_label_ids,
            'removeLabelIds': remove_label_ids or [],
        }
        self.service.users().messages().modify(
            userId='me', id=msg_id, body=body
        ).execute()
