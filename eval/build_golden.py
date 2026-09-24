"""Build eval/golden/<scenario>.json from the user's hand-written eval/specs/<scenario>.yaml.

Values are copied from the spec, never improved:
  - expected_extraction fields as written (dates as ISO strings)
  - account_domain and rep_stated_segment from the spec's top-level keys
  - open_questions = expected_open_questions (field, text, blocking)
Any schema field the spec does not define (company_name always; company_headcount
unless expected_extraction lists it) gets a null value and is listed in
"_unscored" so eval/run_eval.py skips it. Golden citations are null: scoring
compares values, and hallucinations are checked against the deal files instead.

Run:  python eval/build_golden.py        (rewrites eval/golden/*.json)
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "eval" / "specs"
GOLDEN = ROOT / "eval" / "golden"
SCENARIOS = ["clean-midmarket", "conflicting-seats", "mis-segmented", "aggressive-discount"]
FIELDS = ["account_domain", "company_name", "rep_stated_segment", "products", "seat_count",
          "term_months", "start_date", "payment_terms", "requested_discount_pct", "ramp",
          "company_headcount", "contacts"]
TOP_LEVEL = ("account_domain", "rep_stated_segment")


def _plain(v):
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def golden(name: str, specs_dir: Path = SPECS) -> dict:
    spec = yaml.safe_load((Path(specs_dir) / f"{name}.yaml").read_text())
    exp = spec.get("expected_extraction") or {}
    doc = {"_source": f"eval/specs/{name}.yaml",
           "_note": "Golden values from the spec (hand-written); citations not scored.",
           "_unscored": [], "scenario": name}
    for field in FIELDS:
        if field in exp:
            v = exp[field]
        elif field in TOP_LEVEL and field in spec:
            v = spec[field]
        else:
            v = None
            doc["_unscored"].append(field)
        doc[field] = {"value": _plain(v), "source_citation": None, "confidence": "high"}
    doc["open_questions"] = [
        {"field": q["field"], "text": q["text"], "blocking": bool(q["blocking"])}
        for q in spec.get("expected_open_questions") or []]
    return doc


def main() -> int:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name in SCENARIOS:
        path = GOLDEN / f"{name}.json"
        path.write_text(json.dumps(golden(name), indent=2) + "\n")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
