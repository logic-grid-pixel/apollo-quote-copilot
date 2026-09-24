"""Unit tests for scripts/preflight.py and the approval policy it reads.

Scenario tests build the extraction from each eval/specs/*.yaml expected_extraction
and assert that spec's expected_preflight. Numbers in suggested alternatives are
hand-calculated literals (see comments), never copied from code output.
"""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

import preflight
import pricing

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "eval" / "specs"
DOMAINS = {"clean-midmarket": "retool.com", "conflicting-seats": "postman.com",
           "mis-segmented": "mongodb.com", "aggressive-discount": "snowflake.com"}
SCENARIOS = list(DOMAINS)


def wrap(value, citation="C1"):
    return {"value": value, "source_citation": citation if value is not None else None,
            "confidence": "high"}


def load_spec(name):
    return yaml.safe_load((SPECS / f"{name}.yaml").read_text())


def extraction_from_spec(name):
    """The extraction contract shape, filled from the spec's expected_extraction."""
    spec = load_spec(name)
    exp = spec["expected_extraction"]
    ext = {"account_domain": wrap(DOMAINS[name]),
           "company_name": wrap(None),
           "rep_stated_segment": wrap(spec["rep_stated_segment"], "CRM"),
           "company_headcount": wrap(exp.get("company_headcount")),
           "contacts": wrap(exp.get("contacts") or [])}
    for field in ("products", "seat_count", "term_months", "start_date", "payment_terms",
                  "requested_discount_pct", "ramp"):
        v = exp.get(field)
        if isinstance(v, date):
            v = v.isoformat()
        ext[field] = wrap(v)
    ext["open_questions"] = spec.get("expected_open_questions") or []
    return ext


def run(name, **kw):
    spec = load_spec(name)
    return preflight.preflight_extraction(
        extraction_from_spec(name), spec["expected_preflight"]["verified_segment"], **kw)


# --- the four demo scenarios ---------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_matches_spec(name):
    expected = load_spec(name)["expected_preflight"]
    r = run(name)
    assert r["verified_segment"] == expected["verified_segment"]
    assert r["segment_mismatch"] == expected["segment_mismatch"]
    assert r["approval_level_required"] == expected["approval_level_required"]
    assert r["preflight_status"] == expected["preflight_status"]
    assert sorted(r["thresholds_breached"]) == sorted(expected["thresholds_breached"])
    if "rep_segment" in expected:
        assert r["rep_segment"] == expected["rep_segment"]


def test_clean_midmarket_is_ready_with_no_alternative():
    r = run("clean-midmarket")
    assert r["effective_discount_pct"] == 12.00
    assert r["effective_discount_source"] == "computed"
    assert r["suggested_alternative"] is None


def test_conflicting_seats_uses_requested_discount_when_unpriceable():
    r = run("conflicting-seats")
    assert r["effective_discount_pct"] == 15.00
    assert r["effective_discount_source"] == "requested"
    assert "seat_count" in r["blocked_fields"]
    types = [o["type"] for o in r["suggested_alternative"]["options"]]
    assert types[0] == "resolve_open_questions"
    assert "discount_at_rep_limit" in types
    rep_opt = next(o for o in r["suggested_alternative"]["options"]
                   if o["type"] == "discount_at_rep_limit")
    assert rep_opt["discount_pct"] == 12 and rep_opt["approval_level"] == "Rep"


def test_mis_segmented_would_need_manager_on_rep_segment():
    r = run("mis-segmented")
    assert r["rep_segment"] == "SMB"
    assert r["band_segment"] == "Enterprise"
    assert r["approval_level_on_rep_segment"] == "Manager"
    opt = next(o for o in r["suggested_alternative"]["options"]
               if o["type"] == "requote_on_verified_segment")
    # Hand calc, 12 months at 18%:
    #   SMB book:        36,000 + 60*600 = 72,000 -> x0.82 = 59,040.00
    #   Enterprise book: 32,400 + 60*480 = 61,200 -> x0.82 = 50,184.00
    assert opt["price_book"] == "Enterprise"
    assert opt["tcv_on_rep_segment_book"] == 59040.00
    assert opt["tcv_on_verified_segment_book"] == 50184.00
    assert opt["tcv_difference"] == -8856.00


