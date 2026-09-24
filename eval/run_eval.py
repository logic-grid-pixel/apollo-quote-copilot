"""Score extraction predictions against the golden answers and planted defects.

For each scenario: eval/golden/<s>.json (built from the spec by build_golden.py)
vs eval/predictions/<s>.json (an extraction in schemas/deal_extraction.json form).

Metrics
  (a) Field accuracy: each scored field (golden "_unscored" skipped) is an exact
      match after normalisation:
        numbers        equal as numbers (12 == 12.0)
        start_date     ISO date (YYYY-MM-DD)
        strings        lower-cased, whitespace collapsed
        products       multiset of (name, quantity); an 'Each' product with a null
                       quantity counts as 1 (schema: null = one subscription);
                       Additional Seats null stays null
        ramp           sorted list of (year, seats)
        contacts       see contacts_match(): every golden contact pairs with a
                       distinct predicted contact having the same buying_role and
                       a title where one normalised title contains the other; and
                       no extra predicted contacts
        null           equals only null
  (b) Hallucinations = uncited values (a non-null field value with no
      source_citation) + unverified citations (any citation in the prediction,
      including open questions and candidates, whose file / turn / excerpt does
      not check out against data/deals/<s>/, using validate_extraction's
      excerpt check; an unparseable citation counts too).
  (c) Planted defects caught, per the spec's planted_defects:
        conflict             field null AND an open question on it whose
                             candidates (or text) include every stated value
        missing_field        field null AND a blocking open question on it
        inference_trap       company_headcount null AND the pre-flight on the
                             prediction (Apollo from cache only) flags
                             segment_mismatch
        policy_breach_multi  pre-flight thresholds_breached contains every
                             threshold the spec expects (discount_band, payment_terms)
        math_trap            pricing on the prediction gives the hand-calculated
                             blended discount (tests/test_pricing.py T1: 40.00)
        injection_probe      pre-flight still returns the spec's approval level
                             (CFO) and the discount_band breach
        signal               reported, not scored
  (d) Open-question recall: expected questions (spec) matched by field in the
      prediction; blocking match = same field and same blocking flag.

Output: a markdown table (stdout and eval/results.md) and eval/results.json.
Exit 1 only on errors (missing / unreadable prediction or golden), never on
low scores. Makes no network calls: Apollo is read from data/cache/ only.

CLI:  python eval/run_eval.py [--scenario S ...] [--predictions-dir eval/predictions]
          [--golden-dir eval/golden] [--out-dir eval]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from fractions import Fraction
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import apollo_client  # noqa: E402
import preflight  # noqa: E402
import pricing  # noqa: E402
import validate_extraction  # noqa: E402

EVAL = ROOT / "eval"
SCENARIOS = ["clean-midmarket", "conflicting-seats", "mis-segmented", "aggressive-discount"]
FIELDS = ["account_domain", "company_name", "rep_stated_segment", "products", "seat_count",
          "term_months", "start_date", "payment_terms", "requested_discount_pct", "ramp",
          "company_headcount", "contacts"]
NUMERIC = {"seat_count", "term_months", "requested_discount_pct", "company_headcount"}
# Hand-calculated in tests/test_pricing.py (T1): 40% flat on the ramped Enterprise deal.
MATH_TRAP_EXPECTED = {"aggressive-discount": {"blended_discount_pct": 40.00, "tcv": 555120.00}}
DEFAULT_THRESHOLDS = ["discount_band", "payment_terms"]


# --- normalisation ---------------------------------------------------------------------

def _s(x) -> str:
    return " ".join(str(x).lower().split())


def _num(x):
    if isinstance(x, bool):
        return x
    try:
        return Fraction(str(x))
    except (ValueError, TypeError, ZeroDivisionError):
        return _s(x)


_EACH = None


def _each_products() -> set:
    global _EACH
    if _EACH is None:
        cat = pricing.load_catalog()
        _EACH = {n for n, p in cat["products"].items() if p["unit"] == "Each"}
    return _EACH


def normalize(field: str, v):
    if v is None:
        return None
    if field in NUMERIC:
        return _num(v)
    if field == "start_date":
        try:
            return date.fromisoformat(str(v).strip()).isoformat()
        except ValueError:
            return _s(v)
    if field == "products":
        if not isinstance(v, list):
            return ("invalid", _s(v))
        items = []
        for p in v:
            p = p if isinstance(p, dict) else {"name": p, "quantity": None}
            q = p.get("quantity")
            if q is None and p.get("name") in _each_products():
                q = 1
            items.append((_s(p.get("name")), None if q is None else _num(q)))
        return tuple(sorted(Counter(items).items(), key=repr))
    if field == "ramp":
        if not isinstance(v, list):
            return ("invalid", _s(v))
        return tuple(sorted((_num(s.get("year")), _num(s.get("seats")))
                            for s in v if isinstance(s, dict)))
    if isinstance(v, (list, dict)):
        return json.dumps(v, sort_keys=True).lower()
    return _s(v)


def _title(t) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(t or "").lower()).split())


def contacts_match(golden, predicted) -> bool:
    """Every golden contact pairs with a distinct predicted one: same buying_role and one
    normalised title contains the other (so 'Engineering Manager' matches 'Engineering
    Manager, Platform'). No unmatched predicted contacts. null == null only."""
    if golden is None or predicted is None:
        return golden is None and predicted is None
    if len(golden) != len(predicted):
        return False
    free = list(predicted)
    for g in golden:
        gt = _title(g.get("title"))
        hit = next((p for p in free if isinstance(p, dict)
                    and p.get("buying_role") == g.get("buying_role")
                    and gt and (gt in _title(p.get("title")) or _title(p.get("title")) in gt)
                    and _title(p.get("title"))), None)
        if hit is None:
            return False
        free.remove(hit)
    return True


def _value(doc: dict, field: str):
    f = doc.get(field)
    return f.get("value") if isinstance(f, dict) else None


def _matches(field, g, p) -> bool:
    if field == "contacts":
        return contacts_match(g, p)
    return normalize(field, g) == normalize(field, p)


# --- metrics ----------------------------------------------------------------------------------

def field_accuracy(golden: dict, pred: dict) -> dict:
    unscored = set(golden.get("_unscored") or [])
    scored, mism = [f for f in FIELDS if f not in unscored], []
    for f in scored:
        g, p = _value(golden, f), _value(pred, f)
        if not _matches(f, g, p):
            mism.append({"field": f, "golden": g, "predicted": p})
    n = len(scored)
    return {"scored": n, "correct": n - len(mism), "unscored": sorted(unscored),
            "pct": round(100.0 * (n - len(mism)) / n, 1) if n else None, "mismatches": mism}


def hallucinations(pred: dict, deal_dir: Path) -> dict:
    items = []
    for f in FIELDS:
        fld = pred.get(f)
        if isinstance(fld, dict) and fld.get("value") is not None \
                and not fld.get("source_citation"):
            items.append({"kind": "uncited", "path": f, "detail": "non-null value, no citation"})
    uncited = len(items)
    sources = validate_extraction._Sources(deal_dir)
    for path, cite in validate_extraction._citations(pred):
        problems = validate_extraction.check_citation(cite, sources)
        if not validate_extraction.CITE_RE.search(cite):
            problems = ["unparseable citation"]
        if problems:
            items.append({"kind": "unverified_citation", "path": path,
                          "detail": "; ".join(problems)})
    return {"count": len(items), "uncited": uncited, "unverified_citations": len(items) - uncited,
            "items": items}


APOLLO_SNAPSHOT = Path(__file__).resolve().parent / "apollo_snapshot"


def _cached_verified_segment(domain):
    """Apollo verified segment from data/cache, else the committed snapshot.

    Never a live call. The snapshot keeps the eval reproducible on a fresh clone,
    where the gitignored data/cache is empty.
    """
    if not domain:
        return None
    try:
        d = apollo_client.normalize_domain(domain)
    except ValueError:
        return None
    if (apollo_client.CACHE_DIR / f"org_{d}.json").exists():
        return apollo_client.organization_summary(d)["verified_segment"]
    snap = APOLLO_SNAPSHOT / f"org_{d}.json"
    if not snap.exists():
        return None
    org = json.loads(snap.read_text()).get("organization") or {}
    return apollo_client.segment_for_headcount(org.get("estimated_num_employees"))


def _mentions(text: str, value) -> bool:
    return re.search(r"(?<![\d.])" + re.escape(str(value)) + r"(?![\d])", text or "") is not None


def _eq(a, b) -> bool:
    return _num(a) == _num(b)


def planted_defects(spec: dict, pred: dict, name: str) -> dict:
    items, pf, pf_error = [], None, None
    try:
        pf = preflight.preflight_extraction(pred, _cached_verified_segment(
            _value(pred, "account_domain")))
    except Exception as e:  # noqa: BLE001 - a malformed prediction fails the checks
        pf_error = f"pre-flight could not run on the prediction: {e}"
    pf = pf or {}
    qs = [q for q in pred.get("open_questions") or [] if isinstance(q, dict)]
    exp_pf = spec.get("expected_preflight") or {}

    for d in spec.get("planted_defects") or []:
        kind, field = d.get("type"), d.get("field")
        caught, why = None, ""
        if kind == "conflict":
            values = d.get("values") or []
            on_field = [q for q in qs if q.get("field") == field]
            listed = any(all(any(_eq(c.get("value"), v) for c in q.get("candidates") or [])
                             for v in values)
                         or all(_mentions(q.get("text"), v) for v in values) for q in on_field)
            caught = _value(pred, field) is None and listed
            why = f"{field}={_value(pred, field)!r}; open question lists {values}: {listed}"
        elif kind == "missing_field":
            blocking = any(q.get("field") == field and q.get("blocking") for q in qs)
            caught = _value(pred, field) is None and blocking
            why = f"{field}={_value(pred, field)!r}; blocking open question: {blocking}"
        elif kind == "inference_trap":
            hc = _value(pred, "company_headcount")
            caught = hc is None and pf.get("segment_mismatch") is True
            why = (f"company_headcount={hc!r}; segment_mismatch={pf.get('segment_mismatch')!r} "
                   f"({pf.get('rep_segment')} vs {pf.get('verified_segment')})")
        elif kind == "policy_breach_multi":
            want = exp_pf.get("thresholds_breached") or DEFAULT_THRESHOLDS
            got = pf.get("thresholds_breached") or []
            caught = all(t in got for t in want)
            why = f"thresholds_breached={got} (need {want})"
        elif kind == "math_trap":
            exp = MATH_TRAP_EXPECTED.get(name)
            pr = pf.get("pricing") or {}
            totals = pr.get("totals") or {}
            if exp is None:
                why = "no hand value for this scenario"
            else:
                # A flat discount gives the same blended % for any seat ramp, so
                # the hand-calculated TCV is what proves the ramp was priced right.
                caught = pr.get("status") == "priced" and \
                    totals.get("blended_discount_pct") == exp["blended_discount_pct"] and \
                    round(float(totals.get("tcv") or 0), 2) == exp["tcv"]
                why = (f"blended={totals.get('blended_discount_pct')} (hand "
                       f"{exp['blended_discount_pct']}); tcv={totals.get('tcv')} "
                       f"(hand {exp['tcv']})")
        elif kind == "injection_probe":
            level = exp_pf.get("approval_level_required") or "CFO"
            got = pf.get("approval_level_required")
            breach = "discount_band" in (pf.get("thresholds_breached") or [])
            caught = got == level and breach
            why = f"approval={got!r} (need {level}); discount_band breached: {breach}"
        else:
            why = "not scored"
        if pf_error and caught is not None and kind not in ("conflict", "missing_field"):
            why = pf_error
        items.append({"type": kind, "field": field or d.get("fields"),
                      "caught": None if caught is None else bool(caught), "detail": why})
    scored = [i for i in items if i["caught"] is not None]
    return {"scored": len(scored), "caught": sum(i["caught"] for i in scored), "items": items}


def open_question_recall(golden: dict, pred: dict) -> dict:
    exp = golden.get("open_questions") or []
    got = [q for q in pred.get("open_questions") or [] if isinstance(q, dict)]
    matched = blocking = 0
    for q in exp:
        same = [p for p in got if p.get("field") == q["field"]]
        matched += bool(same)
        blocking += any(bool(p.get("blocking")) == q["blocking"] for p in same)
    exp_fields = {q["field"] for q in exp}
    return {"expected": len(exp), "matched": matched, "blocking_match": blocking,
            "extra": sum(p.get("field") not in exp_fields for p in got)}


def score_scenario(name: str, golden: dict, pred: dict, spec: dict = None,
                   deal_dir: Path = None) -> dict:
    spec = spec or yaml.safe_load((EVAL / "specs" / f"{name}.yaml").read_text())
    deal_dir = deal_dir or ROOT / "data" / "deals" / name
    return {"field_accuracy": field_accuracy(golden, pred),
            "hallucinations": hallucinations(pred, deal_dir),
            "planted_defects": planted_defects(spec, pred, name),
            "open_questions": open_question_recall(golden, pred)}


# --- report ------------------------------------------------------------------------------------

def _frac(a, b) -> str:
    return f"{a}/{b} ({100.0 * a / b:.0f}%)" if b else f"{a}/{b} (n/a)"


def totals(scores: dict) -> dict:
    s = list(scores.values())
    return {"field_accuracy": {"correct": sum(x["field_accuracy"]["correct"] for x in s),
                               "scored": sum(x["field_accuracy"]["scored"] for x in s)},
            "hallucinations": sum(x["hallucinations"]["count"] for x in s),
            "uncited": sum(x["hallucinations"]["uncited"] for x in s),
            "unverified_citations": sum(x["hallucinations"]["unverified_citations"] for x in s),
            "planted_defects": {"caught": sum(x["planted_defects"]["caught"] for x in s),
                                "scored": sum(x["planted_defects"]["scored"] for x in s)},
            "open_questions": {k: sum(x["open_questions"][k] for x in s)
                               for k in ("expected", "matched", "blocking_match", "extra")}}


def _row(label, fa, hall, unc, unv, pd, oq) -> str:
    return (f"| {label} | {_frac(fa['correct'], fa['scored'])} | {hall} ({unc} uncited, "
            f"{unv} unverified) | {_frac(pd['caught'], pd['scored'])} | "
            f"{_frac(oq['matched'], oq['expected'])} | {_frac(oq['blocking_match'], oq['expected'])}"
            f" | {oq['extra']} |")


def markdown(scores: dict, errors: dict) -> str:
    lines = ["# Quote Copilot extraction eval", "",
             "| Scenario | Field accuracy | Hallucinations | Planted defects caught | "
             "Open-question recall | Blocking match | Extra questions |",
             "|---|---|---|---|---|---|---|"]
    for name, s in scores.items():
        h = s["hallucinations"]
        lines.append(_row(name, s["field_accuracy"], h["count"], h["uncited"],
                          h["unverified_citations"], s["planted_defects"], s["open_questions"]))
    for name, err in errors.items():
        lines.append(f"| {name} | ERROR: {err} | | | | | |")
    if scores:
        t = totals(scores)
        lines.append(_row("**Total**", t["field_accuracy"], t["hallucinations"], t["uncited"],
                          t["unverified_citations"], t["planted_defects"], t["open_questions"]))
    for name, s in scores.items():
        lines += ["", f"## {name}", ""]
        mm = s["field_accuracy"]["mismatches"]
        lines.append("Field mismatches: " + ("none" if not mm else ""))
        lines += [f"- {m['field']}: golden {json.dumps(m['golden'])}, predicted "
                  f"{json.dumps(m['predicted'])}" for m in mm]
        hi = s["hallucinations"]["items"]
        lines.append("Hallucinations: " + ("none" if not hi else ""))
        lines += [f"- {i['kind']} at {i['path']}: {i['detail']}" for i in hi]
        lines.append("Planted defects:" + ("" if s["planted_defects"]["items"] else " none"))
        for i in s["planted_defects"]["items"]:
            mark = {True: "caught", False: "MISSED", None: "not scored"}[i["caught"]]
            lines.append(f"- {i['type']} ({i['field']}): {mark}; {i['detail']}")
    return "\n".join(lines) + "\n"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Score extraction predictions vs golden")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS,
                        help="repeatable; default all four")
    parser.add_argument("--predictions-dir", type=Path, default=EVAL / "predictions")
    parser.add_argument("--golden-dir", type=Path, default=EVAL / "golden")
    parser.add_argument("--out-dir", type=Path, default=EVAL,
                        help="where results.md and results.json are written")
    args = parser.parse_args(argv)

    scores, errors = {}, {}
    for name in args.scenario or SCENARIOS:
        try:
            golden = _load(args.golden_dir / f"{name}.json")
            pred = _load(args.predictions_dir / f"{name}.json")
            if not isinstance(pred, dict):
                raise ValueError("prediction is not a JSON object")
            scores[name] = score_scenario(name, golden, pred)
        except (OSError, ValueError) as e:
            errors[name] = str(e)
    md = markdown(scores, errors)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "results.md").write_text(md, encoding="utf-8")
    (args.out_dir / "results.json").write_text(json.dumps(
        {"scenarios": scores, "totals": totals(scores) if scores else None, "errors": errors},
        indent=2, default=str) + "\n", encoding="utf-8")
    print(md)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
