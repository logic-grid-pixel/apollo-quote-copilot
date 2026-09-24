"""Unit tests for scripts/sfdc_client.py against a fake Salesforce (offline),
plus one integration test that writes to the real org and cleans up after itself."""

import base64
import json
from datetime import date

import pytest

import preflight
import pricing
import sf_session
import sfdc_client
from fake_sf import FakeError, FakeSF
from test_preflight import extraction_from_spec, load_spec

OPP_ID = "006000000000001AAA"
OWNER_ID = "005000000000001AAA"
QUEUE_ID = "00G000000000001AAA"
PDF = b"%PDF-1.4\n%%EOF\n"
BOOK_IDS = {"SMB": "01s00000000000SMB", "Mid-Market": "01s0000000000MMKT",
            "Enterprise": "01s0000000000ENTR"}
CODES = ["PLAT-STARTER", "PLAT-PRO", "PLAT-ENT", "ADD-SEAT", "SUP-PREM", "SVC-IMPL"]


def pbe_records(soql):
    book = next(n for n, i in BOOK_IDS.items() if i in soql)
    return [{"Id": f"01u{book[:3]}{c}", "Product2Id": f"01t{c}", "UnitPrice": 1,
             "Product2": {"ProductCode": c, "Name": c}} for c in CODES]


def make_sf(fail_on=None, opp=True, queue=True):
    responses = [
        (r"FROM Opportunity", [{"Id": OPP_ID, "Name": "Acme - Platform Pro", "OwnerId": OWNER_ID,
                                "Pricebook2Id": None, "AccountId": "001x"}] if opp else []),
        (r"FROM Pricebook2", lambda q: [{"Id": i, "Name": n} for n, i in BOOK_IDS.items()
                                        if f"'{n}'" in q]),
        (r"FROM PricebookEntry", pbe_records),
        (r"FROM Group", [{"Id": QUEUE_ID}] if queue else []),
        (r"FROM ContentVersion", [{"ContentDocumentId": "069000000000001AAA"}]),
    ]
    return FakeSF(responses, fail_on=fail_on)


def scenario(name):
    ext = extraction_from_spec(name)
    verified = load_spec(name)["expected_preflight"]["verified_segment"]
    pf = preflight.preflight_extraction(ext, verified)
    return ext, pf, pf["pricing"]


# --- validation happens before any read or write ----------------------------------------

def test_invalid_opportunity_id_rejected_before_any_call():
    sf = make_sf()
    ext, pf, pr = scenario("clean-midmarket")
    with pytest.raises(sfdc_client.QuoteInputError):
        sfdc_client.create_quote(sf, "not-an-id", pf, pr, extraction=ext)
    assert sf.queries == [] and sf.created == []


def test_bad_pdf_rejected_before_any_call():
    sf = make_sf()
    ext, pf, pr = scenario("clean-midmarket")
    with pytest.raises(sfdc_client.QuoteInputError):
        sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext, pdf_bytes=b"hello")
    assert sf.queries == [] and sf.created == []


def test_ready_quote_needs_priced_lines():
    ext, pf, _ = scenario("clean-midmarket")
    with pytest.raises(sfdc_client.QuoteInputError):
        sfdc_client.create_quote(make_sf(), OPP_ID, pf, {"status": "blocked"}, extraction=ext)


def test_pricing_segment_must_match_band_segment():
    ext, pf, _ = scenario("clean-midmarket")
    other = pricing.price_extraction(ext, "Enterprise")
    with pytest.raises(sfdc_client.QuoteInputError):
        sfdc_client.create_quote(make_sf(), OPP_ID, pf, other, extraction=ext)


def test_invalid_picklist_value_rejected():
    ext, pf, pr = scenario("clean-midmarket")
    pf = dict(pf, preflight_status="Maybe")
    with pytest.raises(sfdc_client.QuoteInputError):
        sfdc_client.create_quote(make_sf(), OPP_ID, pf, pr, extraction=ext)


def test_missing_opportunity_or_price_book_entry_fails_before_writes():
    ext, pf, pr = scenario("clean-midmarket")
    sf = make_sf(opp=False)
    with pytest.raises(sfdc_client.QuoteInputError):
        sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext)
    assert sf.created == []


# --- happy path: Ready -------------------------------------------------------------------

