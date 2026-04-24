"""
Generate QBO OAuth token for Phase 2 real QuickBooks integration.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/generate_qbo_token.py

A browser window will open for QuickBooks authorization.
Tokens are saved to qbo_token.json at the repo root.
"""

import json
import os
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes

load_dotenv()

CLIENT_ID = os.environ["QBO_CLIENT_ID"]
CLIENT_SECRET = os.environ["QBO_CLIENT_SECRET"]
REALM_ID = os.environ["QBO_REALM_ID"]
ENVIRONMENT = os.environ.get("QBO_ENVIRONMENT", "sandbox")
REDIRECT_URI = "http://localhost:8080"
TOKEN_FILE = "qbo_token.json"

auth_client = AuthClient(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    environment=ENVIRONMENT,
)

callback_params: dict = {}
server_done = threading.Event()


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        callback_params["code"] = params.get("code", [None])[0]
        callback_params["state"] = params.get("state", [None])[0]
        callback_params["realm_id"] = params.get("realmId", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h2>Authorization complete. You can close this tab.</h2></body></html>")
        server_done.set()

    def log_message(self, format, *args):
        pass  # suppress request logs


def main():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])

    print(f"Opening browser for QBO authorization...")
    print(f"If the browser does not open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    httpd = HTTPServer(("localhost", 8080), CallbackHandler)
    thread = threading.Thread(target=httpd.handle_request)
    thread.start()

    print("Waiting for authorization callback on http://localhost:8080 ...")
    server_done.wait(timeout=300)
    thread.join()

    auth_code = callback_params.get("code")
    realm_id = callback_params.get("realm_id") or REALM_ID

    if not auth_code:
        raise RuntimeError("No authorization code received — did you complete the browser flow?")

    auth_client.get_bearer_token(auth_code, realm_id=realm_id)

    token_data = {
        "access_token": auth_client.access_token,
        "refresh_token": auth_client.refresh_token,
        "realm_id": realm_id,
        "token_expiry": (
            datetime.now(timezone.utc) + timedelta(seconds=auth_client.expires_in)
        ).isoformat(),
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print("✅ qbo_token.json generated successfully")


if __name__ == "__main__":
    main()
