"""Phase 0 check: confirm the Salesforce Developer org is reachable.

Run:  python scripts/test_salesforce.py
Pass when: the org name prints and Quote is queryable.
"""

import os

from dotenv import load_dotenv
from simple_salesforce import Salesforce


def main() -> int:
    load_dotenv()
    required = ["SF_USERNAME", "SF_PASSWORD", "SF_SECURITY_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print("Missing in .env: " + ", ".join(missing))
        return 1

    sf = Salesforce(
        username=os.environ["SF_USERNAME"],
        password=os.environ["SF_PASSWORD"],
        security_token=os.environ["SF_SECURITY_TOKEN"],
        domain=os.getenv("SF_DOMAIN", "login"),
    )

    org = sf.query("SELECT Id, Name, OrganizationType FROM Organization LIMIT 1")
    record = org["records"][0]
    print(f"OK    connected to: {record['Name']} ({record['OrganizationType']})")

    # Quotes must be enabled in Setup > Quote Settings before this passes.
    try:
        sf.query("SELECT Id FROM Quote LIMIT 1")
        print("OK    Quote object is queryable")
    except Exception as exc:  # noqa: BLE001 - surface the real message
        print("WARN  Quote not queryable yet - enable Quotes in Setup > Quote Settings")
        print(f"      {exc}")
        return 1

    print()
    print("Phase 0 Salesforce check: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
