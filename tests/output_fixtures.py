"""Write an output/<scenario>/ folder (steps 1-4 JSON) for the renderer tests.

Numbers come from the real scripts (pricing.py, preflight.py) run on the
spec-derived extraction; Apollo and comparables are fixed stand-ins so the
tests never touch the network.
"""

import json
from pathlib import Path

import preflight
from extraction_fixtures import DOMAINS, load_spec, spec_document

EMPLOYEES = {"clean-midmarket": 1100, "conflicting-seats": 900, "mis-segmented": 5200,
             "aggressive-discount": 7800}

COMPARABLES = {
    "segment": "Enterprise", "tier": "Platform Enterprise",
    "source": "seeded closed Opportunities",
    "proposed_discount_pct": 40.0, "window_pct": 5.0,
    "near_proposed": {"discount_range": ">= 35.00%", "count": 4, "won": 3, "lost": 1,
                      "matured": 2, "churned": 1, "churn_rate_pct": 50.0,
                      "renewal_outcomes": {"Renewed": 1, "Expanded": 0, "Churned": 1,
                                           "Too Early": 1}},
    "lower_discount": {"discount_range": "< 35.00%", "count": 11, "won": 8, "lost": 3,
                       "matured": 7, "churned": 1, "churn_rate_pct": 14.29,
                       "renewal_outcomes": {"Renewed": 4, "Expanded": 2, "Churned": 1,
                                            "Too Early": 1}},
    "finding": ("Closed-won Enterprise deals at >= 35.00% discount: 1 of 2 with a renewal "
                "outcome churned (50.00%); at < 35.00%: 1 of 7 with a renewal outcome churned "
                "(14.29%). Excludes 2 Too Early (closed under 12 months ago). Small sample: "
                "fewer than 3 matured deals in a cohort."),
    "small_sample": True,
}


def apollo_for(name: str) -> dict:
    verified = load_spec(name)["expected_preflight"]["verified_segment"]
    return {"domain": DOMAINS[name], "name": spec_document(name)["company_name"]["value"],
            "employees": EMPLOYEES[name], "verified_segment": verified, "source": "cache"}


def write_outputs(root: Path, name: str, extraction: dict = None,
                  comparables: dict = None) -> Path:
    """Write extraction/apollo/pricing/preflight(/comparables) JSON; return the folder."""
    folder = Path(root) / name
    folder.mkdir(parents=True, exist_ok=True)
    ext = extraction or spec_document(name)
    apollo = apollo_for(name)
    pf = preflight.preflight_extraction(ext, apollo["verified_segment"])
    pf["apollo"] = apollo
    files = {"extraction.json": ext, "apollo.json": apollo, "pricing.json": pf["pricing"],
             "preflight.json": pf}
    if comparables is not None:
        files["comparables.json"] = comparables
    for fname, data in files.items():
        (folder / fname).write_text(json.dumps(data, indent=2))
    return folder
