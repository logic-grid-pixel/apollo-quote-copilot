"""Seed 3-4 synthetic Contacts per seeded Account.

Titles come from Apollo People Search for the account's domain (titles only;
no names or emails are kept). If the Apollo plan can't call People Search (Free
plan: 403), a curated title pool for the account's employee band is used
instead. Title lists are cached in data/cache/titles_{domain}.json with their
source, so re-runs are offline.

Names are synthetic and deterministic per seed key. Buying_Role__c is mapped
from the title. Contacts are upserted on Seed_Key__c = "SEED-CON-{domain}-{n}".

Run:  python scripts/seed_contacts.py            # uses cached titles
      python scripts/seed_contacts.py --refresh  # retry Apollo for every account
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from apollo_client import ApolloError, search_people_titles
from setup_quote_fields import connect

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
ACC_PREFIX = "SEED-ACC-"

SENIORITIES = ["c_suite", "vp", "head", "director"]
TITLE_KEYWORDS = ["engineering", "IT", "information technology", "operations", "finance",
                  "procurement", "purchasing", "chief"]

# Fill order: one contact per role first, then top up with whatever is left.
ROLE_PRIORITY = ["Economic Buyer", "Technical Evaluator", "Procurement", "Champion"]
CONTACTS_PER_BAND = {"<200": 3, "200-2000": 4, ">2000": 4}

# (pattern, role) checked in order; first match wins.
ROLE_RULES = [
    (r"procure|purchas|sourcing|vendor", "Procurement"),
    (r"\bcfo\b|financ|controller|treasur|\bceo\b|chief executive|founder|president|owner",
     "Economic Buyer"),
    (r"\bcto\b|\bcio\b|\bciso\b|chief (technology|information|security)|engineer|\bit\b|"
     r"information technology|infrastructure|security|platform|architect|devops|data",
     "Technical Evaluator"),
    (r"\bcoo\b|chief operating|operations|\bops\b|revops|enablement", "Champion"),
]

# Used only when Apollo People Search is unavailable. Titles are typical for the
# band; roles still come from ROLE_RULES, not from this table.
CURATED_TITLES = {
    "<200": ["CEO", "Co-Founder & CEO", "CTO", "Head of Engineering", "VP of Engineering",
             "Head of Operations", "COO", "Head of Finance"],
    "200-2000": ["CFO", "VP of Finance", "VP of Engineering", "Director of IT",
                 "Head of Platform Engineering", "Procurement Manager", "Head of Procurement",
                 "VP of Operations", "Director of Business Operations",
                 "Director of Revenue Operations"],
    ">2000": ["Chief Financial Officer", "SVP, Finance", "VP, Finance", "Chief Information Officer",
              "VP, IT Infrastructure", "Director of Engineering", "Director, Strategic Sourcing",
              "Head of Global Procurement", "Senior Procurement Manager",
              "VP, Business Operations", "Senior Director, Revenue Operations"],
}

FIRST_NAMES = ["Avery", "Jordan", "Riley", "Casey", "Morgan", "Quinn", "Rowan", "Skyler",
               "Harper", "Emerson", "Parker", "Reese", "Sage", "Dakota", "Finley", "Hayden",
               "Kendall", "Logan", "Marlowe", "Remy", "Sasha", "Tatum", "Blair", "Carmen"]
LAST_NAMES = ["Ashdown", "Brightwater", "Calloway", "Delacroix", "Everly", "Fairbanks",
              "Galloway", "Hartwell", "Ingram", "Juniper", "Kingsley", "Lockwood", "Merriweather",
              "Northcott", "Oakley", "Pemberton", "Quill", "Ravenscroft", "Stirling",
              "Thistlewood", "Underhill", "Vance", "Whitlock", "Yardley"]


def buying_role(title: str) -> str:
    t = title.lower()
    for pattern, role in ROLE_RULES:
        if re.search(pattern, t):
            return role
    return "End User"


def stable_rank(domain: str, text: str) -> str:
    return hashlib.sha256(f"{domain}|{text}".encode()).hexdigest()


def load_titles(domain: str, band: str, refresh: bool):
    """Return (titles, source), from cache unless refresh is set."""
    path = CACHE_DIR / f"titles_{domain}.json"
    if path.exists() and not refresh:
        cached = json.loads(path.read_text())
        return cached["titles"], f"{cached['source']} (cache)"
    try:
        titles, source = search_people_titles(domain, SENIORITIES, TITLE_KEYWORDS), "apollo"
    except ApolloError as e:
        if e.status not in (401, 403):
            raise
        titles, source = CURATED_TITLES[band], "curated"
    titles = list(dict.fromkeys(titles))  # de-dupe, keep order
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"domain": domain, "source": source, "titles": titles}, indent=2))
    return titles, source


def pick_titles(domain: str, titles: list, count: int) -> list:
    """One title per role in ROLE_PRIORITY, then top up; order varies per domain."""
    ranked = sorted(titles, key=lambda t: stable_rank(domain, t))
    picked = []
    for role in ROLE_PRIORITY:
        match = next((t for t in ranked if buying_role(t) == role and t not in picked), None)
        if match and len(picked) < count:
            picked.append(match)
    picked += [t for t in ranked if t not in picked][:count - len(picked)]
    return picked


def synthetic_name(seed_key: str, used: set):
    h = int(stable_rank("name", seed_key), 16)
    for i in range(len(FIRST_NAMES) * len(LAST_NAMES)):
        first = FIRST_NAMES[(h + i) % len(FIRST_NAMES)]
        last = LAST_NAMES[(h // len(FIRST_NAMES) + i) % len(LAST_NAMES)]
        if (first, last) not in used:
            used.add((first, last))
            return first, last
    raise RuntimeError("synthetic name list exhausted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true",
                        help="ignore cached titles and retry Apollo People Search")
    args = parser.parse_args()

    sf = connect()
    accounts = sf.query_all(
        "SELECT Id, Name, Seed_Key__c, Employee_Band__c FROM Account "
        f"WHERE Seed_Key__c LIKE '{ACC_PREFIX}%' ORDER BY NumberOfEmployees")["records"]
    if not accounts:
        print("No seeded Accounts found. Run scripts/seed_accounts.py first.")
        return 1

    used_names, total, short = set(), 0, []
    for acc in accounts:
        domain = acc["Seed_Key__c"][len(ACC_PREFIX):]
        band = acc["Employee_Band__c"] or "200-2000"
        titles, source = load_titles(domain, band, args.refresh)
        picked = pick_titles(domain, titles, CONTACTS_PER_BAND.get(band, 4))
        if len(picked) < 3:
            short.append(domain)

        print(f"\n{acc['Name']} ({domain}, {band}) - {len(titles)} titles from {source}")
        for n, title in enumerate(picked, start=1):
            key = f"SEED-CON-{domain}-{n}"
            first, last = synthetic_name(key, used_names)
            role = buying_role(title)
            sf.Contact.upsert(f"Seed_Key__c/{key}", {
                "AccountId": acc["Id"], "FirstName": first, "LastName": last,
                "Title": title, "Buying_Role__c": role})
            print(f"  {n}. {title:40} -> {role}")
        total += len(picked)

        # Remove contacts left over from an earlier run that picked more titles.
        stale = sf.query(f"SELECT Id FROM Contact WHERE Seed_Key__c LIKE 'SEED-CON-{domain}-%'"
                         f" AND Seed_Key__c NOT IN ({', '.join(repr(f'SEED-CON-{domain}-{n}') for n in range(1, len(picked) + 1))})")
        for rec in stale["records"]:
            sf.Contact.delete(rec["Id"])

    print(f"\nUpserted {total} Contacts across {len(accounts)} Accounts.")
    if short:
        print("FEWER THAN 3 TITLES: " + ", ".join(short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
