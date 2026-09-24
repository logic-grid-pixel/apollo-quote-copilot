"""scripts/run_pipeline.py: SKILL.md steps 2-5 on output/<scenario>/extraction.json,
against a fake Salesforce and a stubbed Apollo (no network)."""

import json

import pytest

import run_pipeline
from extraction_fixtures import spec_document
from fake_sf import FakeSF
from output_fixtures import EMPLOYEES
from test_sfdc_client import BOOK_IDS, OPP_ID, OWNER_ID, QUEUE_ID, pbe_records

VERIFIED = {"retool.com": "Mid-Market", "postman.com": "Mid-Market",
            "mongodb.com": "Enterprise", "snowflake.com": "Enterprise"}
DOMAIN_SCENARIO = {"retool.com": "clean-midmarket", "postman.com": "conflicting-seats",
                   "mongodb.com": "mis-segmented", "snowflake.com": "aggressive-discount"}
OLD_QUOTE = "0Q0000000000OLD"


def seed_history(soql):
    seg = "Enterprise" if "'Enterprise'" in soql else "Mid-Market"
    rows = []
    for i, (disc, stage, outcome) in enumerate([(10, "Closed Won", "Renewed"),
                                                (14, "Closed Won", "Churned"),
                                                (12, "Closed Lost", None),
                                                (38, "Closed Won", "Churned"),
                                                (41, "Closed Won", "Renewed")]):
        rows.append({"Id": f"006SEED{i}", "Name": f"seed {i}", "StageName": stage,
                     "CloseDate": "2025-01-01", "Amount": 1000, "Segment__c": seg,
                     "Effective_Discount__c": disc, "Renewal_Outcome__c": outcome,
                     "Product_Mix__c": "Platform Pro;Additional Seats", "Approver_Level__c": "Rep"})
    return rows


