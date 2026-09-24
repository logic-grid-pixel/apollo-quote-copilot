"""Thin Apollo API client shared by the Quote Copilot scripts.

Credits: organization enrichment costs 1 credit per call, so get_organization()
caches every successful response in data/cache/org_{domain}.json and only goes
live when the cache is missing or refresh=True.

Rate limits: HTTP 429 honours Retry-After (capped at MAX_SLEEP), otherwise
exponential backoff from BACKOFF_BASE. Transient 5xx responses are retried the
same way. After MAX_RETRIES retries the last error is raised as ApolloError.

The headcount -> segment rule lives here (segment_for_headcount) and is reused
by the seed scripts and the pre-flight, so there is exactly one definition.

CLI:  python scripts/apollo_client.py <domain> [--refresh]
      prints {domain, name, employees, verified_segment, source: cache|live}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

BASE = "https://api.apollo.io/api/v1"
TIMEOUT = 30
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

MAX_RETRIES = 4          # retries after the first attempt
BACKOFF_BASE = 2.0       # seconds; doubles each retry
MAX_SLEEP = 60.0         # never wait longer than this for one retry
RETRY_STATUSES = {429, 500, 502, 503, 504}

# Segment boundaries on Apollo estimated_num_employees (inclusive upper bounds).
SMB_MAX_EMPLOYEES = 199
MID_MARKET_MAX_EMPLOYEES = 2000

_sleep = time.sleep  # swapped out in tests


class ApolloError(RuntimeError):
    def __init__(self, status: int, detail):
        super().__init__(f"Apollo API error {status}: {detail}")
        self.status = status
        self.detail = detail


def segment_for_headcount(employees) -> Optional[str]:
    """<200 SMB, 200-2000 Mid-Market, >2000 Enterprise; None when unknown."""
    if employees is None:
        return None
    if employees <= SMB_MAX_EMPLOYEES:
        return "SMB"
    if employees <= MID_MARKET_MAX_EMPLOYEES:
        return "Mid-Market"
    return "Enterprise"


def normalize_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    d = d.split("/")[0]
    if d.startswith("www."):
        d = d[4:]
    if not d:
        raise ValueError("domain is required")
    return d


def _api_key() -> str:
    load_dotenv(".env")
    key = os.getenv("APOLLO_API_KEY")
    if not key:
        raise ApolloError(0, "APOLLO_API_KEY is not set in .env")
    return key


def _body(resp) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {"raw": (resp.text or "")[:300]}


def _retry_delay(resp, attempt: int) -> float:
    """Seconds to wait before retry number `attempt` (0-based)."""
    header = (resp.headers or {}).get("Retry-After")
    if header is not None:
        try:
            return min(max(float(header), 0.0), MAX_SLEEP)
        except ValueError:
            pass  # HTTP-date form: fall back to backoff
    return min(BACKOFF_BASE * (2 ** attempt), MAX_SLEEP)


def _request(method: str, path: str, **kwargs):
    """Send a request, retrying 429 and transient 5xx. Returns (status, body)."""
    headers = {"x-api-key": _api_key(), "accept": "application/json"}
    attempt = 0
    while True:
        resp = requests.request(method, f"{BASE}{path}", headers=headers,
                                timeout=TIMEOUT, **kwargs)
        if resp.status_code not in RETRY_STATUSES or attempt >= MAX_RETRIES:
            return resp.status_code, _body(resp)
        _sleep(_retry_delay(resp, attempt))
        attempt += 1


def enrich_organization(domain: str) -> dict:
    """Return Apollo's raw JSON for GET /organizations/enrich?domain=... (1 credit)."""
    status, body = _request("GET", "/organizations/enrich", params={"domain": domain})
    if status != 200:
        raise ApolloError(status, body.get("error_details") or body.get("error") or body)
    return body


def search_people_titles(domain: str, seniorities: list, title_keywords: list,
                         per_page: int = 25) -> list:
    """Return only the job titles from POST /mixed_people/api_search (no credits).

    Names, emails and every other personal field are discarded here so they
    never reach callers, caches or logs. Requires a paid Apollo plan; the Free
    plan answers 403 API_INACCESSIBLE.
    """
    status, body = _request(
        "POST", "/mixed_people/api_search",
        json={"q_organization_domains_list": [domain], "person_seniorities": seniorities,
              "person_titles": title_keywords, "per_page": per_page, "page": 1})
    if status != 200:
        raise ApolloError(status, body.get("error") or body.get("error_details") or body)
    return [p["title"].strip() for p in body.get("people") or [] if p.get("title")]


def get_organization(domain: str, refresh: bool = False):
    """Return (raw Apollo enrichment JSON, "cache" | "live").

    Reads data/cache/org_{domain}.json unless refresh is set; a live call writes
    the cache. Errors are raised and never cached.
    """
    domain = normalize_domain(domain)
    path = CACHE_DIR / f"org_{domain}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text()), "cache"
    raw = enrich_organization(domain)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2))
    return raw, "live"


def organization_summary(domain: str, refresh: bool = False) -> dict:
    domain = normalize_domain(domain)
    raw, source = get_organization(domain, refresh)
    org = (raw or {}).get("organization") or {}
    employees = org.get("estimated_num_employees")
    return {"domain": domain, "name": org.get("name"), "employees": employees,
            "verified_segment": segment_for_headcount(employees), "source": source}


def verified_segment(domain: str, refresh: bool = False) -> Optional[str]:
    """Segment from Apollo headcount, or None if Apollo has no employee count."""
    return organization_summary(domain, refresh)["verified_segment"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apollo organization lookup (cached)")
    parser.add_argument("domain")
    parser.add_argument("--refresh", action="store_true",
                        help="ignore the cache and re-fetch (1 Apollo credit)")
    args = parser.parse_args(argv)
    try:
        summary = organization_summary(args.domain, args.refresh)
    except (ApolloError, ValueError) as e:
        print(json.dumps({"domain": args.domain, "error": str(e)}))
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
