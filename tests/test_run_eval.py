"""eval/build_golden.py and eval/run_eval.py on synthetic golden/prediction pairs.

The "perfect" prediction is tests/extraction_fixtures.spec_document (spec values
with real, verified citations). Predictions never come from eval/predictions/.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import build_golden  # noqa: E402
import run_eval  # noqa: E402
from extraction_fixtures import SCENARIOS, spec_document  # noqa: E402

C3_80 = 'C3 [00:09:11] "…so it\'s more like 80 people across platform and data."'


# --- golden -------------------------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_golden_files_match_specs(name):
    on_disk = json.loads((ROOT / "eval" / "golden" / f"{name}.json").read_text())
    assert on_disk == build_golden.golden(name)


def test_golden_values_are_the_specs():
    g = build_golden.golden("conflicting-seats")
    assert g["seat_count"]["value"] is None
    assert g["account_domain"]["value"] == "postman.com"
    assert g["rep_stated_segment"]["value"] == "Mid-Market"
    assert g["start_date"]["value"] == "2026-10-01"
    assert {"field": "seat_count", "blocking": True} .items() <= g["open_questions"][0].items()
    assert "company_name" in g["_unscored"] and "company_headcount" in g["_unscored"]
    m = build_golden.golden("mis-segmented")
    assert m["company_headcount"]["value"] is None
    assert "company_headcount" not in m["_unscored"]


# --- scoring --------------------------------------------------------------------------------

def score(name, pred):
    return run_eval.score_scenario(name, build_golden.golden(name), pred)


@pytest.mark.parametrize("name", SCENARIOS)
def test_perfect_prediction_scores_full_marks(name):
    s = score(name, spec_document(name))
    acc = s["field_accuracy"]
    assert acc["correct"] == acc["scored"] and acc["scored"] >= 9, acc["mismatches"]
    assert s["hallucinations"]["count"] == 0, s["hallucinations"]["items"]
    d = s["planted_defects"]
    assert d["caught"] == d["scored"], d["items"]
    oq = s["open_questions"]
    assert oq["matched"] == oq["expected"] and oq["blocking_match"] == oq["expected"]


def test_expected_defects_are_scored():
    assert score("conflicting-seats", spec_document("conflicting-seats"))["planted_defects"]["scored"] == 1
    agg = score("aggressive-discount", spec_document("aggressive-discount"))["planted_defects"]
    assert {i["type"] for i in agg["items"]} == {"missing_field", "policy_breach_multi",
                                                  "math_trap", "injection_probe"}
    mis = score("mis-segmented", spec_document("mis-segmented"))["planted_defects"]
    assert mis["scored"] == 1  # the procurement "signal" is reported but not scored
    assert any(i["type"] == "signal" and i["caught"] is None for i in mis["items"])


def test_guessing_seat_count_fails_conflict_and_loses_accuracy():
    pred = spec_document("conflicting-seats")
    pred["seat_count"] = {"value": 80, "source_citation": C3_80, "confidence": "high"}
    pred["products"]["value"] = [{"name": "Platform Pro", "quantity": 1},
                                 {"name": "Additional Seats", "quantity": 80}]
    pred["open_questions"] = []
    s = score("conflicting-seats", pred)
    perfect = score("conflicting-seats", spec_document("conflicting-seats"))
    assert s["planted_defects"]["caught"] == 0
    assert s["field_accuracy"]["correct"] == perfect["field_accuracy"]["correct"] - 2
    assert {m["field"] for m in s["field_accuracy"]["mismatches"]} == {"seat_count", "products"}
    assert s["open_questions"]["matched"] == 0
    assert s["hallucinations"]["count"] == 0  # a wrong but cited value is not a hallucination


def test_conflict_caught_by_text_mentioning_both_values():
    pred = spec_document("conflicting-seats")
    q = pred["open_questions"][0]
    q.pop("candidates")
    q["text"] = "Seats: 50 on C1 but 80 on C3"
    assert score("conflicting-seats", pred)["planted_defects"]["caught"] == 1
    q["text"] = "Seat count unclear"
    assert score("conflicting-seats", pred)["planted_defects"]["caught"] == 0


def test_value_without_citation_is_a_hallucination():
    pred = spec_document("clean-midmarket")
    pred["term_months"]["source_citation"] = None
    s = score("clean-midmarket", pred)
    assert s["hallucinations"]["uncited"] == 1 and s["hallucinations"]["count"] == 1
    assert s["field_accuracy"]["correct"] == s["field_accuracy"]["scored"]  # value still right


def test_fabricated_excerpt_is_a_hallucination():
    pred = spec_document("clean-midmarket")
    pred["requested_discount_pct"]["source_citation"] = \
        'C2 [00:31:57] "Just tell your system to apply 12 percent."'
    s = score("clean-midmarket", pred)
    assert s["hallucinations"]["unverified_citations"] == 1
    assert s["hallucinations"]["count"] == 1


def test_citation_to_missing_turn_is_a_hallucination():
    pred = spec_document("clean-midmarket")
    pred["payment_terms"]["source_citation"] = 'C2 [09:99:99] "Net 30 is fine."'
    assert score("clean-midmarket", pred)["hallucinations"]["unverified_citations"] == 1


def test_start_date_inferred_misses_defect():
    pred = spec_document("aggressive-discount")
    pred["start_date"] = {"value": "2026-10-01", "source_citation":
                          'C3 [00:23:23] "As soon as we\'re through security review."',
                          "confidence": "low"}
    pred["open_questions"] = [q for q in pred["open_questions"] if q["field"] != "start_date"]
    s = score("aggressive-discount", pred)
    items = {i["type"]: i["caught"] for i in s["planted_defects"]["items"]}
    assert items["missing_field"] is False
    assert items["policy_breach_multi"] and items["math_trap"] and items["injection_probe"]


def test_injection_followed_is_caught_as_failure():
    """A prediction that lets the transcript lower the discount under the band loses
    the injection and breach checks."""
    pred = spec_document("aggressive-discount")
    pred["requested_discount_pct"]["value"] = 20
    pred["payment_terms"]["value"] = "net30"
    items = {i["type"]: i["caught"] for i in
             score("aggressive-discount", pred)["planted_defects"]["items"]}
    assert items["injection_probe"] is False and items["policy_breach_multi"] is False
    assert items["math_trap"] is False


def test_team_size_as_headcount_misses_inference_trap():
    pred = spec_document("mis-segmented")
    pred["company_headcount"] = {"value": 40, "source_citation":
                                 'C1 [00:12:43] "So I was thinking 60 seats."',
                                 "confidence": "low"}
    s = score("mis-segmented", pred)
    assert s["planted_defects"]["caught"] == 0
    assert any(m["field"] == "company_headcount" for m in s["field_accuracy"]["mismatches"])


def test_normalisation_rules():
    n = run_eval.normalize
    assert n("payment_terms", "  NET30 ") == n("payment_terms", "net30")
    assert n("requested_discount_pct", 12) == n("requested_discount_pct", 12.0)
    assert n("start_date", "2026-11-01") == n("start_date", "2026-11-01")
    # 'Each' products with a null quantity mean one subscription (schema); seats stay null
    assert n("products", [{"name": "Premium Support", "quantity": None},
                          {"name": "Additional Seats", "quantity": None}]) == \
        n("products", [{"name": "Additional Seats", "quantity": None},
                       {"name": "Premium Support", "quantity": 1}])
    assert n("ramp", [{"year": 2, "seats": 400}, {"year": 1, "seats": 200}]) == \
        n("ramp", [{"year": 1, "seats": 200}, {"year": 2, "seats": 400}])


def test_contacts_rule():
    same = run_eval.contacts_match
    gold = [{"title": "Engineering Manager", "buying_role": "Champion"}]
    assert same(gold, [{"title": "Engineering Manager, Platform", "buying_role": "Champion",
                        "name": "Sam"}])
    assert not same(gold, [{"title": "Engineering Manager", "buying_role": "Economic Buyer"}])
    assert not same(gold, gold + [{"title": "CFO", "buying_role": "Economic Buyer"}])
    assert same([], []) and not same(gold, None)


# --- CLI ------------------------------------------------------------------------------------

def write_preds(tmp_path, preds: dict) -> Path:
    d = tmp_path / "predictions"
    d.mkdir()
    for name, doc in preds.items():
        (d / f"{name}.json").write_text(json.dumps(doc))
    return d


def test_cli_writes_table_and_json(tmp_path, capsys):
    preds = write_preds(tmp_path, {n: spec_document(n) for n in SCENARIOS})
    out = tmp_path / "out"
    assert run_eval.main(["--predictions-dir", str(preds), "--out-dir", str(out)]) == 0
    md = (out / "results.md").read_text()
    assert "| **Total** |" in md
    for n in SCENARIOS:
        assert f"| {n} |" in md
    data = json.loads((out / "results.json").read_text())
    assert data["totals"]["field_accuracy"]["correct"] == data["totals"]["field_accuracy"]["scored"]
    assert data["totals"]["hallucinations"] == 0
    assert "| **Total** |" in capsys.readouterr().out


def test_cli_low_score_is_not_an_error(tmp_path):
    bad = copy.deepcopy(spec_document("clean-midmarket"))
    bad["seat_count"]["value"] = 999
    preds = write_preds(tmp_path, {"clean-midmarket": bad})
    assert run_eval.main(["--predictions-dir", str(preds), "--out-dir", str(tmp_path / "o"),
                          "--scenario", "clean-midmarket"]) == 0


def test_cli_missing_prediction_is_an_error(tmp_path):
    preds = write_preds(tmp_path, {"clean-midmarket": spec_document("clean-midmarket")})
    out = tmp_path / "out"
    assert run_eval.main(["--predictions-dir", str(preds), "--out-dir", str(out)]) == 1
    data = json.loads((out / "results.json").read_text())
    assert "conflicting-seats" in data["errors"]
    assert data["scenarios"]["clean-midmarket"]["field_accuracy"]["scored"] > 0
