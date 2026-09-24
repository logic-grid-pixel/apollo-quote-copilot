"""Phase 0 check: confirm Apollo organization enrichment works.

Run:  python scripts/test_apollo.py [domain ...]
Pass when: status 200 and estimated_num_employees is populated.
"""

import os
import sys

import requests
from dotenv import load_dotenv

BASE = "https://api.apollo.io/api/v1"
DEFAULT_DOMAINS = ["snowflake.com", "mongodb.com", "gitlab.com"]


def enrich(domain: str, api_key: str) -> tuple[int, dict]:
    resp = requests.get(
        f"{BASE}/organizations/enrich",
        params={"domain": domain},
        headers={"x-api-key": api_key, "accept": "application/json"},
        timeout=30,
    )
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text[:300]}
    return resp.status_code, body


def main() -> int:
    load_dotenv()
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        print("APOLLO_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return 1

    domains = sys.argv[1:] or DEFAULT_DOMAINS
    failures = 0

    for domain in domains:
        status, body = enrich(domain, api_key)

        if status != 200:
            failures += 1
            detail = body.get("error_details") or body
            print(f"FAIL  {domain}  status={status}")
            print(f"      {detail}")
            if status in (401, 403):
                print("      403/401 usually means the key lacks the")
                print("      api/v1/organizations/enrich scope, or the free-tier")
                print("      work-email requirement is blocking the account.")
            continue

        org = body.get("organization") or {}
        employees = org.get("estimated_num_employees")
        if not employees:
            failures += 1
            print(f"WARN  {domain}  200 but no employee count - pick another domain")
            continue

        print(
            f"OK    {domain}  {org.get('name')} | "
            f"{employees} employees | {org.get('industry')} | "
            f"{org.get('annual_revenue_printed')}"
        )

    print()
    print("Phase 0 Apollo check: " + ("PASSED" if failures == 0 else f"{failures} issue(s)"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
