"""Tests for scripts/find_opportunity.py (demo Opportunity lookup by Seed_Key__c)."""

import json

import pytest

import find_opportunity
from fake_sf import FakeSF

OPP = {"Id": "006000000000001AAA", "Name": "Retool - Quote Copilot demo (clean-midmarket)",
       "AccountId": "001000000000001AAA", "StageName": "Proposal/Price Quote",
       "Seed_Key__c": "DEMO-OPP-clean-midmarket"}


def test_finds_demo_opportunity_by_seed_key():
    sf = FakeSF([(r"Seed_Key__c = 'DEMO-OPP-clean-midmarket'", [OPP])])
    r = find_opportunity.find(sf, "clean-midmarket")
    assert r == {"scenario": "clean-midmarket", "seed_key": "DEMO-OPP-clean-midmarket",
                 "opportunity_id": OPP["Id"], "name": OPP["Name"],
                 "account_id": OPP["AccountId"], "stage": OPP["StageName"]}


def test_unknown_scenario_is_rejected_before_any_query():
    sf = FakeSF()
    with pytest.raises(ValueError):
        find_opportunity.find(sf, "x' OR Name != '")
    assert sf.queries == []


def test_missing_opportunity_raises():
    with pytest.raises(LookupError):
        find_opportunity.find(FakeSF(), "mis-segmented")


def test_cli(monkeypatch, capsys):
    sf = FakeSF([(r"DEMO-OPP-clean-midmarket", [OPP])])
    monkeypatch.setattr(find_opportunity, "connect", lambda: sf)
    assert find_opportunity.main(["clean-midmarket"]) == 0
    assert json.loads(capsys.readouterr().out)["opportunity_id"] == OPP["Id"]
    monkeypatch.setattr(find_opportunity, "connect", lambda: FakeSF())
    assert find_opportunity.main(["clean-midmarket"]) == 1
    assert "error" in json.loads(capsys.readouterr().out)
