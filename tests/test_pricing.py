"""Unit tests for scripts/pricing.py.

The T1-T4 expected values were computed BY HAND, independently of the code, and
are hard-coded as literals. Never edit an expectation to match code output: if
the code disagrees, the code is wrong unless the hand calculation below can be
shown to contain an arithmetic error.
"""

import json
from decimal import Decimal

import pytest

import pricing

ENT_LINES = [
    {"product": "Platform Enterprise", "quantity": 1},
    {"product": "Additional Seats", "quantity": 200},
    {"product": "Premium Support", "quantity": 1},
]
RAMP_200_400_600 = [{"year": 1, "seats": 200}, {"year": 2, "seats": 400},
                    {"year": 3, "seats": 600}]


def money(x):
    return Decimal(str(x)).quantize(Decimal("0.01"))


def year_totals(result, key):
    return [money(y[key]) for y in result["years"]]


# --- T1: aggressive-discount at a flat 40%, Enterprise book, ramp 200/400/600 -------
# Hand calc (Enterprise book: Platform Enterprise 86,400; seat 480; Premium Support 30,000)
#   Y1 list 86,400 + 200*480 + 30,000 = 212,400
#   Y2 list 86,400 + 400*480 + 30,000 = 308,400
#   Y3 list 86,400 + 600*480 + 30,000 = 404,400
#   list TCV 925,200; net = 60% = 555,120; ACV = 555,120 / 3 = 185,040; blended 40%

def test_t1_flat_40_ramped_enterprise():
    r = pricing.price_quote({"segment": "Enterprise", "term_months": 36,
                             "lines": ENT_LINES, "ramp": RAMP_200_400_600,
                             "discount_pct": 40})
    assert r["status"] == "priced"
    assert year_totals(r, "list_total") == [money(212400), money(308400), money(404400)]
    assert money(r["totals"]["list_tcv"]) == money("925200.00")
    assert money(r["totals"]["tcv"]) == money("555120.00")
    assert money(r["totals"]["acv"]) == money("185040.00")
    assert r["totals"]["blended_discount_pct"] == 40.00


# --- T2: same lines and ramp, per-year discounts 40 / 35 / 30 -----------------------
#   Y1 212,400 * 0.60 = 127,440
#   Y2 308,400 * 0.65 = 200,460
#   Y3 404,400 * 0.70 = 283,080
#   TCV 610,980; ACV 203,660; blended = 314,220 / 925,200 = 0.3396238... -> 33.96%
#   (the simple average of the yearly discounts would be 35.00%, which is wrong)

def test_t2_per_year_discounts_blend_by_value_not_average():
    r = pricing.price_quote({"segment": "Enterprise", "term_months": 36,
                             "lines": ENT_LINES, "ramp": RAMP_200_400_600,
                             "year_discounts": {1: 40, 2: 35, 3: 30}})
    assert year_totals(r, "net_total") == [money(127440), money(200460), money(283080)]
    assert money(r["totals"]["tcv"]) == money("610980.00")
    assert money(r["totals"]["acv"]) == money("203660.00")
    assert r["totals"]["blended_discount_pct"] == 33.96
    assert r["totals"]["blended_discount_pct"] != 35.00


# --- T3: Mid-Market, ramp 50/100/150, 25/20/15 on subscription, implementation at list
# Mid-Market book: Platform Pro 34,200; seat 540; Implementation Services 25,000 one-time
#   Y1 list 34,200 + 50*540  = 61,200  -> net 45,900  (25%)
#   Y2 list 34,200 + 100*540 = 88,200  -> net 70,560  (20%)
#   Y3 list 34,200 + 150*540 = 115,200 -> net 97,920  (15%)
#   recurring list 264,600, net 214,380; implementation 25,000 once, undiscounted
#   list TCV 289,600; TCV 239,380; ACV 214,380 / 3 = 71,460
#   blended = 50,220 / 289,600 = 0.1734116... -> 17.34%

