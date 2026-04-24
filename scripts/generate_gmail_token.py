"""
Generate Gmail OAuth token for Phase 2 real email sending.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/generate_gmail_token.py

A browser window will open for Gmail authorization.
Credentials are saved to token.json at the repo root.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "token.json"


def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(credentials.to_json())

    print("✅ token.json generated successfully")


if __name__ == "__main__":
    main()
