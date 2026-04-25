"""
scripts/cleanup_qbo_bills.py — Remove duplicate QBO sandbox bills.

For each vendor that has more than one bill, keeps only the most recent
(highest numeric Id) and deletes the older ones.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/cleanup_qbo_bills.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from intuitlib.client import AuthClient

load_dotenv()

TOKEN_FILE = "qbo_token.json"
QBO_BASE_URL = "https://sandbox-quickbooks.api.intuit.com"
MINOR_VERSION = "65"


# ── Token management (same pattern as seed_qbo_sandbox.py) ──────────

def load_token() -> dict:
    with open(TOKEN_FILE) as f:
        return json.load(f)


def save_token(token_data: dict) -> None:
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def get_access_token(token_data: dict) -> str:
    expiry = datetime.fromisoformat(token_data["token_expiry"])
    if datetime.now(timezone.utc) < expiry:
        return token_data["access_token"]

    print("Refreshing expired access token...")
    auth_client = AuthClient(
        client_id=os.environ["QBO_CLIENT_ID"],
        client_secret=os.environ["QBO_CLIENT_SECRET"],
        redirect_uri="http://localhost:8080",
        environment=os.environ.get("QBO_ENVIRONMENT", "sandbox"),
        refresh_token=token_data["refresh_token"],
    )
    auth_client.refresh(refresh_token=token_data["refresh_token"])

    new_token = {
        "access_token": auth_client.access_token,
        "refresh_token": auth_client.refresh_token,
        "realm_id": token_data["realm_id"],
        "token_expiry": (
            datetime.now(timezone.utc) + timedelta(seconds=auth_client.expires_in)
        ).isoformat(),
    }
    save_token(new_token)
    print("Token refreshed.")
    return auth_client.access_token


# ── QBO REST helpers ─────────────────────────────────────────────────

def qbo_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def qbo_query(query: str, access_token: str, realm_id: str) -> dict:
    url = f"{QBO_BASE_URL}/v3/company/{realm_id}/query"
    resp = requests.get(
        url,
        headers=qbo_headers(access_token),
        params={"query": query, "minorversion": MINOR_VERSION},
    )
    if not resp.ok:
        raise RuntimeError(f"QBO query failed {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def qbo_delete_bill(bill_id: str, sync_token: str, access_token: str, realm_id: str) -> None:
    url = (
        f"{QBO_BASE_URL}/v3/company/{realm_id}/bill"
        f"?operation=delete&minorversion={MINOR_VERSION}"
    )
    payload = {"Id": bill_id, "SyncToken": sync_token}
    resp = requests.post(url, headers=qbo_headers(access_token), json=payload)
    if not resp.ok:
        raise RuntimeError(
            f"QBO DELETE bill id={bill_id} failed {resp.status_code}: {resp.text[:400]}"
        )


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("QBO Sandbox — Duplicate Bill Cleanup")
    print("=" * 60)

    token_data = load_token()
    access_token = get_access_token(token_data)
    realm_id = token_data["realm_id"]

    print(f"\nRealm ID : {realm_id}")

    # Fetch all bills (MAXRESULTS 1000 covers any realistic sandbox volume)
    data = qbo_query(
        "select * from Bill MAXRESULTS 1000",
        access_token,
        realm_id,
    )
    bills = data.get("QueryResponse", {}).get("Bill", [])
    print(f"Total bills fetched: {len(bills)}\n")

    if not bills:
        print("No bills found — nothing to clean up.")
        return

    # Group by vendor display name
    by_vendor: dict[str, list[dict]] = {}
    for bill in bills:
        vendor_name = bill.get("VendorRef", {}).get("name", "Unknown")
        by_vendor.setdefault(vendor_name, []).append(bill)

    deleted: list[dict] = []
    kept: list[dict] = []

    for vendor_name, vendor_bills in sorted(by_vendor.items()):
        # Sort by numeric Id descending — highest Id is most recent seed run
        vendor_bills.sort(key=lambda b: int(b["Id"]), reverse=True)
        keep = vendor_bills[0]
        duplicates = vendor_bills[1:]

        kept.append({"vendor": vendor_name, "id": keep["Id"], "amount": keep.get("TotalAmt", 0)})

        if not duplicates:
            continue

        print(f"{vendor_name}")
        print(f"  keep   id={keep['Id']:>5}  ${keep.get('TotalAmt', 0):>9,.2f}")
        for dup in duplicates:
            dup_id = dup["Id"]
            sync_token = dup["SyncToken"]
            amount = dup.get("TotalAmt", 0)
            print(f"  delete id={dup_id:>5}  ${amount:>9,.2f}", end="  ")
            try:
                qbo_delete_bill(dup_id, sync_token, access_token, realm_id)
                print("✅ deleted")
                deleted.append({"vendor": vendor_name, "id": dup_id, "amount": amount})
            except RuntimeError as exc:
                print(f"❌ FAILED: {exc}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Bills deleted : {len(deleted)}")
    for b in deleted:
        print(f"  id={b['id']:>5}  ${b['amount']:>9,.2f}  {b['vendor']}")
    print(f"\nBills kept    : {len(kept)}")
    for b in kept:
        print(f"  id={b['id']:>5}  ${b['amount']:>9,.2f}  {b['vendor']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
