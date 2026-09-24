"""Seed Accounts from Apollo organization enrichment.

For each domain in DOMAINS: enrich via Apollo (cached in data/cache/), then
upsert an Account on Seed_Key__c = "SEED-ACC-{domain}". Fields Apollo returns as
null are never written. Domains with no employee count are flagged so they can
be swapped out.

Run:  python scripts/seed_accounts.py            # uses cache where present
      python scripts/seed_accounts.py --refresh  # re-fetch every domain (15 credits)
"""

import argparse
import sys
from datetime import date

from simple_salesforce.exceptions import SalesforceMalformedRequest

from apollo_client import ApolloError, get_organization
from setup_quote_fields import connect

TECH_LIMIT = 10
# Apollo lists technologies alphabetically, so "first 10" is arbitrary. Pick by
# category instead: monitoring first (it drives product-mix bias downstream),
# then one per category round-robin across what matters for a software sale.
TECH_CATEGORY_PRIORITY = [
    "Web Performance Monitoring", "Cloud Services", "Database",
    "Data Engineering and Streaming", "Customer Relationship Management",
    "Business Intelligence", "Security", "Deployment Tools",
    "Virtualization and Containers", "ERP", "Financial Software",
    "Communication and Collaboration", "Developer Tools",
]
MONITORING_SLOTS = 3
# Validated against the org's State and Country picklists; rejected values are dropped.
ADDRESS_PICKLISTS = {"BillingState", "BillingCountry"}
APOLLO_KEY = {"BillingState": "state", "BillingCountry": "country"}

# Five per employee band, chosen by expected size; check the printed band.
DOMAINS = [
    # <200
    "plausible.io",
    "cal.com",
    "resend.com",
    "posthog.com",
    "fly.io",
    # 200-2000
    "vercel.com",
    "retool.com",
    "zapier.com",
    "airtable.com",
    "postman.com",
    # >2000
    "gitlab.com",
    "mongodb.com",
    "snowflake.com",
    "datadoghq.com",
    "atlassian.com",
]


def employee_band(count):
    if count is None:
        return None
    if count < 200:
        return "<200"
    if count <= 2000:
        return "200-2000"
    return ">2000"


def load_org(domain: str, refresh: bool):
    """Return (raw Apollo JSON, source) using the shared cache unless refresh is set."""
    return get_organization(domain, refresh)


def pick_technologies(technologies: list) -> list:
    """Up to TECH_LIMIT names: monitoring tools first, then round-robin by category."""
    by_cat = {}
    for t in technologies:
        name = t.get("name")
        if name and t.get("category") in TECH_CATEGORY_PRIORITY:
            by_cat.setdefault(t["category"], [])
            if name not in by_cat[t["category"]]:
                by_cat[t["category"]].append(name)
    picked = by_cat.pop(TECH_CATEGORY_PRIORITY[0], [])[:MONITORING_SLOTS]
    queues = [by_cat[c] for c in TECH_CATEGORY_PRIORITY if by_cat.get(c)]
    while len(picked) < TECH_LIMIT and any(queues):
        for q in queues:
            if q and len(picked) < TECH_LIMIT:
                picked.append(q.pop(0))
    return picked


def account_fields(org: dict) -> dict:
    """Map Apollo org to Account fields, dropping anything Apollo left null."""
    techs = pick_technologies(org.get("current_technologies") or [])
    fields = {
        "Name": org.get("name"),
        "Website": org.get("website_url"),
        "NumberOfEmployees": org.get("estimated_num_employees"),
        "Industry": org.get("industry"),
        "AnnualRevenue": org.get("annual_revenue"),
        "BillingCity": org.get("city"),
        "BillingState": org.get("state"),
        "BillingCountry": org.get("country"),
        "Description": org.get("short_description") or None,
        "Tech_Stack__c": ", ".join(techs) or None,
        "Employee_Band__c": employee_band(org.get("estimated_num_employees")),
        "Apollo_Enriched_Date__c": date.today().isoformat(),
    }
    return {k: v for k, v in fields.items() if v is not None}


def upsert_account(sf, domain: str, fields: dict) -> list:
    """Upsert, dropping address values the org's State/Country picklists reject.

    Returns the list of dropped field names (left blank, never substituted).
    """
    dropped = []
    while True:
        try:
            sf.Account.upsert(f"Seed_Key__c/SEED-ACC-{domain}", fields)
            return dropped
        except SalesforceMalformedRequest as e:
            bad = [f for err in e.content if err.get("errorCode") == "FIELD_INTEGRITY_EXCEPTION"
                   for f in err.get("fields", []) if f in ADDRESS_PICKLISTS and f in fields]
            if not bad:
                raise
            for f in bad:
                fields.pop(f)
                dropped.append(f)
            if "BillingCountry" in bad:  # a state can't be valid without its country
                if fields.pop("BillingState", None) is not None:
                    dropped.append("BillingState")


def fmt_revenue(value):
    if value is None:
        return "-"
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= div:
            return f"{value / div:.1f}{suffix}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true",
                        help="ignore the cache and re-fetch from Apollo (1 credit per domain)")
    args = parser.parse_args()

    sf = connect()
    rows, flagged, failed, notes = [], [], [], []

    for domain in DOMAINS:
        try:
            raw, source = load_org(domain, args.refresh)
        except ApolloError as e:
            failed.append(domain)
            print(f"FAIL  {domain}: {e}")
            continue

        org = raw.get("organization") or {}
        if not org:
            failed.append(domain)
            print(f"FAIL  {domain}: Apollo returned no organization")
            continue

        fields = account_fields(org)
        dropped = upsert_account(sf, domain, fields)
        if dropped:
            notes.append(f"{domain}: left blank, not in Salesforce picklist: "
                         + ", ".join(f"{f}={org.get(APOLLO_KEY[f])!r}" for f in dropped))

        employees = org.get("estimated_num_employees")
        if employees is None:
            flagged.append(domain)
        rows.append((domain, org.get("name") or "-",
                     f"{employees:,}" if employees is not None else "NULL",
                     fields.get("Employee_Band__c", "-"),
                     fmt_revenue(org.get("annual_revenue")), source))

    header = ("Domain", "Name", "Employees", "Band", "Revenue", "Source")
    widths = [max(len(str(r[i])) for r in rows + [header]) for i in range(len(header))]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths))
    print("\n" + line(header))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))

    print(f"\nUpserted {len(rows)} Accounts.")
    for n in notes:
        print("NOTE  " + n)
    if flagged:
        print("SWAP OUT (no estimated_num_employees): " + ", ".join(flagged))
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