def test_aggressive_discount_alternative_holds_at_ceiling():
    r = run("aggressive-discount")
    assert r["effective_discount_pct"] == 40.00
    assert "start_date" in r["blocked_fields"]
    opts = {o["type"]: o for o in r["suggested_alternative"]["options"]}
    hold = opts["hold_discount_at_ceiling"]
    # Hand calc: list TCV 925,200 (see test_pricing T1).
    #   at 40%: 555,120.00   at 35% ceiling: 925,200 * 0.65 = 601,380.00
    #   difference 46,260.00 back to us
    assert hold["discount_pct"] == 35
    assert hold["tcv_at_requested"] == 555120.00
    assert hold["tcv_at_alternative"] == 601380.00
    assert hold["tcv_difference"] == 46260.00
    assert hold["approval_level"] == "VP"          # 35% is inside the Enterprise VP band
    assert opts["standard_payment_terms"]["payment_terms"] == "net30"
    assert r["suggested_alternative"]["approval_level_if_all_applied"] == "VP"


# --- band boundaries (inclusive upper bounds) -----------------------------------------

@pytest.mark.parametrize("segment, pct, level, breached", [
    ("SMB", "10.00", "Rep", False), ("SMB", "10.01", "Manager", False),
    ("SMB", "20.00", "Manager", False), ("SMB", "20.01", "VP", False),
    ("SMB", "25.00", "VP", False), ("SMB", "25.01", "CFO", True),
    ("Mid-Market", "0", "Rep", False),
    ("Mid-Market", "12.00", "Rep", False), ("Mid-Market", "12.01", "Manager", False),
    ("Mid-Market", "20.00", "Manager", False), ("Mid-Market", "20.01", "VP", False),
    ("Mid-Market", "30.00", "VP", False), ("Mid-Market", "30.01", "CFO", True),
    ("Enterprise", "20.00", "Rep", False), ("Enterprise", "20.01", "Manager", False),
    ("Enterprise", "28.00", "Manager", False), ("Enterprise", "28.01", "VP", False),
    ("Enterprise", "35.00", "VP", False), ("Enterprise", "35.01", "CFO", True),
])
def test_band_boundaries(segment, pct, level, breached):
    policy = preflight.load_policy()
    assert preflight.discount_approval(policy, segment, pct) == (level, breached)


def test_boundary_uses_exact_value_not_rounded():
    policy = preflight.load_policy()
    assert preflight.discount_approval(policy, "Mid-Market", "12.001") == ("Manager", False)


def base_eval(**overrides):
    kw = dict(rep_segment="Mid-Market", verified_segment="Mid-Market",
              effective_discount_pct=10, payment_terms="net30", blocked_fields=[])
    kw.update(overrides)
    return preflight.evaluate(preflight.load_policy(), **kw)


@pytest.mark.parametrize("terms, breached, level", [
    ("net30", False, "Rep"), ("Net 30", False, "Rep"), ("net15", False, "Rep"),
    ("net45", True, "VP"), ("net60", True, "VP"), ("net 90", True, "VP"),
    ("quarterly in arrears", True, "VP"),
])
def test_payment_terms(terms, breached, level):
    r = base_eval(payment_terms=terms)
    assert ("payment_terms" in r["thresholds_breached"]) == breached
    assert r["approval_level_required"] == level
    assert r["preflight_status"] == ("Needs Approval" if breached else "Ready")


def test_payment_terms_never_lower_a_higher_discount_level():
    r = base_eval(effective_discount_pct=31, payment_terms="net60")
    assert r["approval_level_required"] == "CFO"
    assert sorted(r["thresholds_breached"]) == ["discount_band", "payment_terms"]


