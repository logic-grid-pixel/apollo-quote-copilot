"""Seed ~80 closed Opportunities on the seeded Accounts.

Anchored to Apollo data already on the Account where possible:
  Segment__c      from NumberOfEmployees
  Amount          0.05%-0.3% of AnnualRevenue, kept inside the segment's range
  Product_Mix__c  tier biased up when Tech_Stack__c shows observability tooling

Generated (no external source): stage, close date, discount, renewal outcome.
Approver_Level__c comes from the per-segment bands in reference/approval_policy.yaml.

Reproducible via random.seed(42). Upserts on Seed_Key__c = "SEED-OPP-{domain}-{n}".
Close dates are relative to today, so "Too Early" shifts as time passes.

Run:  python scripts/seed_opportunities.py
      python scripts/seed_opportunities.py --reset   # delete SEED-% Opportunities first
"""

import argparse
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import preflight
from apollo_client import segment_for_headcount
from setup_quote_fields import connect

POLICY = Path(__file__).resolve().parent.parent / "reference" / "approval_policy.yaml"
SEED = 42
TOTAL = 80
WON_SHARE = 0.70
ENTERPRISE_OUTLIERS = 4  # Closed Won Enterprise deals at 42-48% discount
HISTORY_DAYS = 730
TOO_EARLY_DAYS = 365

SEGMENTS = {  # amount range (USD), discount range (%)
    "SMB": {"amount": (15_000, 60_000), "discount": (5, 20)},
    "Mid-Market": {"amount": (60_000, 250_000), "discount": (10, 28)},
    "Enterprise": {"amount": (250_000, 1_200_000), "discount": (18, 40)},
}
REVENUE_SHARE = (0.0005, 0.003)

TIERS = ["Platform Starter", "Platform Pro", "Platform Enterprise"]
BASE_TIER_WEIGHTS = {"SMB": [70, 25, 5], "Mid-Market": [15, 65, 20], "Enterprise": [0, 30, 70]}
OBSERVABILITY = ["datadog", "new relic", "splunk", "grafana", "prometheus", "sentry",
                 "pagerduty", "dynatrace", "honeycomb", "elastic apm", "elastic stack",
                 "appdynamics", "logz", "sumo logic", "lightstep", "instana"]
REGULATED = ["financial", "banking", "insurance", "health", "hospital", "government"]
ADDON_ODDS = {  # probability of each add-on by segment
    "SMB": {"Additional Seats": 0.3, "Premium Support": 0.15, "Implementation Services": 0.2},
    "Mid-Market": {"Additional Seats": 0.6, "Premium Support": 0.4,
                   "Implementation Services": 0.5},
    "Enterprise": {"Additional Seats": 0.8, "Premium Support": 0.7,
                   "Implementation Services": 0.8},
}

RENEWAL_ODDS = [  # (max discount %, [(outcome, weight), ...]) for Closed Won > 12 months old
    (30, [("Renewed", 50), ("Expanded", 30), ("Churned", 20)]),
    (40, [("Renewed", 40), ("Expanded", 20), ("Churned", 40)]),
    (100, [("Renewed", 35), ("Expanded", 15), ("Churned", 50)]),
]
DISCOUNT_BANDS = [("<30%", 30), ("30-40%", 40), (">40%", 100)]


def load_policy():
    """Per-segment approval bands from reference/approval_policy.yaml (via preflight)."""
    return preflight.load_policy(POLICY)


def approver_level(discount, segment, policy):
    """Approval level for a discount in the Opportunity's Segment__c."""
    return preflight.discount_approval(policy, segment, discount)[0]


segment_for = segment_for_headcount  # single rule, defined in apollo_client


def employee_band(segment):
    return {"SMB": "<200", "Mid-Market": "200-2000", "Enterprise": ">2000"}[segment]


def deal_amount(rng, revenue, segment):
    lo, hi = SEGMENTS[segment]["amount"]
    if revenue:
        amount = revenue * rng.uniform(*REVENUE_SHARE)
        # Floor/cap with some spread so clamped deals aren't all identical.
        if amount < lo:
            amount = rng.uniform(lo, lo * 1.6)
        elif amount > hi:
            amount = rng.uniform(hi * 0.7, hi)
    else:
        amount = rng.uniform(lo, hi)
    return round(min(max(amount, lo), hi) / 500) * 500


