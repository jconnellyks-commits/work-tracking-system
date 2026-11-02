#!/usr/bin/env python3
"""
Text the admin when the email parser stops working.

The parser crash-looped for a month (Sep 30 - Nov 1, 2026) without anyone
noticing: the Gmail token was revoked by a "log out of all devices", and the
long silence then let Pub/Sub delete the subscription too. This checks for
the failure shapes seen so far and sends an SMS through the app's own SMS
service.

Run every 15 minutes as www-data (the app's user, so it can read the app's
.env and never leaves root-owned files behind):

  */15 * * * * cd /opt/work-tracking && /opt/work-tracking/venv/bin/python scripts/email_parser_watchdog.py >> /var/tmp/email_parser_watchdog.log 2>&1

Pass --dry-run to print what would be sent without sending it.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVICE = 'email-parser'
RENEW_LOG = '/opt/email-parser/renew_watch.log'
STATE_FILE = '/var/tmp/email_parser_watchdog.json'
ADMIN_EMAIL = 'jconnellyks@gmail.com'

# Restarts between two runs (15 min) that count as a crash loop. A crash
# loop restarts every ~10s, so a healthy-looking "active" between crashes
# still shows up here as dozens of restarts.
RESTART_THRESHOLD = 3
# The renewal cron runs daily at 06:00; past this, the cron itself is dead.
RENEW_MAX_AGE_HOURS = 26
# While a problem persists, repeat the alert this often.
REPEAT_SECONDS = 24 * 3600


def systemctl_show(*props):
    out = subprocess.run(
        ['/usr/bin/systemctl', 'show', SERVICE] + [f'-p{p}' for p in props],
        capture_output=True, text=True, timeout=30,
    ).stdout
    return dict(line.split('=', 1) for line in out.splitlines() if '=' in line)


def find_problems(state):
    """Return {key: message} for every check that is currently failing."""
    problems = {}

    svc = systemctl_show('ActiveState', 'NRestarts')
    restarts = int(svc.get('NRestarts') or 0)
    # NRestarts resets to 0 on a manual restart, so only a rise counts.
    previous = state.get('last_nrestarts')
    new_restarts = restarts - previous if previous is not None and restarts >= previous else 0
    state['last_nrestarts'] = restarts

    if svc.get('ActiveState') != 'active':
        problems['service_down'] = f"email-parser is {svc.get('ActiveState', 'unknown')}"
    elif new_restarts >= RESTART_THRESHOLD:
        problems['service_down'] = f"email-parser crash-looping ({new_restarts} restarts in 15 min)"

    try:
        age_hours = (time.time() - os.path.getmtime(RENEW_LOG)) / 3600
        with open(RENEW_LOG, errors='replace') as f:
            lines = [l.strip() for l in f.readlines()[-50:] if l.strip()]
        last = lines[-1] if lines else ''
        if age_hours > RENEW_MAX_AGE_HOURS:
            problems['renew_stale'] = f"Gmail watch renewal hasn't run in {age_hours:.0f}h (cron broken?)"
        elif 'Watch renewed' not in last:
            hint = ' - token revoked, re-run auth_setup.py' if 'invalid_grant' in last else ''
            problems['renew_failed'] = f"Gmail watch renewal failed{hint}: {last[:80]}"
    except OSError as e:
        problems['renew_stale'] = f"Can't read renewal log: {e}"

    return problems


def plan_messages(problems, state, now):
    """Decide which texts to send, updating state.alerts. Pure, for testing."""
    alerts = state.setdefault('alerts', {})
    messages = []

    for key, text in problems.items():
        last_sent = alerts.get(key)
        if last_sent is None or now - last_sent >= REPEAT_SECONDS:
            prefix = 'STILL DOWN' if last_sent is not None else 'ALERT'
            messages.append(f"Work Tracking {prefix}: {text}")
            alerts[key] = now

    for key in [k for k in alerts if k not in problems]:
        del alerts[key]
        messages.append(f"Work Tracking OK: email parser {key.replace('_', ' ')} resolved")

    return messages


def send(messages):
    from app import create_app
    from app.models import User
    from app.utils.sms_service import get_sms_service

    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        tech = admin.technician if admin else None
        if not tech or not tech.phone:
            print(f"{datetime.now():%F %T} no phone on file for {ADMIN_EMAIL}, cannot alert")
            return False
        sms = get_sms_service()
        ok = True
        for msg in messages:
            # Bypass opt-in: this is a system alert to the admin, not a job text.
            result = sms.send_sms(tech.phone, msg, notification_type='other',
                                  tech_id=tech.tech_id, bypass_opt_in_check=True)
            print(f"{datetime.now():%F %T} sent={result.get('success')} {msg} {result.get('error') or ''}")
            ok = ok and result.get('success', False)
        return ok


def main():
    dry_run = '--dry-run' in sys.argv
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}

    problems = find_problems(state)
    messages = plan_messages(problems, state, time.time())

    if messages:
        if dry_run:
            for m in messages:
                print('[dry-run]', m)
        elif not send(messages):
            # Leave the alerts unrecorded so the next run tries again.
            return 1

    if not dry_run:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    return 0


if __name__ == '__main__':
    sys.exit(main())