def test_clean_quote_lines_fields_pdf_and_no_task():
    sf = make_sf()
    ext, pf, pr = scenario("clean-midmarket")
    out = sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext, pdf_bytes=PDF)

    [(quote_id, q)] = sf.created_of("Quote")
    assert out["quote_id"] == quote_id
    assert q["OpportunityId"] == OPP_ID
    assert q["Pricebook2Id"] == BOOK_IDS["Mid-Market"]
    assert q["Status"] == "Draft"
    assert q["Rep_Segment__c"] == "Mid-Market"
    assert q["Verified_Segment__c"] == "Mid-Market"
    assert q["Segment_Mismatch__c"] is False
    assert q["Effective_Discount__c"] == 12.00
    assert q["Approval_Level_Required__c"] == "Rep"
    assert q["Preflight_Status__c"] == "Ready"
    assert "term_months: 24 | source: C1 | confidence: high" in q["Source_Citations__c"]
    assert "Platform Pro x1, Additional Seats x120" in q["Source_Citations__c"]
    assert q["Open_Questions__c"] in (None, "", "None")

    lines = [d for _, d in sf.created_of("QuoteLineItem")]
    # 24 months: 2 years x (Platform Pro, Additional Seats) + Implementation once = 5
    assert len(lines) == 5
    assert all(ln["QuoteId"] == quote_id for ln in lines)
    seats = [ln for ln in lines if ln["PricebookEntryId"].endswith("ADD-SEAT")]
    assert [ln["Quantity"] for ln in seats] == [120, 120]
    assert all(ln["UnitPrice"] == 540.0 and ln["Discount"] == 12.0 for ln in seats)
    assert [ln["Description"].split(" ")[:2] for ln in seats] == [["Year", "1"], ["Year", "2"]]
    assert seats[0]["ServiceDate"] == "2026-11-01" and seats[1]["ServiceDate"] == "2027-11-01"
    # Quote total at list x (1 - discount) must equal pricing.py's TCV (hand calc 196,240)
    total = sum(ln["Quantity"] * ln["UnitPrice"] * (1 - ln["Discount"] / 100) for ln in lines)
    assert round(total, 2) == 196240.00

    [(cv_id, cv)] = sf.created_of("ContentVersion")
    assert cv["FirstPublishLocationId"] == quote_id
    assert base64.b64decode(cv["VersionData"]) == PDF
    assert cv["PathOnClient"].endswith(".pdf")
    assert sf.created_of("Task") == []
    assert out["task_id"] is None


# --- Needs Approval -> Deal Desk queue task on the Quote ------------------------------------

def test_mis_segmented_task_to_deal_desk_queue():
    sf = make_sf()
    ext, pf, pr = scenario("mis-segmented")
    out = sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext)
    [(quote_id, q)] = sf.created_of("Quote")
    assert q["Pricebook2Id"] == BOOK_IDS["Enterprise"]
    assert q["Rep_Segment__c"] == "SMB" and q["Verified_Segment__c"] == "Enterprise"
    assert q["Segment_Mismatch__c"] is True
    assert q["Preflight_Status__c"] == "Needs Approval"
    [(task_id, t)] = sf.created_of("Task")
    assert t["OwnerId"] == QUEUE_ID
    assert t["WhatId"] == quote_id
    assert "SMB" in t["Description"] and "Enterprise" in t["Description"]
    assert out["task_what_id"] == quote_id


def test_task_falls_back_to_opportunity_when_quote_not_allowed():
    sf = make_sf(fail_on={"Task": lambda d: d.get("WhatId", "").startswith("0Q0")})
    ext, pf, pr = scenario("mis-segmented")
    out = sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext)
    [(task_id, t)] = sf.created_of("Task")
    assert t["WhatId"] == OPP_ID
    assert out["task_what_id"] == OPP_ID


# --- Blocked -> task to the Opportunity owner listing open questions -----------------------

def test_conflicting_seats_blocked_quote_without_lines():
    sf = make_sf()
    ext, pf, pr = scenario("conflicting-seats")
    assert pr["status"] == "blocked"
    sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext)
    [(quote_id, q)] = sf.created_of("Quote")
    assert q["Preflight_Status__c"] == "Blocked on Open Questions"
    assert q["Approval_Level_Required__c"] == "Manager"
    assert "seat_count" in q["Open_Questions__c"] and "BLOCKING" in q["Open_Questions__c"]
    assert sf.created_of("QuoteLineItem") == []
    [(_, t)] = sf.created_of("Task")
    assert t["OwnerId"] == OWNER_ID
    assert "Seat count stated as 50 (C1) and 80 (C3)" in t["Description"]


