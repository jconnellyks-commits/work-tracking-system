"""
Work Tracking API client: authenticate once, auto-refresh JWT, import jobs.
"""

import logging
import time

import requests

import config

logger = logging.getLogger(__name__)


class WorkTrackingClient:
    def __init__(self):
        self._access_token = None
        self._refresh_token = None
        self._token_expiry = 0
        self._login()

    def _login(self):
        resp = requests.post(
            f"{config.API_URL}/auth/login",
            json={'email': config.API_EMAIL, 'password': config.API_PASSWORD},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data['access_token']
        self._refresh_token = data.get('refresh_token')
        # Assume 15-minute access token; refresh 2 min before expiry
        self._token_expiry = time.time() + (15 * 60) - 120
        logger.info("Logged in to Work Tracking API")

    def _refresh(self):
        if not self._refresh_token:
            self._login()
            return
        try:
            resp = requests.post(
                f"{config.API_URL}/auth/refresh",
                json={'refresh_token': self._refresh_token},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data['access_token']
            self._token_expiry = time.time() + (15 * 60) - 120
        except Exception:
            logger.warning("Token refresh failed, re-logging in")
            self._login()

    @property
    def _headers(self):
        if time.time() >= self._token_expiry:
            self._refresh()
        return {'Authorization': f'Bearer {self._access_token}'}

    def _post(self, path, payload):
        resp = requests.post(
            f"{config.API_URL}{path}",
            json=payload,
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def import_tst(self, jobs):
        """POST /api/imports/tst — create/update TST jobs."""
        return self._post('/imports/tst', jobs)

    def import_techlink(self, jobs):
        """POST /api/imports/techlink — create/update TechLink jobs."""
        return self._post('/imports/techlink', jobs)
