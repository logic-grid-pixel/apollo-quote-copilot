"""Comparable closed deals from the seeded Opportunity history.

Pulls closed seeded Opportunities in the same Segment__c (optionally the same
platform tier, the first item in Product_Mix__c), then compares the cohort at or
near the proposed discount (>= proposed - window) with lower-discount deals.

Churn rate = Churned / (Renewed + Expanded + Churned) among Closed Won deals;
"Too Early" is excluded and reported separately. Every rate is reported with
its counts, never as a trend word alone.

CLI:  python scripts/comparables.py --segment Enterprise --discount 40
          [--tier "Platform Enterprise"] [--window 5]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys

from sf_session import connect

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")
TIERS = ("Platform Starter", "Platform Pro", "Platform Enterprise")
OUTCOMES = ("Renewed", "Expanded", "Churned", "Too Early")
MATURED = ("Renewed", "Expanded", "Churned")
SEED_PREFIX = "SEED-OPP-"
DEFAULT_WINDOW = 5.0
SMALL_SAMPLE = 3  # fewer matured deals than this in a cohort -> flag it

FIELDS = ["Id", "Name", "StageName", "CloseDate", "Amount", "Segment__c",
          "Effective_Discount__c", "Product_Mix__c", "Renewal_Outcome__c", "Approver_Level__c"]


def build_soql(segment: str, tier: str = None) -> str:
    # Values are whitelisted, so nothing user-supplied is ever spliced into SOQL.
    if segment not in SEGMENTS:
        raise ValueError(f"segment must be one of {SEGMENTS}, got {segment!r}")
    if tier is not None and tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
    where = [f"Seed_Key__c LIKE '{SEED_PREFIX}%'", "IsClosed = true",
             f"Segment__c = '{segment}'", "Effective_Discount__c != null"]
    if tier:
        where.append(f"Product_Mix__c LIKE '{tier}%'")
    return (f"SELECT {', '.join(FIELDS)} FROM Opportunity WHERE "
            + " AND ".join(where) + " ORDER BY Effective_Discount__c")


def _tier_of(record) -> str:
    return (record.get("Product_Mix__c") or "").split(";")[0].strip()


def _r2(x):
    return None if x is None else round(float(x) + 0.0, 2)


def cohort_stats(records: list, label: str) -> dict:
    d = [float(r["Effective_Discount__c"]) for r in records]
    won = [r for r in records if r["StageName"] == "Closed Won"]
    outcomes = {o: sum(r.get("Renewal_Outcome__c") == o for r in won) for o in OUTCOMES}
    matured = sum(outcomes[o] for o in MATURED)
    churned = outcomes["Churned"]
    return {
        "discount_range": label,
        "count": len(records),
        "won": len(won),
        "lost": len(records) - len(won),
        "discount_pct": {"min": _r2(min(d)) if d else None,
                         "median": _r2(statistics.median(d)) if d else None,
                         "max": _r2(max(d)) if d else None},
        "renewal_outcomes": outcomes,
        "matured": matured,
        "churned": churned,
        "churn_rate_pct": round(100.0 * churned / matured, 2) if matured else None,
    }


def _rate_text(c: dict) -> str:
    if not c["matured"]:
        return f"no deals with a renewal outcome yet (0 of 0; {c['count']} deals in cohort)"
    return (f"{c['churned']} of {c['matured']} with a renewal outcome churned "
            f"({c['churn_rate_pct']:.2f}%)")


def summarize(records: list, proposed_discount: float, window: float = DEFAULT_WINDOW,
              segment: str = None) -> dict:
    cut = float(proposed_discount) - float(window)
    near = [r for r in records if float(r["Effective_Discount__c"]) >= cut]
    lower = [r for r in records if float(r["Effective_Discount__c"]) < cut]
    all_c = cohort_stats(records, "all")
    near_c = cohort_stats(near, f">= {cut:.2f}%")
    low_c = cohort_stats(lower, f"< {cut:.2f}%")
    too_early = near_c["renewal_outcomes"]["Too Early"] + low_c["renewal_outcomes"]["Too Early"]
    who = f"Closed-won {segment} deals" if segment else "Closed-won deals"
    finding = (f"{who} at {near_c['discount_range']} discount: {_rate_text(near_c)}; "
               f"at {low_c['discount_range']}: {_rate_text(low_c)}. "
               f"Excludes {too_early} Too Early (closed under 12 months ago).")
    small = near_c["matured"] < SMALL_SAMPLE or low_c["matured"] < SMALL_SAMPLE
    if small:
        finding += f" Small sample: fewer than {SMALL_SAMPLE} matured deals in a cohort."
    return {"proposed_discount_pct": float(proposed_discount), "window_pct": float(window),
            "all": all_c, "near_proposed": near_c, "lower_discount": low_c,
            "finding": finding, "small_sample": small}


def comparables(sf, segment: str, discount: float, tier: str = None,
                window: float = DEFAULT_WINDOW) -> dict:
    soql = build_soql(segment, tier)
    records = sf.query_all(soql)["records"]
    if tier:
        records = [r for r in records if _tier_of(r) == tier]
    result = summarize(records, discount, window, segment)
    return {"segment": segment, "tier": tier, "source": "seeded closed Opportunities",
            "soql": soql, **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Comparable closed deals and renewal outcomes")
    parser.add_argument("--segment", required=True, choices=SEGMENTS)
    parser.add_argument("--discount", required=True, type=float,
                        help="proposed effective discount, percent")
    parser.add_argument("--tier", choices=TIERS, default=None)
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW,
                        help="near cohort = discount >= proposed - window (default 5)")
    args = parser.parse_args(argv)
    print(json.dumps(comparables(connect(), args.segment, args.discount, args.tier,
                                 args.window), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
