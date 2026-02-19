#!/usr/bin/env python3
"""
One-time OAuth setup. Run locally:
  python auth_setup.py
Opens a browser, prompts Google sign-in for jconnellyks@gmail.com,
saves token.json for the service to use.
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_FILE = os.environ.get('CREDENTIALS_FILE', 'credentials.json')
TOKEN_FILE = os.environ.get('TOKEN_FILE', 'token.json')

if not os.path.exists(CREDENTIALS_FILE):
    print(f"ERROR: {CREDENTIALS_FILE} not found.")
    print("Download OAuth2 Desktop credentials from GCP Console and save as credentials.json")
    sys.exit(1)

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, 'w') as f:
    f.write(creds.to_json())

print(f"Token saved to {TOKEN_FILE}")
print("Copy token.json and credentials.json to the server:")
print(f"  scp token.json credentials.json claude-code@34.27.146.58:/opt/email-parser/")