def test_null_payment_terms_is_noted_not_breached():
    r = base_eval(payment_terms=None)
    assert r["thresholds_breached"] == []
    assert any("payment terms" in x.lower() for x in r["reasons"])


def test_manager_level_alone_needs_approval():
    r = base_eval(effective_discount_pct=15)
    assert (r["approval_level_required"], r["preflight_status"]) == ("Manager", "Needs Approval")


def test_mismatch_alone_needs_approval_even_at_rep():
    r = base_eval(rep_segment="SMB", verified_segment="Enterprise", effective_discount_pct=5)
    assert r["segment_mismatch"] is True
    assert r["approval_level_required"] == "Rep"
    assert r["preflight_status"] == "Needs Approval"


def test_unverified_segment_uses_rep_bands_and_needs_review():
    r = base_eval(verified_segment=None, effective_discount_pct=5)
    assert r["verified_segment"] == "Unverified"
    assert r["segment_mismatch"] is False
    assert r["band_segment"] == "Mid-Market"
    assert r["preflight_status"] == "Needs Approval"


def test_blocked_outranks_needs_approval():
    r = base_eval(effective_discount_pct=45, payment_terms="net60",
                  blocked_fields=["start_date"])
    assert r["preflight_status"] == "Blocked on Open Questions"
    assert r["approval_level_required"] == "CFO"


def test_null_discount_blocked_and_level_unknown():
    r = base_eval(effective_discount_pct=None, blocked_fields=["requested_discount_pct"])
    assert r["preflight_status"] == "Blocked on Open Questions"
    assert r["approval_level_required"] is None


def test_blocked_fields_from_extraction():
    ext = extraction_from_spec("clean-midmarket")
    assert preflight.blocked_fields(ext) == []
    ext["start_date"]["value"] = None
    ext["open_questions"] = [{"field": "term_months", "text": "?", "blocking": True},
                             {"field": "economic_buyer", "text": "?", "blocking": True}]
    # economic_buyer is not pricing-critical, so it does not block
    assert sorted(preflight.blocked_fields(ext)) == ["start_date", "term_months"]


def test_policy_is_read_from_yaml_not_hardcoded(tmp_path):
    policy = yaml.safe_load(preflight.POLICY.read_text())
    policy["segments"]["Mid-Market"]["bands"][0]["max_discount_pct"] = 15
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(policy))
    custom = preflight.load_policy(path)
    assert preflight.discount_approval(custom, "Mid-Market", 14) == ("Rep", False)
    assert preflight.discount_approval(preflight.load_policy(), "Mid-Market", 14) == \
        ("Manager", False)


def test_policy_ceiling_must_match_last_band(tmp_path):
    policy = yaml.safe_load(preflight.POLICY.read_text())
    policy["segments"]["SMB"]["ceiling_pct"] = 40
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(policy))
    with pytest.raises(preflight.PolicyError):
        preflight.load_policy(path)


def test_seed_opportunities_uses_per_segment_policy():
    import seed_opportunities
    policy = seed_opportunities.load_policy()
    assert seed_opportunities.approver_level(18, "Enterprise", policy) == "Rep"
    assert seed_opportunities.approver_level(18, "SMB", policy) == "Manager"
    assert seed_opportunities.approver_level(45, "Enterprise", policy) == "CFO"


def test_cli(tmp_path, monkeypatch, capsys):
    path = tmp_path / "ext.json"
    path.write_text(json.dumps(extraction_from_spec("mis-segmented")))
    monkeypatch.setattr(preflight.apollo_client, "organization_summary",
                        lambda d, refresh=False: {"domain": d, "name": "MongoDB",
                                                  "employees": 5700,
                                                  "verified_segment": "Enterprise",
                                                  "source": "cache"})
    assert preflight.main([str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verified_segment"] == "Enterprise"
    assert out["preflight_status"] == "Needs Approval"
    assert out["apollo"]["employees"] == 5700
    assert out["pricing"]["totals"]["tcv"] == 50184.00