def test_t3_one_time_line_excluded_from_acv_and_undiscounted():
    r = pricing.price_quote({
        "segment": "Mid-Market", "term_months": 36,
        "lines": [{"product": "Platform Pro", "quantity": 1},
                  {"product": "Additional Seats", "quantity": 50},
                  {"product": "Implementation Services", "quantity": 1}],
        "ramp": [{"year": 1, "seats": 50}, {"year": 2, "seats": 100},
                 {"year": 3, "seats": 150}],
        "year_discounts": {1: 25, 2: 20, 3: 15},
        "line_discounts": {"Implementation Services": 0},
    })
    assert money(r["totals"]["list_tcv"]) == money("289600.00")
    assert money(r["totals"]["tcv"]) == money("239380.00")
    assert money(r["totals"]["acv"]) == money("71460.00")
    assert r["totals"]["blended_discount_pct"] == 17.34
    impl = [ln for y in r["years"] for ln in y["lines"]
            if ln["product"] == "Implementation Services"]
    assert len(impl) == 1 and impl[0]["year"] == 1 and impl[0]["billing"] == "one_time"


# --- T4: clean-midmarket, Platform Pro + 120 seats + implementation, 24 months, 12% --
#   annual list 34,200 + 120*540 = 99,000; x2 years = 198,000; + 25,000 = 223,000
#   net at 12%: 196,240; ACV = 198,000 * 0.88 / 2 = 87,120; blended 12%

T4_EXTRACTION = {
    "account_domain": {"value": "retool.com", "source_citation": "C1", "confidence": "high"},
    "rep_stated_segment": {"value": "Mid-Market", "source_citation": None, "confidence": "high"},
    "products": {"value": [{"name": "Platform Pro", "quantity": 1},
                           {"name": "Additional Seats", "quantity": 120},
                           {"name": "Implementation Services", "quantity": 1}],
                 "source_citation": "C1, C2", "confidence": "high"},
    "seat_count": {"value": 120, "source_citation": "C1; C2", "confidence": "high"},
    "term_months": {"value": 24, "source_citation": "C2", "confidence": "high"},
    "start_date": {"value": "2026-11-01", "source_citation": "C2", "confidence": "high"},
    "payment_terms": {"value": "net30", "source_citation": "C2", "confidence": "high"},
    "requested_discount_pct": {"value": 12, "source_citation": "C2", "confidence": "high"},
    "ramp": {"value": None, "source_citation": None, "confidence": "high"},
    "open_questions": [],
}


def test_t4_clean_midmarket_from_request():
    r = pricing.price_quote({
        "segment": "Mid-Market", "term_months": 24,
        "lines": [{"product": "Platform Pro", "quantity": 1},
                  {"product": "Additional Seats", "quantity": 120},
                  {"product": "Implementation Services", "quantity": 1}],
        "discount_pct": 12})
    assert money(r["totals"]["list_tcv"]) == money("223000.00")
    assert money(r["totals"]["tcv"]) == money("196240.00")
    assert money(r["totals"]["acv"]) == money("87120.00")
    assert r["totals"]["blended_discount_pct"] == 12.00


def test_t4_clean_midmarket_from_extraction():
    r = pricing.price_extraction(T4_EXTRACTION, "Mid-Market")
    assert r["status"] == "priced"
    assert money(r["totals"]["list_tcv"]) == money("223000.00")
    assert money(r["totals"]["tcv"]) == money("196240.00")
    assert money(r["totals"]["acv"]) == money("87120.00")
    assert r["totals"]["blended_discount_pct"] == 12.00


# --- behaviour -------------------------------------------------------------------

def test_list_prices_come_from_the_segment_book():
    r = pricing.price_quote({"segment": "SMB", "term_months": 12,
                             "lines": [{"product": "Platform Pro", "quantity": 1}],
                             "discount_pct": 0})
    line = r["years"][0]["lines"][0]
    assert money(line["unit_list_price"]) == money(36000)
    assert line["product_code"] == "PLAT-PRO"


def test_blocked_when_seat_count_null():
    ext = json.loads(json.dumps(T4_EXTRACTION))
    ext["seat_count"]["value"] = None
    ext["products"]["value"][1]["quantity"] = None
    ext["open_questions"] = [{"field": "seat_count", "text": "50 vs 80", "blocking": True}]
    built = pricing.request_from_extraction(ext, "Mid-Market")
    assert built["status"] == "blocked"
    assert "seat_count" in built["blocked_fields"]
    r = pricing.price_extraction(ext, "Mid-Market")
    assert r["status"] == "blocked"
    assert "totals" not in r and "years" not in r