def test_aggressive_ramped_lines_one_per_product_per_year():
    sf = make_sf()
    ext, pf, pr = scenario("aggressive-discount")
    sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext)
    lines = [d for _, d in sf.created_of("QuoteLineItem")]
    assert len(lines) == 9
    seats = [ln for ln in lines if ln["PricebookEntryId"].endswith("ADD-SEAT")]
    assert [ln["Quantity"] for ln in seats] == [200, 400, 600]
    assert all("ServiceDate" not in ln for ln in lines)  # start date unknown
    total = sum(ln["Quantity"] * ln["UnitPrice"] * (1 - ln["Discount"] / 100) for ln in lines)
    assert round(total, 2) == 555120.00  # hand calc T1
    [(_, q)] = sf.created_of("Quote")
    assert q["Approval_Level_Required__c"] == "CFO"
    assert "start_date" in q["Open_Questions__c"]
    [(_, t)] = sf.created_of("Task")
    assert t["OwnerId"] == OWNER_ID  # Blocked outranks Needs Approval


# --- rollback ------------------------------------------------------------------------------

def test_failure_after_quote_create_rolls_back():
    sf = make_sf(fail_on={"QuoteLineItem": lambda d: True})
    ext, pf, pr = scenario("clean-midmarket")
    with pytest.raises(FakeError):
        sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext, pdf_bytes=PDF)
    [(quote_id, _)] = sf.created_of("Quote")
    assert ("Quote", quote_id) in sf.deleted


def test_pdf_failure_rolls_back_quote():
    sf = make_sf(fail_on={"ContentVersion": lambda d: True})
    ext, pf, pr = scenario("clean-midmarket")
    with pytest.raises(FakeError):
        sfdc_client.create_quote(sf, OPP_ID, pf, pr, extraction=ext, pdf_bytes=PDF)
    [(quote_id, _)] = sf.created_of("Quote")
    assert ("Quote", quote_id) in sf.deleted


# --- plan / dry run -------------------------------------------------------------------------

def test_plan_is_pure_and_readable():
    ext, pf, pr = scenario("aggressive-discount")
    plan = sfdc_client.plan_quote(pf, pr, extraction=ext, opportunity_id=OPP_ID)
    assert plan["price_book"] == "Enterprise"
    assert len(plan["lines"]) == 9
    assert plan["task"]["assign_to"] == "opportunity_owner"
    assert plan["quote"]["Status"] == "Draft"


def test_cli_dry_run_does_not_touch_salesforce(tmp_path, monkeypatch, capsys):
    path = tmp_path / "ext.json"
    path.write_text(json.dumps(extraction_from_spec("clean-midmarket")))
    monkeypatch.setattr(sfdc_client, "connect",
                        lambda: (_ for _ in ()).throw(AssertionError("connected")))
    monkeypatch.setattr(preflight.apollo_client, "organization_summary",
                        lambda d, refresh=False: {"verified_segment": "Mid-Market",
                                                  "domain": d, "source": "cache"})
    assert sfdc_client.main([str(path), "--opportunity", OPP_ID, "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["quote"]["Preflight_Status__c"] == "Ready"
    assert len(out["lines"]) == 5


def test_session_retries_spurious_504_once(monkeypatch):
    calls = []
    monkeypatch.setattr(sf_session, "_sleep", lambda s: None)

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise Exception("504 upstream request timeout")
        return "sf"
    assert sf_session.connect(connect_fn=flaky) == "sf"

    def broken():
        raise Exception("INVALID_LOGIN")
    with pytest.raises(Exception):
        sf_session.connect(connect_fn=broken)


# --- integration: real org, cleans up everything it creates ---------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("name, expected_owner", [("aggressive-discount", "owner"),
                                                  ("mis-segmented", "queue")])
