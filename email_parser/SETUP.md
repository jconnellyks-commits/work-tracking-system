# Email Parser Setup Guide

Automates job creation from TechLink and Tech Service Today dispatch emails
sent to jconnellyks@gmail.com.

## Architecture

- **Gmail push notifications** via Google Pub/Sub (StreamingPull)
- **Python daemon** on the GCP VM (`remoteworkstation`) alongside `work-tracking` service
- **Systemd service** `email-parser` — starts on boot, restarts on failure

---

## Step 1: Enable APIs (one-time)

```bash
gcloud services enable gmail.googleapis.com pubsub.googleapis.com \
  --project=remoteworkstation
```

---

## Step 2: Create Pub/Sub Topic and Subscription

```bash
gcloud pubsub topics create gmail-dispatch-notifications \
  --project=remoteworkstation

gcloud pubsub subscriptions create gmail-dispatch-sub \
  --topic=gmail-dispatch-notifications \
  --ack-deadline=60 \
  --project=remoteworkstation
```

Grant Gmail the right to publish to the topic:
```bash
gcloud pubsub topics add-iam-policy-binding gmail-dispatch-notifications \
  --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
  --role=roles/pubsub.publisher \
  --project=remoteworkstation
```

---

## Step 3: Create OAuth2 Credentials (one-time)

1. Go to **GCP Console → APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Name: `email-parser`
5. Download the JSON file and save as `credentials.json` in this directory

---

## Step 4: Local Auth Flow (run once from your Windows machine)

```bash
cd email_parser
pip install google-auth-oauthlib google-api-python-client
python auth_setup.py
```

A browser window will open. Sign in as **jconnellyks@gmail.com** and grant permissions.
`token.json` will be saved locally.

---

## Step 5: Deploy to Server

```bash
# Copy credentials and token to server
powershell -Command "scp -i '$HOME/.ssh/gcp_work_tracking' token.json credentials.json claude-code@34.27.146.58:/tmp/"

# SSH into server
ssh -i ~/.ssh/gcp_work_tracking claude-code@34.27.146.58

# Create app directory
sudo mkdir -p /opt/email-parser
sudo chown claude-code:claude-code /opt/email-parser

# Copy files from repo (after git pull)
cp -r /opt/work-tracking/email_parser/* /opt/email-parser/
mv /tmp/token.json /opt/email-parser/token.json
mv /tmp/credentials.json /opt/email-parser/credentials.json

# Set up virtualenv
cd /opt/email-parser
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

---

## Step 6: Create .env File on Server

```bash
cat > /opt/email-parser/.env << 'EOF'
API_URL=https://worktracking.sleepybear.tech/api
API_EMAIL=your-admin@email.com
API_PASSWORD=your-admin-password
GCP_PROJECT=remoteworkstation
PUBSUB_SUBSCRIPTION=gmail-dispatch-sub
PUBSUB_TOPIC=gmail-dispatch-notifications
STATE_FILE=/opt/email-parser/state.json
TOKEN_FILE=/opt/email-parser/token.json
CREDENTIALS_FILE=/opt/email-parser/credentials.json
EOF
chmod 600 /opt/email-parser/.env
```

---

## Step 7: Install and Start Systemd Service

```bash
sudo cp /opt/email-parser/email_parser.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-parser
sudo systemctl start email-parser
sudo systemctl status email-parser
```

---

## Step 8: Set Up Watch Renewal Cron

Gmail push watches expire after 7 days. Add a daily cron job:

```bash
crontab -e
# Add:
0 6 * * * cd /opt/email-parser && venv/bin/python renew_watch.py >> /var/log/email-parser-watch.log 2>&1
```

---

## Verification

```bash
# Check service logs
sudo journalctl -u email-parser -f

# Manual endpoint test (TST)
curl -s -X POST https://worktracking.sleepybear.tech/api/imports/tst \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"ticket_number":"502861","client_name":"Altoona Quarry (Altoona, KS)","job_date":"2026-02-27","scheduled_start_time":"09:30","description":"Onsite Support for Site Migration","billing_rate":75.00,"trip_charge":130.00,"status":"assigned"}]'

# Manual endpoint test (TechLink)
curl -s -X POST https://worktracking.sleepybear.tech/api/imports/techlink \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"ticket_number":"398586","client_name":"Wichita Dwight D. Eisenhower Natl Airport","job_date":"2026-02-20","scheduled_start_time":"09:30","description":"Filter Change","address":"1980 S. Airport Road, Wichita, KS 67209","contact":"Robert Halbleib, 3167558870","status":"assigned"}]'

# Test parser locally against sample .eml files
python -c "
import json, sys
sys.path.insert(0, '.')
# You'd need to construct a Gmail-style message dict from the .eml
"
```

---

## How It Works

1. Gmail delivers new emails to the Pub/Sub topic via push notifications
2. The daemon's StreamingPull picks up notifications instantly (~seconds)
3. For each new INBOX message from known senders:
   - **TST Service Order** → parsed → `POST /api/imports/tst`
   - **TST Special Update** → rate/trip extracted → `POST /api/imports/tst` (updates existing)
   - **TechLink Assigned** → parsed → `POST /api/imports/techlink`
   - Unknown TST/TechLink email → labeled `work-orders/review` for manual review
4. Processed emails get labeled `work-orders/{platform}/processed` and archived from INBOX
5. Jobs appear in the Work Tracking UI as "assigned" status, unassigned to a technician

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `token.json` expired | Re-run `auth_setup.py` locally, scp new token to server |
| Watch expired | Run `python renew_watch.py` or check cron |
| Email not parsed | Check `work-orders/review` Gmail label |
| API import fails | Check `sudo journalctl -u email-parser` for error details |
| historyId 404 error | State file deleted or too old — service resets automatically |
