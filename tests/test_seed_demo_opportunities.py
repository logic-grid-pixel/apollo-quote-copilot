"""Unit tests for scripts/seed_demo_opportunities.py (offline)."""

from datetime import date

import seed_demo_opportunities as demo
from fake_sf import FakeSF

ACCOUNTS = [{"Id": f"001{d[:6]}", "Name": d.split(".")[0].title(),
             "Seed_Key__c": f"SEED-ACC-{d}"}
            for d in ("retool.com", "postman.com", "mongodb.com", "snowflake.com", "cal.com")]


def test_records_one_open_opportunity_per_scenario():
    recs = demo.build_records({a["Seed_Key__c"][9:]: a for a in ACCOUNTS}, date(2026, 9, 23))
    assert sorted(r["Seed_Key__c"] for r in recs) == [
        "DEMO-OPP-aggressive-discount", "DEMO-OPP-clean-midmarket",
        "DEMO-OPP-conflicting-seats", "DEMO-OPP-mis-segmented", "DEMO-OPP-smb-starter"]
    for r in recs:
        assert not r["Seed_Key__c"].startswith("SEED-")
        assert r["StageName"] == "Proposal/Price Quote"
        assert r["CloseDate"] == "2026-10-23"
    mis = next(r for r in recs if r["Seed_Key__c"] == "DEMO-OPP-mis-segmented")
    assert mis["AccountId"] == "001mongod"
    assert "SMB" in mis["Description"] and "Jordan Mwangi" in mis["Description"]


def test_run_upserts_on_external_id():
    sf = FakeSF([(r"FROM Account", ACCOUNTS)])
    assert demo.run(sf, date(2026, 9, 23)) == 0
    assert len(sf.upserts) == 5
    name, key, data = sf.upserts[0]
    assert name == "Opportunity" and key.startswith("Seed_Key__c/DEMO-OPP-")
    assert "Seed_Key__c" not in data


def test_run_fails_when_account_missing():
    sf = FakeSF([(r"FROM Account", ACCOUNTS[:3])])
    assert demo.run(sf, date(2026, 9, 23)) == 1
    assert sf.upserts == []
