"""Look up a demo scenario's open Opportunity (Seed_Key__c = DEMO-OPP-<scenario>).

The Opportunity Id is what scripts/sfdc_client.py --opportunity needs.

CLI:  python scripts/find_opportunity.py <scenario>
      prints {scenario, seed_key, opportunity_id, name, account_id, stage}
"""

from __future__ import annotations

import argparse
import json
import sys

from seed_demo_opportunities import KEY_PREFIX, SCENARIO_DOMAINS
from sf_session import connect

SCENARIOS = tuple(SCENARIO_DOMAINS)


def find(sf, scenario: str) -> dict:
    # Whitelisted, so nothing user-supplied is spliced into SOQL.
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}, got {scenario!r}")
    key = f"{KEY_PREFIX}{scenario}"
    records = sf.query("SELECT Id, Name, AccountId, StageName FROM Opportunity "
                       f"WHERE Seed_Key__c = '{key}'")["records"]
    if not records:
        raise LookupError(f"no Opportunity with Seed_Key__c {key} "
                          "(run scripts/seed_demo_opportunities.py)")
    r = records[0]
    return {"scenario": scenario, "seed_key": key, "opportunity_id": r["Id"],
            "name": r["Name"], "account_id": r["AccountId"], "stage": r["StageName"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Find a demo scenario's Opportunity Id")
    parser.add_argument("scenario", choices=SCENARIOS)
    args = parser.parse_args(argv)
    try:
        result = find(connect(), args.scenario)
    except (LookupError, ValueError) as e:
        print(json.dumps({"scenario": args.scenario, "error": str(e)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