def make_sf(existing_quotes=()):
    responses = [
        (r"FROM Opportunity WHERE Seed_Key__c = 'DEMO-OPP-", lambda q: [{
            "Id": OPP_ID, "Name": "Demo opp", "AccountId": "001x",
            "StageName": "Proposal/Price Quote"}]),
        (r"FROM Opportunity WHERE Seed_Key__c LIKE 'SEED-OPP-", seed_history),
        (r"FROM Opportunity", [{"Id": OPP_ID, "Name": "Demo opp", "OwnerId": OWNER_ID,
                                "Pricebook2Id": None, "AccountId": "001x"}]),
        (r"FROM Quote WHERE OpportunityId", list(existing_quotes)),
        (r"FROM Task WHERE WhatId", lambda q: [{"Id": "00TOLD1", "WhatId": OLD_QUOTE,
                                                "Subject": "Deal Desk review"}]
         if OLD_QUOTE in q else []),
        (r"FROM ContentDocumentLink", lambda q: [{"ContentDocumentId": "069OLD1"}]
         if OLD_QUOTE in q else []),
        (r"FROM Pricebook2", lambda q: [{"Id": i, "Name": n} for n, i in BOOK_IDS.items()
                                        if f"'{n}'" in q]),
        (r"FROM PricebookEntry", pbe_records),
        (r"FROM Group", [{"Id": QUEUE_ID}]),
        (r"FROM ContentVersion", [{"ContentDocumentId": "069000000000001AAA"}]),
    ]
    return FakeSF(responses)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Output root with no network: Apollo stub; Salesforce is whatever the test sets."""
    calls = {"connect": 0, "apollo": []}

    def summary(domain, refresh=False):
        assert not refresh
        calls["apollo"].append(domain)
        return {"domain": domain, "name": domain.split(".")[0].title(),
                "employees": EMPLOYEES[DOMAIN_SCENARIO[domain]],
                "verified_segment": VERIFIED[domain], "source": "cache"}

    monkeypatch.setattr(run_pipeline.apollo_client, "organization_summary", summary)
    sf = make_sf()

    def connect():
        calls["connect"] += 1
        return env_state["sf"]

    env_state = {"sf": sf, "calls": calls, "root": tmp_path}
    monkeypatch.setattr(run_pipeline, "connect", connect)
    return env_state


def put_extraction(root, name, doc=None):
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "extraction.json").write_text(json.dumps(doc or spec_document(name)))
    return folder


def run(env, name, *flags):
    return run_pipeline.main([name, "--output-root", str(env["root"]), *flags])


def load(folder, fname):
    return json.loads((folder / fname).read_text())


# --- dry run ------------------------------------------------------------------------------

def test_dry_run_clean_writes_every_file_and_no_records(env, capsys):
    folder = put_extraction(env["root"], "clean-midmarket")
    assert run(env, "clean-midmarket") == 0
    for f in ["validation.json", "apollo.json", "pricing.json", "preflight.json",
              "comparables.json", "opportunity.json", "sfdc_plan.json", "order_form.pdf",
              "deal_brief.md"]:
        assert (folder / f).exists(), f
    assert not (folder / "sfdc_result.json").exists()
    assert env["sf"].created == [] and env["sf"].deleted == []
    assert load(folder, "validation.json")["valid"] is True
    assert load(folder, "pricing.json")["totals"]["tcv"] == 196240.00  # hand calc
    pf = load(folder, "preflight.json")
    assert pf["preflight_status"] == "Ready" and pf["apollo"]["verified_segment"] == "Mid-Market"
    comps = load(folder, "comparables.json")
    assert comps["segment"] == "Mid-Market" and comps["tier"] == "Platform Pro"
    assert comps["proposed_discount_pct"] == 12.0
    plan = load(folder, "sfdc_plan.json")
    assert plan["quote"]["OpportunityId"] == OPP_ID and len(plan["lines"]) == 5
    assert (folder / "order_form.pdf").read_bytes().startswith(b"%PDF-")
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "dry-run" and out["preflight_status"] == "Ready"
    assert out["order_form"].endswith("order_form.pdf")
    assert env["calls"]["apollo"] == ["retool.com"]


def test_dry_run_blocked_renders_no_order_form_and_clears_stale_one(env):
    folder = put_extraction(env["root"], "conflicting-seats")
    (folder / "order_form.pdf").write_bytes(b"%PDF-1.4 stale")
    assert run(env, "conflicting-seats") == 0
    assert not (folder / "order_form.pdf").exists()
    assert load(folder, "preflight.json")["preflight_status"] == "Blocked on Open Questions"
    assert load(folder, "pricing.json")["status"] == "blocked"
    assert load(folder, "sfdc_plan.json")["task"]["assign_to"] == "opportunity_owner"
    assert "Not priced: blocked on seat_count" in (folder / "deal_brief.md").read_text()


def test_pricing_uses_verified_segment_book(env):
    folder = put_extraction(env["root"], "mis-segmented")
    assert run(env, "mis-segmented") == 0
    pr = load(folder, "pricing.json")
    assert pr["segment"] == "Enterprise" and pr["totals"]["tcv"] == 50184.00  # hand calc
    assert load(folder, "preflight.json")["segment_mismatch"] is True


def test_no_effective_discount_skips_comparables(env):
    doc = spec_document("clean-midmarket")
    doc["requested_discount_pct"] = {"value": None, "source_citation": None,
                                     "confidence": "high"}
    doc["open_questions"] = [{"field": "requested_discount_pct", "text": "No discount stated",
                              "blocking": True}]
    folder = put_extraction(env["root"], "clean-midmarket", doc)
    (folder / "comparables.json").write_text("{}")  # stale from an earlier run
    assert run(env, "clean-midmarket") == 0
    assert not (folder / "comparables.json").exists()
    assert "Comparables: not run (no effective discount)" in (folder / "deal_brief.md").read_text()


def test_invalid_extraction_stops_after_validation(env, capsys):
    doc = spec_document("conflicting-seats")
    doc["seat_count"] = {"value": 80, "source_citation":
                         'C3 [00:09:11] "…so it\'s more like 80 people across platform and data."',
                         "confidence": "high"}
    folder = put_extraction(env["root"], "conflicting-seats", doc)
    assert run(env, "conflicting-seats") == 1
    assert load(folder, "validation.json")["valid"] is False
    assert not (folder / "pricing.json").exists()
    assert "validation" in capsys.readouterr().err.lower()


def test_missing_extraction_errors(env, capsys):
    assert run(env, "clean-midmarket") == 1
    assert "extraction.json" in capsys.readouterr().err


def test_offline_never_connects(env):
    folder = put_extraction(env["root"], "clean-midmarket")
    assert run(env, "clean-midmarket", "--offline") == 0
    assert env["calls"]["connect"] == 0
    assert not (folder / "opportunity.json").exists()
    assert "not run (--offline)" in load(folder, "comparables.json")["error"]
    assert load(folder, "sfdc_plan.json")["quote"]["OpportunityId"] is None
    assert (folder / "order_form.pdf").exists()


def test_offline_and_live_are_exclusive(env):
    put_extraction(env["root"], "clean-midmarket")
    with pytest.raises(SystemExit):
        run(env, "clean-midmarket", "--offline", "--live")


# --- live ---------------------------------------------------------------------------------

def test_live_clean_creates_quote_with_pdf(env):
    folder = put_extraction(env["root"], "clean-midmarket")
    assert run(env, "clean-midmarket", "--live") == 0
    sf = env["sf"]
    [(quote_id, q)] = sf.created_of("Quote")
    assert q["Preflight_Status__c"] == "Ready"
    assert len(sf.created_of("QuoteLineItem")) == 5
    [(_, cv)] = sf.created_of("ContentVersion")
    assert cv["FirstPublishLocationId"] == quote_id
    res = load(folder, "sfdc_result.json")
    assert res["quote_id"] == quote_id and res["replaced_quote_ids"] == []
    assert f"({quote_id}), 5 lines" in (folder / "deal_brief.md").read_text()


def test_live_blocked_creates_quote_without_pdf(env):
    folder = put_extraction(env["root"], "aggressive-discount")
    assert run(env, "aggressive-discount", "--live") == 0
    sf = env["sf"]
    assert len(sf.created_of("Quote")) == 1
    assert sf.created_of("ContentVersion") == []
    [(_, task)] = sf.created_of("Task")
    assert task["OwnerId"] == OWNER_ID
    assert not (folder / "order_form.pdf").exists()


TOOL_QUOTE = {"Id": OLD_QUOTE, "Name": "Demo opp - Mid-Market quote 2026-09-01",
              "Description": "Quote Copilot draft on the Mid-Market price book, 24 months.",
              "Preflight_Status__c": "Ready"}
OTHER_QUOTE = {"Id": "0Q0000000000HUM", "Name": "Hand-made quote",
               "Description": "Made by a person", "Preflight_Status__c": None}


def test_live_refuses_when_tool_quote_exists(env, capsys):
    env["sf"] = make_sf([TOOL_QUOTE])
    folder = put_extraction(env["root"], "clean-midmarket")
    assert run(env, "clean-midmarket", "--live") == 2
    assert env["sf"].created == [] and env["sf"].deleted == []
    assert OLD_QUOTE in capsys.readouterr().err
    assert not (folder / "sfdc_result.json").exists()


def test_live_replace_deletes_previous_tool_quote_then_creates(env):
    env["sf"] = make_sf([TOOL_QUOTE, OTHER_QUOTE])
    folder = put_extraction(env["root"], "clean-midmarket")
    assert run(env, "clean-midmarket", "--live", "--replace") == 0
    sf = env["sf"]
    assert ("Quote", OLD_QUOTE) in sf.deleted
    assert ("Task", "00TOLD1") in sf.deleted and ("ContentDocument", "069OLD1") in sf.deleted
    assert ("Quote", OTHER_QUOTE["Id"]) not in sf.deleted  # not ours: never touched
    assert len(sf.created_of("Quote")) == 1
    assert load(folder, "sfdc_result.json")["replaced_quote_ids"] == [OLD_QUOTE]


def test_human_quote_is_not_a_duplicate(env):
    env["sf"] = make_sf([OTHER_QUOTE])
    put_extraction(env["root"], "clean-midmarket")
    assert run(env, "clean-midmarket", "--live") == 0
    assert env["sf"].deleted == []


def test_replace_needs_live(env):
    put_extraction(env["root"], "clean-midmarket")
    with pytest.raises(SystemExit):
        run(env, "clean-midmarket", "--replace")
