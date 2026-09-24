"""Tests for schemas/deal_extraction.json and its contract with the Phase 3 scripts."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

import apollo_client
import preflight
import pricing
from extraction_fixtures import FIELDS, SCENARIOS, load_spec, spec_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "deal_extraction.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


def errors(schema, doc):
    v = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    return list(v.iter_errors(doc))


def assert_valid(schema, doc):
    errs = errors(schema, doc)
    assert not errs, [f"{list(e.absolute_path)}: {e.message}" for e in errs]


def assert_invalid(schema, doc):
    assert errors(schema, doc), "document should have been rejected"


# --- the schema itself -------------------------------------------------------------------

def test_schema_is_valid_draft_2020_12(schema):
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_requires_every_field_and_open_questions(schema):
    assert set(schema["required"]) >= set(FIELDS) | {"open_questions"}
    assert schema["additionalProperties"] is False


def test_product_enum_matches_price_books(schema):
    catalog = pricing.load_catalog()
    enum = schema["$defs"]["product"]["properties"]["name"]["enum"]
    assert sorted(enum) == sorted(catalog["products"])


def test_citation_format_is_documented(schema):
    text = json.dumps(schema)
    assert 'C3 [00:09:11]' in text and 'rep_notes: \\"' in text


# --- valid documents -----------------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_spec_documents_are_valid(schema, name):
    assert_valid(schema, spec_document(name))


@pytest.mark.parametrize("name", SCENARIOS)
def test_spec_documents_carry_the_spec_values(name):
    doc, exp = spec_document(name), load_spec(name)["expected_extraction"]
    for field, v in exp.items():
        got = doc[field]["value"]
        assert (got == v.isoformat()) if hasattr(v, "isoformat") else got == v, field


def test_metadata_is_optional(schema):
    doc = spec_document("clean-midmarket")
    del doc["scenario"], doc["source_files"]
    assert_valid(schema, doc)


def test_empty_open_questions_ok(schema):
    doc = spec_document("clean-midmarket")
    assert doc["open_questions"] == []
    assert_valid(schema, doc)


def test_multiple_citations_and_header_citation_ok(schema):
    doc = spec_document("clean-midmarket")
    assert " | " in doc["contacts"]["source_citation"]
    assert "[header]" in doc["contacts"]["source_citation"]
    assert_valid(schema, doc)


def test_non_net_payment_terms_are_allowed_as_text(schema):
    # preflight treats unparseable terms as non-standard (a breach), so keep them.
    doc = spec_document("clean-midmarket")
    doc["payment_terms"]["value"] = "50% upfront, balance net 45"
    assert_valid(schema, doc)


# --- invalid documents ----------------------------------------------------------------------

def mutate(fn, name="clean-midmarket"):
    doc = copy.deepcopy(spec_document(name))
    fn(doc)
    return doc


@pytest.mark.parametrize("fn", [
    pytest.param(lambda d: d["seat_count"].pop("source_citation"), id="missing-citation-key"),
    pytest.param(lambda d: d["seat_count"].pop("confidence"), id="missing-confidence-key"),
    pytest.param(lambda d: d["seat_count"].pop("value"), id="missing-value-key"),
    pytest.param(lambda d: d["seat_count"].update(source_citation=None), id="value-without-citation"),
    pytest.param(lambda d: d["start_date"].update(value=None), id="null-value-with-citation"),
    pytest.param(lambda d: d["seat_count"].update(value="120"), id="seat-count-string"),
    pytest.param(lambda d: d["seat_count"].update(value=0), id="seat-count-zero"),
    pytest.param(lambda d: d["term_months"].update(value=24.5), id="term-float"),
    pytest.param(lambda d: d["seat_count"].update(confidence="certain"), id="bad-confidence"),
    pytest.param(lambda d: d["products"]["value"][0].update(name="Platform Ultra"), id="bad-product"),
    pytest.param(lambda d: d["products"]["value"][0].update(quantity="1"), id="product-qty-string"),
    pytest.param(lambda d: d["products"].update(value=[]), id="empty-products"),
    pytest.param(lambda d: d["contacts"]["value"][0].update(buying_role="Decision Maker"), id="bad-role"),
    pytest.param(lambda d: d["rep_stated_segment"].update(value="Mid Market"), id="bad-segment"),
    pytest.param(lambda d: d["start_date"].update(value="November 1"), id="start-not-iso"),
    pytest.param(lambda d: d["start_date"].update(value="2026-13-01"), id="start-bad-month"),
    pytest.param(lambda d: d["requested_discount_pct"].update(value=140), id="discount-over-100"),
    pytest.param(lambda d: d["requested_discount_pct"].update(value="12%"), id="discount-string"),
    pytest.param(lambda d: d.update(notes="x"), id="extra-top-level-property"),
    pytest.param(lambda d: d["seat_count"].update(reasoning="x"), id="extra-field-property"),
    pytest.param(lambda d: d["products"]["value"][0].update(price=1), id="extra-product-property"),
    pytest.param(lambda d: d.pop("open_questions"), id="missing-open-questions"),
    pytest.param(lambda d: d.pop("start_date"), id="missing-field"),
    pytest.param(lambda d: d["seat_count"].update(source_citation="the first call"),
                 id="citation-free-text"),
    pytest.param(lambda d: d["seat_count"].update(source_citation='C1 [8:20] "about 120"'),
                 id="citation-bad-timestamp"),
    pytest.param(lambda d: d["seat_count"].update(source_citation='C1 [00:08:20] about 120'),
                 id="citation-unquoted"),
    pytest.param(lambda d: d["open_questions"].append({"field": "seat_count", "text": "x"}),
                 id="question-missing-blocking"),
    pytest.param(lambda d: d["open_questions"].append(
        {"field": "seat_count", "text": "x", "blocking": "yes"}), id="question-blocking-string"),
    pytest.param(lambda d: d["open_questions"].append(
        {"field": "seat_count", "text": "x", "blocking": True,
         "candidates": [{"value": 50}]}), id="candidate-without-citation"),
])
def test_invalid_documents_rejected(schema, fn):
    assert_invalid(schema, mutate(fn))


def test_ramp_step_types(schema):
    assert_invalid(schema, mutate(lambda d: d["ramp"]["value"][1].update(seats="400"),
                                  "aggressive-discount"))
    assert_invalid(schema, mutate(lambda d: d["ramp"]["value"][1].update(extra=1),
                                  "aggressive-discount"))


# --- contract with pricing.py and preflight.py ------------------------------------------------

def test_clean_midmarket_prices_to_spec_tcv(schema, tmp_path, capsys):
    doc = spec_document("clean-midmarket")
    assert_valid(schema, doc)
    # 34,200 x 2 + 540 x 120 x 2 + 25,000 = 223,000 list; x 0.88 = 196,240.00
    r = pricing.price_extraction(doc, "Mid-Market")
    assert r["status"] == "priced"
    assert r["segment"] == "Mid-Market"
    assert r["totals"]["tcv"] == 196240.00
    assert r["totals"]["list_tcv"] == 223000.00
    # and through the CLI the skill runs
    path = tmp_path / "extraction.json"
    path.write_text(json.dumps(doc))
    assert pricing.main([str(path), "--segment", "Mid-Market"]) == 0
    assert json.loads(capsys.readouterr().out)["totals"]["tcv"] == 196240.00


def test_conflicting_seats_does_not_price(schema):
    doc = spec_document("conflicting-seats")
    r = pricing.price_extraction(doc, "Mid-Market")
    assert r["status"] == "blocked" and "seat_count" in r["blocked_fields"]


@pytest.fixture
def no_live_apollo(monkeypatch):
    def refuse(domain):
        raise AssertionError(f"live Apollo call for {domain}; the cache should be used")
    monkeypatch.setattr(apollo_client, "enrich_organization", refuse)


@pytest.mark.parametrize("name", SCENARIOS)
def test_preflight_on_spec_documents_matches_spec(schema, no_live_apollo, name):
    doc = spec_document(name)
    assert_valid(schema, doc)
    expected = load_spec(name)["expected_preflight"]
    r = preflight.run(doc)  # verified segment from data/cache (no credits)
    assert r["apollo"]["source"] == "cache"
    assert r["verified_segment"] == expected["verified_segment"]
    assert r["segment_mismatch"] == expected["segment_mismatch"]
    assert r["approval_level_required"] == expected["approval_level_required"]
    assert r["preflight_status"] == expected["preflight_status"]
    assert sorted(r["thresholds_breached"]) == sorted(expected["thresholds_breached"])
