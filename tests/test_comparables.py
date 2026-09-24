"""Unit tests for scripts/comparables.py with fake query results (offline).

Expected numbers below are counted by hand from FAKE_RECORDS.
"""

import json

import pytest

import comparables


def rec(stage, disc, outcome=None, mix="Platform Enterprise; Premium Support", seg="Enterprise"):
    return {"attributes": {"type": "Opportunity"}, "Id": "006x", "Name": "n",
            "StageName": stage, "Effective_Discount__c": disc, "Renewal_Outcome__c": outcome,
            "Product_Mix__c": mix, "Segment__c": seg, "Amount": 1000, "CloseDate": "2025-01-01"}


FAKE_RECORDS = [
    rec("Closed Won", 45, "Churned"),
    rec("Closed Won", 43, "Churned"),
    rec("Closed Won", 42, "Renewed"),
    rec("Closed Won", 38, "Too Early"),
    rec("Closed Lost", 36),
    rec("Closed Won", 25, "Renewed", mix="Platform Pro; Additional Seats"),
    rec("Closed Won", 22, "Expanded"),
    rec("Closed Won", 30, "Churned"),
    rec("Closed Won", 20, "Too Early"),
    rec("Closed Lost", 19, mix="Platform Pro"),
]


class FakeSF:
    def __init__(self, records):
        self.records = records
        self.queries = []

    def query_all(self, soql):
        self.queries.append(soql)
        return {"records": list(self.records), "totalSize": len(self.records), "done": True}


def test_soql_filters_seeded_closed_same_segment():
    q = comparables.build_soql("Enterprise")
    assert "FROM Opportunity" in q
    assert "Seed_Key__c LIKE 'SEED-OPP-%'" in q
    assert "IsClosed = true" in q
    assert "Segment__c = 'Enterprise'" in q
    assert "Product_Mix__c" in q.split("WHERE")[0]  # selected
    assert "Product_Mix__c LIKE" not in q


def test_soql_tier_filter():
    q = comparables.build_soql("Enterprise", tier="Platform Enterprise")
    assert "Product_Mix__c LIKE 'Platform Enterprise%'" in q


@pytest.mark.parametrize("segment, tier", [("Galactic", None), ("SMB", "Platform Ultra"),
                                           ("SMB' OR Name != '", None)])
def test_invalid_inputs_rejected(segment, tier):
    with pytest.raises(ValueError):
        comparables.build_soql(segment, tier)


def test_summary_counts():
    s = comparables.summarize(FAKE_RECORDS, proposed_discount=40, window=5)
    allc, near, low = s["all"], s["near_proposed"], s["lower_discount"]

    assert (allc["count"], allc["won"], allc["lost"]) == (10, 8, 2)
    assert allc["discount_pct"] == {"min": 19.0, "median": 33.0, "max": 45.0}
    assert allc["renewal_outcomes"] == {"Renewed": 2, "Expanded": 1, "Churned": 3,
                                        "Too Early": 2}
    assert (allc["matured"], allc["churned"], allc["churn_rate_pct"]) == (6, 3, 50.0)

    assert near["discount_range"] == ">= 35.00%"
    assert (near["count"], near["won"], near["lost"]) == (5, 4, 1)
    assert near["discount_pct"] == {"min": 36.0, "median": 42.0, "max": 45.0}
    assert near["renewal_outcomes"] == {"Renewed": 1, "Expanded": 0, "Churned": 2,
                                        "Too Early": 1}
    assert (near["matured"], near["churned"], near["churn_rate_pct"]) == (3, 2, 66.67)

    assert low["discount_range"] == "< 35.00%"
    assert (low["count"], low["won"], low["lost"]) == (5, 4, 1)
    assert low["discount_pct"] == {"min": 19.0, "median": 22.0, "max": 30.0}
    assert (low["matured"], low["churned"], low["churn_rate_pct"]) == (3, 1, 33.33)


def test_finding_cites_counts_not_just_a_trend():
    s = comparables.summarize(FAKE_RECORDS, proposed_discount=40, window=5)
    f = s["finding"]
    assert "2 of 3" in f and "1 of 3" in f
    assert "Too Early" in f


def test_empty_cohort_reports_zero_counts_and_no_rate():
    s = comparables.summarize(FAKE_RECORDS, proposed_discount=90, window=5)
    near = s["near_proposed"]
    assert near["count"] == 0 and near["discount_pct"] == {"min": None, "median": None,
                                                           "max": None}
    assert near["churn_rate_pct"] is None
    assert "0 of 0" in s["finding"] or "no " in s["finding"].lower()


def test_small_sample_is_flagged():
    s = comparables.summarize(FAKE_RECORDS[:2], proposed_discount=40, window=5)
    assert s["small_sample"] is True


def test_comparables_applies_tier_post_filter():
    sf = FakeSF(FAKE_RECORDS)
    s = comparables.comparables(sf, "Enterprise", 40, tier="Platform Enterprise")
    assert "Product_Mix__c LIKE 'Platform Enterprise%'" in sf.queries[0]
    assert s["all"]["count"] == 8  # the two Platform Pro deals are dropped
    assert s["segment"] == "Enterprise" and s["tier"] == "Platform Enterprise"


def test_cli(monkeypatch, capsys):
    monkeypatch.setattr(comparables, "connect", lambda: FakeSF(FAKE_RECORDS))
    assert comparables.main(["--segment", "Enterprise", "--discount", "40"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["near_proposed"]["count"] == 5


@pytest.mark.integration
def test_against_org_read_only():
    s = comparables.comparables(comparables.connect(), "Enterprise", 40)
    assert s["all"]["count"] > 0
    assert s["near_proposed"]["count"] + s["lower_discount"]["count"] == s["all"]["count"]
    assert s["near_proposed"]["matured"] >= 1
    assert "of" in s["finding"]
