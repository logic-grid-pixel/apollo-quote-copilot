"""Upsert one OPEN Opportunity per demo scenario, for Quote Copilot to quote against.

Keys are DEMO-OPP-<scenario>, deliberately not SEED-, so
`seed_opportunities.py --reset` (which deletes SEED-%) never removes them, and
comparables.py (SEED-OPP-% only) never counts them as history.

Rep and rep-stated segment come from eval/specs/<scenario>.yaml; Segment__c is
left blank on purpose (the rep's segment is context, not a verified fact).

Run:  python scripts/seed_demo_opportunities.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from sf_session import connect

SPECS = Path(__file__).resolve().parent.parent / "eval" / "specs"
SCENARIO_DOMAINS = {
    "clean-midmarket": "retool.com",
    "conflicting-seats": "postman.com",
    "mis-segmented": "mongodb.com",
    "aggressive-discount": "snowflake.com",
    "smb-starter": "cal.com",
}
STAGE = "Proposal/Price Quote"
CLOSE_IN_DAYS = 30
KEY_PREFIX = "DEMO-OPP-"


def build_records(accounts_by_domain: dict, today: date) -> list:
    records = []
    for scenario, domain in SCENARIO_DOMAINS.items():
        spec = yaml.safe_load((SPECS / f"{scenario}.yaml").read_text())
        acc = accounts_by_domain[domain]
        records.append({
            "Seed_Key__c": f"{KEY_PREFIX}{scenario}",
            "Name": f"{acc['Name']} - Quote Copilot demo ({scenario})",
            "AccountId": acc["Id"],
            "StageName": STAGE,
            "CloseDate": (today + timedelta(days=CLOSE_IN_DAYS)).isoformat(),
            "Description": (f"Quote Copilot demo scenario '{scenario}'. Rep: {spec['rep']}. "
                            f"Rep-stated segment: {spec['rep_stated_segment']} "
                            "(unverified; the pre-flight checks it against Apollo)."),
        })
    return records


def run(sf, today: date) -> int:
    keys = ", ".join(f"'SEED-ACC-{d}'" for d in SCENARIO_DOMAINS.values())
    accounts = sf.query(f"SELECT Id, Name, Seed_Key__c FROM Account "
                        f"WHERE Seed_Key__c IN ({keys})")["records"]
    by_domain = {a["Seed_Key__c"][len("SEED-ACC-"):]: a for a in accounts}
    missing = [d for d in SCENARIO_DOMAINS.values() if d not in by_domain]
    if missing:
        print("FAIL  seeded Account missing for: " + ", ".join(missing)
              + " (run scripts/seed_accounts.py)")
        return 1
    for rec in build_records(by_domain, today):
        key = rec.pop("Seed_Key__c")
        status = sf.Opportunity.upsert(f"Seed_Key__c/{key}", rec)
        print(f"OK    {key}: {'created' if status == 201 else 'updated'} "
              f"({rec['Name']}, close {rec['CloseDate']})")
    return 0


def main() -> int:
    return run(connect(), date.today())


if __name__ == "__main__":
    sys.exit(main())