def test_create_quote_in_org(name, expected_owner):
    sf = sf_session.connect()
    opp = sf.query(f"SELECT Id, OwnerId FROM Opportunity "
                   f"WHERE Seed_Key__c = 'DEMO-OPP-{name}'")["records"]
    assert opp, "run scripts/seed_demo_opportunities.py first"
    opp = opp[0]
    ext, pf, pr = scenario(name)
    out = None
    try:
        out = sfdc_client.create_quote(sf, opp["Id"], pf, pr, extraction=ext, pdf_bytes=PDF,
                                       quote_name=f"TEST {name} (integration, auto-deleted)")
        qid = out["quote_id"]
        q = sf.query("SELECT Status, Pricebook2.Name, Rep_Segment__c, Verified_Segment__c, "
                     "Segment_Mismatch__c, Effective_Discount__c, Approval_Level_Required__c, "
                     "Preflight_Status__c, Open_Questions__c, Source_Citations__c, TotalPrice "
                     f"FROM Quote WHERE Id = '{qid}'")["records"][0]
        assert q["Status"] == "Draft"
        assert q["Pricebook2"]["Name"] == pf["band_segment"]
        assert q["Verified_Segment__c"] == pf["verified_segment"]
        assert q["Approval_Level_Required__c"] == pf["approval_level_required"]
        assert q["Preflight_Status__c"] == pf["preflight_status"]
        assert q["Segment_Mismatch__c"] == pf["segment_mismatch"]
        assert q["Effective_Discount__c"] == pf["effective_discount_pct"]
        assert q["Source_Citations__c"]
        assert round(q["TotalPrice"], 2) == pr["totals"]["tcv"]
        n_lines = sf.query(f"SELECT COUNT() FROM QuoteLineItem WHERE QuoteId = '{qid}'")
        assert n_lines["totalSize"] == sum(len(y["lines"]) for y in pr["years"])
        links = sf.query("SELECT ContentDocumentId FROM ContentDocumentLink "
                         f"WHERE LinkedEntityId = '{qid}'")["records"]
        assert [ln["ContentDocumentId"] for ln in links] == [out["content_document_id"]]
        task = sf.query(f"SELECT OwnerId, WhatId FROM Task WHERE Id = '{out['task_id']}'")
        task = task["records"][0]
        assert task["WhatId"] == out["task_what_id"] == qid  # Quote supports activities
        if expected_owner == "owner":
            assert task["OwnerId"] == opp["OwnerId"]
        else:
            queue = sf.query("SELECT Id FROM Group WHERE Type = 'Queue' "
                             "AND DeveloperName = 'Deal_Desk'")["records"][0]["Id"]
            assert task["OwnerId"] == queue
    finally:
        if out:
            sfdc_client.delete_created(sf, out)
    if out:
        assert sf.query(f"SELECT COUNT() FROM Quote WHERE Id = '{out['quote_id']}'")[
            "totalSize"] == 0
        assert sf.query("SELECT COUNT() FROM ContentDocument "
                        f"WHERE Id = '{out['content_document_id']}'")["totalSize"] == 0
        assert sf.query(f"SELECT COUNT() FROM Task WHERE Id = '{out['task_id']}'")[
            "totalSize"] == 0


# --- Open_Questions__c keeps each question's candidates and citations ----------------------

C1_50 = 'C1 [00:10:27] "But it\'s roughly 50 engineers who\'d need access."'
C3_80 = 'C3 [00:09:11] "…so it\'s more like 80 people across platform and data."'


def test_open_questions_text_lists_candidates_with_citations():
    pf = {"open_questions": [
        {"field": "seat_count", "text": "Seat count stated as 50 (C1) and 80 (C3); never reconciled",
         "blocking": True,
         "candidates": [{"value": 50, "source_citation": C1_50},
                        {"value": 80, "source_citation": C3_80}]}],
        "blocked_fields": ["seat_count"]}
    text = sfdc_client.open_questions_text(pf)
    assert text.count("seat_count") == 1  # blocked field covered by the question
    assert "candidates: 50 (" + C1_50 + "); 80 (" + C3_80 + ")" in text
    assert text.startswith("[BLOCKING] seat_count: Seat count stated as 50")


def test_open_questions_text_includes_question_source_citation():
    cite = 'C3 [00:23:23] "As soon as we\'re through security review."'
    pf = {"open_questions": [{"field": "start_date", "text": "No start date stated",
                              "blocking": True, "source_citation": cite}]}
    assert sfdc_client.open_questions_text(pf) == \
        f"[BLOCKING] start_date: No start date stated | source: {cite}"


def test_open_questions_text_without_context_is_unchanged():
    pf = {"open_questions": [{"field": "economic_buyer", "text": "No EB", "blocking": False}]}
    assert sfdc_client.open_questions_text(pf) == "[non-blocking] economic_buyer: No EB"


def test_blocked_task_lists_candidates():
    from extraction_fixtures import spec_document
    ext = spec_document("conflicting-seats")
    pf = preflight.preflight_extraction(ext, "Mid-Market")
    plan = sfdc_client.plan_quote(pf, pf["pricing"], extraction=ext, opportunity_id=OPP_ID)
    assert C1_50 in plan["quote"]["Open_Questions__c"]
    assert C3_80 in plan["task"]["Description"]
