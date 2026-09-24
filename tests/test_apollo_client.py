"""Unit tests for scripts/apollo_client.py. Offline: requests is always mocked.

Apollo enrichment costs credits, so nothing here may reach the network. The one
live test is marked `integration` and only reads a domain that is already cached.
"""

import json

import pytest

import apollo_client
from apollo_client import ApolloError


class FakeResponse:
    def __init__(self, status, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.text = text or (json.dumps(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


ORG_BODY = {"organization": {"name": "Example Co", "estimated_num_employees": 450}}


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if anything tries a real HTTP call."""
    def boom(*a, **k):
        raise AssertionError("network call attempted in a unit test")
    monkeypatch.setattr(apollo_client.requests, "get", boom)
    monkeypatch.setattr(apollo_client.requests, "post", boom)
    monkeypatch.setattr(apollo_client.requests, "request", boom)
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")


@pytest.fixture
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(apollo_client, "_sleep", calls.append)
    return calls


def script_responses(monkeypatch, responses):
    """Make requests.request return the given responses in order; record calls."""
    calls = []
    queue = list(responses)

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if not queue:
            raise AssertionError("more requests than scripted responses")
        return queue.pop(0)

    monkeypatch.setattr(apollo_client.requests, "request", fake_request)
    return calls


# --- headcount -> segment: one rule, reused everywhere -----------------------

@pytest.mark.parametrize("employees, segment", [
    (None, None), (0, "SMB"), (1, "SMB"), (199, "SMB"), (200, "Mid-Market"),
    (1300, "Mid-Market"), (2000, "Mid-Market"), (2001, "Enterprise"), (9300, "Enterprise"),
])
def test_segment_for_headcount(employees, segment):
    assert apollo_client.segment_for_headcount(employees) == segment


def test_seed_opportunities_reuses_the_same_rule():
    import seed_opportunities
    for n in (None, 199, 200, 2000, 2001):
        assert seed_opportunities.segment_for(n) == apollo_client.segment_for_headcount(n)


# --- cache ---------------------------------------------------------------------

def test_get_organization_reads_cache_without_network(tmp_path, monkeypatch, no_network):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_example.com.json").write_text(json.dumps(ORG_BODY))
    raw, source = apollo_client.get_organization("example.com")
    assert source == "cache"
    assert raw == ORG_BODY


def test_get_organization_normalises_domain(tmp_path, monkeypatch, no_network):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_example.com.json").write_text(json.dumps(ORG_BODY))
    raw, source = apollo_client.get_organization("https://www.Example.com/")
    assert source == "cache" and raw == ORG_BODY


def test_get_organization_live_writes_cache(tmp_path, monkeypatch, no_network, sleeps):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path / "cache")
    calls = script_responses(monkeypatch, [FakeResponse(200, ORG_BODY)])
    raw, source = apollo_client.get_organization("example.com")
    assert source == "live" and raw == ORG_BODY
    assert len(calls) == 1
    assert calls[0][2]["params"] == {"domain": "example.com"}
    assert json.loads((tmp_path / "cache" / "org_example.com.json").read_text()) == ORG_BODY
    # second call is served from cache (script has no more responses)
    assert apollo_client.get_organization("example.com")[1] == "cache"


def test_get_organization_refresh_bypasses_cache(tmp_path, monkeypatch, no_network, sleeps):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_example.com.json").write_text(json.dumps({"organization": {}}))
    script_responses(monkeypatch, [FakeResponse(200, ORG_BODY)])
    raw, source = apollo_client.get_organization("example.com", refresh=True)
    assert source == "live" and raw == ORG_BODY


def test_errors_are_not_cached(tmp_path, monkeypatch, no_network, sleeps):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    script_responses(monkeypatch, [FakeResponse(401, {"error_details": "bad key"})])
    with pytest.raises(ApolloError) as e:
        apollo_client.get_organization("example.com")
    assert e.value.status == 401
    assert not (tmp_path / "org_example.com.json").exists()


def test_empty_domain_rejected_before_request(no_network):
    with pytest.raises(ValueError):
        apollo_client.get_organization("  ")


# --- rate limits and transient errors -------------------------------------------

def test_429_honours_retry_after(monkeypatch, no_network, sleeps):
    calls = script_responses(monkeypatch, [
        FakeResponse(429, {"error": "rate limited"}, headers={"Retry-After": "7"}),
        FakeResponse(200, ORG_BODY),
    ])
    assert apollo_client.enrich_organization("example.com") == ORG_BODY
    assert len(calls) == 2
    assert sleeps == [7.0]


def test_429_without_retry_after_backs_off_exponentially(monkeypatch, no_network, sleeps):
    script_responses(monkeypatch, [
        FakeResponse(429, {}), FakeResponse(429, {}), FakeResponse(200, ORG_BODY)])
    assert apollo_client.enrich_organization("example.com") == ORG_BODY
    assert sleeps == [apollo_client.BACKOFF_BASE, apollo_client.BACKOFF_BASE * 2]


def test_transient_5xx_retried(monkeypatch, no_network, sleeps):
    script_responses(monkeypatch, [FakeResponse(502, None, text="bad gateway"),
                                   FakeResponse(504, {}), FakeResponse(200, ORG_BODY)])
    assert apollo_client.enrich_organization("example.com") == ORG_BODY
    assert len(sleeps) == 2


def test_gives_up_after_max_retries(monkeypatch, no_network, sleeps):
    n = apollo_client.MAX_RETRIES + 1
    calls = script_responses(monkeypatch, [FakeResponse(429, {"error": "slow down"})] * n)
    with pytest.raises(ApolloError) as e:
        apollo_client.enrich_organization("example.com")
    assert e.value.status == 429
    assert len(calls) == n
    assert len(sleeps) == apollo_client.MAX_RETRIES


def test_4xx_not_retried(monkeypatch, no_network, sleeps):
    calls = script_responses(monkeypatch, [FakeResponse(422, {"error_details": "bad"})])
    with pytest.raises(ApolloError):
        apollo_client.enrich_organization("example.com")
    assert len(calls) == 1 and sleeps == []


def test_retry_after_is_capped(monkeypatch, no_network, sleeps):
    script_responses(monkeypatch, [
        FakeResponse(429, {}, headers={"Retry-After": "100000"}), FakeResponse(200, ORG_BODY)])
    apollo_client.enrich_organization("example.com")
    assert sleeps == [apollo_client.MAX_SLEEP]


def test_search_people_titles_still_strips_personal_fields(monkeypatch, no_network, sleeps):
    body = {"people": [{"title": " CFO ", "name": "Secret Person", "email": "x@y.z"},
                       {"name": "No Title"}]}
    script_responses(monkeypatch, [FakeResponse(200, body)])
    assert apollo_client.search_people_titles("example.com", ["vp"], ["finance"]) == ["CFO"]


# --- verified segment / summary --------------------------------------------------

def test_verified_segment_from_cache(tmp_path, monkeypatch, no_network):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_big.com.json").write_text(
        json.dumps({"organization": {"name": "Big", "estimated_num_employees": 5700}}))
    (tmp_path / "org_unknown.com.json").write_text(json.dumps({"organization": {"name": "U"}}))
    (tmp_path / "org_none.com.json").write_text(json.dumps({}))
    assert apollo_client.verified_segment("big.com") == "Enterprise"
    assert apollo_client.verified_segment("unknown.com") is None
    assert apollo_client.verified_segment("none.com") is None


def test_organization_summary_shape(tmp_path, monkeypatch, no_network):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_example.com.json").write_text(json.dumps(ORG_BODY))
    assert apollo_client.organization_summary("example.com") == {
        "domain": "example.com", "name": "Example Co", "employees": 450,
        "verified_segment": "Mid-Market", "source": "cache"}


def test_cli_prints_summary_json(tmp_path, monkeypatch, no_network, capsys):
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_example.com.json").write_text(json.dumps(ORG_BODY))
    assert apollo_client.main(["example.com"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verified_segment"] == "Mid-Market" and out["source"] == "cache"


def test_seed_accounts_uses_shared_cache_loader(tmp_path, monkeypatch, no_network):
    import seed_accounts
    monkeypatch.setattr(apollo_client, "CACHE_DIR", tmp_path)
    (tmp_path / "org_example.com.json").write_text(json.dumps(ORG_BODY))
    assert seed_accounts.load_org("example.com", False) == (ORG_BODY, "cache")


# --- integration: cached domain only, never spends a credit -----------------------

@pytest.mark.integration
def test_cached_demo_domains_resolve_to_expected_segments():
    expected = {"retool.com": "Mid-Market", "postman.com": "Mid-Market",
                "mongodb.com": "Enterprise", "snowflake.com": "Enterprise"}
    for domain, segment in expected.items():
        cached = apollo_client.CACHE_DIR / f"org_{domain}.json"
        assert cached.exists(), f"{domain} not cached; refusing to spend a credit"
        summary = apollo_client.organization_summary(domain)
        assert summary["source"] == "cache", f"{domain} not cached; refusing to spend a credit"
        assert summary["verified_segment"] == segment
