"""Tests for scripts/validate_extraction.py (schema + citation checks)."""

import copy
import json

import pytest

import validate_extraction as ve
from extraction_fixtures import DEALS, SCENARIOS, spec_document


def messages(errs):
    return " / ".join(f"{e['path']}: {e['message']}" for e in errs)


@pytest.mark.parametrize("name", SCENARIOS)
def test_spec_documents_pass_including_citations(name):
    errs = ve.validate(spec_document(name), deal_dir=DEALS / name)
    assert errs == [], messages(errs)


def test_schema_error_reported_with_path():
    doc = spec_document("clean-midmarket")
    doc["seat_count"]["value"] = "120"
    errs = ve.validate(doc)
    assert any(e["path"] == "seat_count.value" for e in errs), messages(errs)


def test_citation_quote_not_in_file_is_rejected():
    doc = spec_document("clean-midmarket")
    doc["seat_count"]["source_citation"] = 'C1 [00:08:20] "about 150 engineers"'
    errs = ve.validate(doc, deal_dir=DEALS / "clean-midmarket")
    assert any(e["path"] == "seat_count.source_citation" and "not found" in e["message"]
               for e in errs), messages(errs)


def test_citation_wrong_timestamp_is_rejected():
    doc = spec_document("clean-midmarket")
    doc["seat_count"]["source_citation"] = 'C1 [00:00:01] "about 120 engineers"'
    errs = ve.validate(doc, deal_dir=DEALS / "clean-midmarket")
    assert any("00:00:01" in e["message"] for e in errs), messages(errs)


def test_citation_unknown_call_is_rejected():
    doc = spec_document("clean-midmarket")
    doc["seat_count"]["source_citation"] = 'C9 [00:08:20] "about 120 engineers"'
    errs = ve.validate(doc, deal_dir=DEALS / "clean-midmarket")
    assert any("C9" in e["message"] for e in errs), messages(errs)


def test_candidate_citations_are_checked():
    doc = copy.deepcopy(spec_document("conflicting-seats"))
    doc["open_questions"][0]["candidates"][1]["source_citation"] = 'C3 [00:09:11] "90 people"'
    errs = ve.validate(doc, deal_dir=DEALS / "conflicting-seats")
    assert any(e["path"].startswith("open_questions.0.candidates.1") for e in errs), messages(errs)


def test_conflict_candidates_require_null_value():
    # Picking one of two conflicting statements is not allowed.
    doc = copy.deepcopy(spec_document("conflicting-seats"))
    doc["seat_count"] = {"value": 80, "confidence": "medium",
                         "source_citation": doc["open_questions"][0]["candidates"][1]["source_citation"]}
    errs = ve.validate(doc)
    assert any(e["path"] == "seat_count.value" and "candidates" in e["message"]
               for e in errs), messages(errs)


def test_quotes_match_ignoring_quote_style_and_ellipsis():
    doc = spec_document("aggressive-discount")
    doc["open_questions"][0]["source_citation"] = "rep_notes: \"'teaser rate worthless'\""
    assert ve.validate(doc, deal_dir=DEALS / "aggressive-discount") == []


def test_cli_ok_and_failure(tmp_path, capsys):
    path = tmp_path / "extraction.json"
    path.write_text(json.dumps(spec_document("clean-midmarket")))
    assert ve.main([str(path), "--deal-dir", str(DEALS / "clean-midmarket")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"valid": True, "errors": [], "file": str(path)}

    bad = spec_document("clean-midmarket")
    bad["seat_count"]["source_citation"] = None
    path.write_text(json.dumps(bad))
    assert ve.main([str(path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["valid"] is False and out["errors"]


def test_cli_rejects_non_json(tmp_path, capsys):
    path = tmp_path / "extraction.json"
    path.write_text("{not json")
    assert ve.main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False