def test_blocked_when_blocking_question_on_pricing_field_even_if_value_present():
    ext = json.loads(json.dumps(T4_EXTRACTION))
    ext["open_questions"] = [{"field": "term_months", "text": "12 or 24?", "blocking": True}]
    assert pricing.price_extraction(ext, "Mid-Market")["status"] == "blocked"


def test_start_date_not_needed_to_price():
    ext = json.loads(json.dumps(T4_EXTRACTION))
    ext["start_date"]["value"] = None
    ext["open_questions"] = [{"field": "start_date", "text": "unknown", "blocking": True}]
    assert pricing.price_extraction(ext, "Mid-Market")["status"] == "priced"


def test_blocked_when_seat_quantity_conflicts_with_seat_count():
    ext = json.loads(json.dumps(T4_EXTRACTION))
    ext["products"]["value"][1]["quantity"] = 80
    r = pricing.price_extraction(ext, "Mid-Market")
    assert r["status"] == "blocked"


def test_discount_override_beats_requested():
    r = pricing.price_extraction(T4_EXTRACTION, "Mid-Market", discount_pct=0)
    assert money(r["totals"]["tcv"]) == money("223000.00")
    assert r["totals"]["blended_discount_pct"] == 0.00


def test_null_discount_blocks_unless_overridden():
    ext = json.loads(json.dumps(T4_EXTRACTION))
    ext["requested_discount_pct"]["value"] = None
    assert pricing.price_extraction(ext, "Mid-Market")["status"] == "blocked"
    assert pricing.price_extraction(ext, "Mid-Market", discount_pct=12)["status"] == "priced"


def test_unknown_product_blocks():
    ext = json.loads(json.dumps(T4_EXTRACTION))
    ext["products"]["value"].append({"name": "Platinum Widget", "quantity": 1})
    r = pricing.price_extraction(ext, "Mid-Market")
    assert r["status"] == "blocked" and "products" in r["blocked_fields"]


def test_partial_year_prorates_by_months():
    # 18 months of Platform Pro (SMB 36,000/yr) at list: 36,000 + 18,000 = 54,000
    r = pricing.price_quote({"segment": "SMB", "term_months": 18,
                             "lines": [{"product": "Platform Pro", "quantity": 1}],
                             "discount_pct": 0})
    assert [y["months"] for y in r["years"]] == [12, 6]
    assert money(r["totals"]["list_tcv"]) == money(54000)
    # ACV = 54,000 / 1.5 years = 36,000
    assert money(r["totals"]["acv"]) == money(36000)


def test_ramp_must_cover_every_year():
    with pytest.raises(pricing.PricingError):
        pricing.price_quote({"segment": "Enterprise", "term_months": 36, "lines": ENT_LINES,
                             "ramp": RAMP_200_400_600[:2], "discount_pct": 10})


def test_invalid_inputs_raise():
    base = {"segment": "Enterprise", "term_months": 12, "lines": ENT_LINES, "discount_pct": 10}
    for bad in ({"segment": "Galactic"}, {"term_months": 0}, {"discount_pct": 101},
                {"discount_pct": -1}, {"lines": []}):
        with pytest.raises(pricing.PricingError):
            pricing.price_quote({**base, **bad})


def test_money_rounded_to_cents_at_output():
    # 7 seats at 540 with 33.333% discount -> 3,780 * 0.66667 = 2,520.0126 -> 2,520.01
    r = pricing.price_quote({"segment": "Mid-Market", "term_months": 12,
                             "lines": [{"product": "Additional Seats", "quantity": 7}],
                             "discount_pct": "33.333"})
    assert r["totals"]["tcv"] == 2520.01


def test_cli_outputs_json(tmp_path, capsys):
    path = tmp_path / "ext.json"
    path.write_text(json.dumps(T4_EXTRACTION))
    assert pricing.main([str(path), "--segment", "Mid-Market"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["totals"]["tcv"] == 196240.00
    assert out["totals"]["acv"] == 87120.00