def product_mix(rng, segment, tech_stack, industry):
    weights = list(BASE_TIER_WEIGHTS[segment])
    if any(k in (tech_stack or "").lower() for k in OBSERVABILITY):
        weights = [0] + weights[:-2] + [weights[-2] + weights[-1]]  # shift one tier up
    tier = rng.choices(TIERS, weights=weights)[0]
    odds = dict(ADDON_ODDS[segment])
    if any(k in (industry or "").lower() for k in REGULATED):
        odds["Premium Support"] = min(1.0, odds["Premium Support"] + 0.3)
    return [tier] + [p for p, o in odds.items() if rng.random() < o]


def renewal_outcome(rng, discount, days_ago):
    if days_ago < TOO_EARLY_DAYS:
        return "Too Early"
    for max_pct, odds in RENEWAL_ODDS:
        if discount <= max_pct:
            outcomes, weights = zip(*odds)
            return rng.choices(outcomes, weights=weights)[0]


def build(accounts, policy, today):
    rng = random.Random(SEED)
    # Spread deals evenly, remainder to random accounts.
    per_account = Counter({a["Id"]: TOTAL // len(accounts) for a in accounts})
    for a in rng.sample(accounts, TOTAL % len(accounts)):
        per_account[a["Id"]] += 1

    plan = [a for a in accounts for _ in range(per_account[a["Id"]])]
    # 70/30 won/lost within each segment, so segment mix can't mask the
    # "lost deals had lower discounts" pattern.
    won_flags = [False] * len(plan)
    by_segment = defaultdict(list)
    for i, a in enumerate(plan):
        by_segment[segment_for(a["NumberOfEmployees"])].append(i)
    for idx in by_segment.values():
        for i in rng.sample(idx, round(len(idx) * WON_SHARE)):
            won_flags[i] = True

    ent_won = [i for i, (a, w) in enumerate(zip(plan, won_flags))
               if w and segment_for(a["NumberOfEmployees"]) == "Enterprise"]
    outliers = set(rng.sample(ent_won, min(ENTERPRISE_OUTLIERS, len(ent_won))))

    records, counters = [], Counter()
    for i, (acc, won) in enumerate(zip(plan, won_flags)):
        domain = acc["Seed_Key__c"][len("SEED-ACC-"):]
        segment = segment_for(acc["NumberOfEmployees"])
        d_lo, d_hi = SEGMENTS[segment]["discount"]
        if i in outliers:
            discount = rng.uniform(42, 48)
        elif won:
            discount = rng.uniform(d_lo, d_hi)
        else:
            discount = rng.triangular(d_lo, d_hi, d_lo)  # lost deals skew low
        discount = round(discount, 2)

        # Outliers close 12-24 months ago so they carry a real renewal outcome.
        days_ago = rng.randint(TOO_EARLY_DAYS, HISTORY_DAYS) if i in outliers \
            else rng.randint(1, HISTORY_DAYS)
        products = product_mix(rng, segment, acc["Tech_Stack__c"], acc["Industry"])
        counters[domain] += 1
        n = counters[domain]
        close = today - timedelta(days=days_ago)
        records.append({
            "Seed_Key__c": f"SEED-OPP-{domain}-{n}",
            "Name": f"{acc['Name']} - {products[0]} ({close:%Y-%m})",
            "AccountId": acc["Id"],
            "StageName": "Closed Won" if won else "Closed Lost",
            "CloseDate": close.isoformat(),
            "Amount": deal_amount(rng, acc["AnnualRevenue"], segment),
            "Segment__c": segment,
            "Employee_Band__c": employee_band(segment),
            "Effective_Discount__c": discount,
            "Approver_Level__c": approver_level(discount, segment, policy),
            "Product_Mix__c": "; ".join(products)[:255],
            "Renewal_Outcome__c": renewal_outcome(rng, discount, days_ago) if won else None,
        })
    return records


def band_of(discount):
    return next(label for label, max_pct in DISCOUNT_BANDS if discount <= max_pct)


def summarize(records, observability_accounts):
    won = [r for r in records if r["StageName"] == "Closed Won"]
    print(f"\nOpportunities: {len(records)}  (Closed Won {len(won)}, "
          f"Closed Lost {len(records) - len(won)})")
    print(f"Accounts with observability tooling in Tech_Stack__c: "
          f"{', '.join(observability_accounts) or 'none'}")

    print(f"\n{'Segment':12} {'Deals':>5} {'Won':>4} {'Lost':>5}  "
          f"{'Disc min':>8} {'median':>7} {'max':>6}  {'Amount median':>13}  Approvers")
    for seg in SEGMENTS:
        rs = [r for r in records if r["Segment__c"] == seg]
        if not rs:
            continue
        d = [r["Effective_Discount__c"] for r in rs]
        w = sum(r["StageName"] == "Closed Won" for r in rs)
        appr = Counter(r["Approver_Level__c"] for r in rs)
        print(f"{seg:12} {len(rs):>5} {w:>4} {len(rs) - w:>5}  {min(d):>7.2f}% "
              f"{statistics.median(d):>6.2f}% {max(d):>5.2f}%  "
              f"{statistics.median(r['Amount'] for r in rs):>13,.0f}  "
              + ", ".join(f"{k} {v}" for k, v in sorted(appr.items())))

    lost = [r["Effective_Discount__c"] for r in records if r["StageName"] == "Closed Lost"]
    print(f"\nMedian discount: Closed Won {statistics.median(r['Effective_Discount__c'] for r in won):.2f}%"
          f" vs Closed Lost {statistics.median(lost):.2f}%")

    outcomes = ["Renewed", "Expanded", "Churned", "Too Early"]
    grid = defaultdict(Counter)
    for r in won:
        grid[band_of(r["Effective_Discount__c"])][r["Renewal_Outcome__c"]] += 1
    print(f"\nRenewal outcome by discount band (Closed Won)")
    print(f"{'Band':8}" + "".join(f"{o:>11}" for o in outcomes) + f"{'Churn rate*':>13}")
    for label, _ in DISCOUNT_BANDS:
        c = grid[label]
        matured = sum(c[o] for o in outcomes[:3])
        rate = f"{c['Churned'] / matured:.0%}" if matured else "-"
        print(f"{label:8}" + "".join(f"{c[o]:>11}" for o in outcomes) + f"{rate:>13}")
    print("* churned / (renewed + expanded + churned); excludes Too Early")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true",
                        help="delete Opportunities with Seed_Key__c LIKE 'SEED-%%' before seeding")
    args = parser.parse_args()

    sf = connect()
    policy = load_policy()

    if args.reset:
        old = sf.query_all("SELECT Id FROM Opportunity WHERE Seed_Key__c LIKE 'SEED-%'")["records"]
        if old:
            res = sf.bulk.Opportunity.delete([{"Id": r["Id"]} for r in old])
            print(f"Reset: deleted {sum(r['success'] for r in res)} seeded Opportunities")

    accounts = sf.query_all(
        "SELECT Id, Name, Seed_Key__c, NumberOfEmployees, AnnualRevenue, Industry, "
        "Tech_Stack__c FROM Account WHERE Seed_Key__c LIKE 'SEED-ACC-%' "
        "AND NumberOfEmployees != null ORDER BY Seed_Key__c")["records"]
    if not accounts:
        print("No seeded Accounts with employee counts. Run scripts/seed_accounts.py first.")
        return 1

    records = build(accounts, policy, date.today())
    results = sf.bulk.Opportunity.upsert(records, "Seed_Key__c", batch_size=200)
    errors = [(rec["Seed_Key__c"], res["errors"]) for rec, res in zip(records, results)
              if not res["success"]]
    for key, errs in errors:
        print(f"FAIL  {key}: {errs}")
    print(f"Upserted {len(records) - len(errors)} Opportunities "
          f"({sum(r['created'] for r in results if r['success'])} created)")

    obs = [a["Name"] for a in accounts
           if any(k in (a["Tech_Stack__c"] or "").lower() for k in OBSERVABILITY)]
    summarize(records, obs)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
