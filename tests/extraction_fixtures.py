"""Schema-conformant extraction documents built from eval/specs/*.yaml.

Values come from each spec's expected_extraction / expected_open_questions; the
citations below are real excerpts from data/deals/<scenario>/ (the citation
checker in scripts/validate_extraction.py verifies them against the files).
"""

import copy
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "eval" / "specs"
DEALS = ROOT / "data" / "deals"
SCENARIOS = ["clean-midmarket", "conflicting-seats", "mis-segmented", "aggressive-discount"]

FIELDS = ["account_domain", "company_name", "rep_stated_segment", "products", "seat_count",
          "term_months", "start_date", "payment_terms", "requested_discount_pct", "ramp",
          "company_headcount", "contacts"]

COMPANY = {"clean-midmarket": "Retool", "conflicting-seats": "Postman",
           "mis-segmented": "MongoDB", "aggressive-discount": "Snowflake"}

CITATIONS = {
    "clean-midmarket": {
        "account_domain": 'rep_notes: "Acct: Retool (retool.com)"',
        "company_name": 'rep_notes: "Acct: Retool (retool.com)"',
        "rep_stated_segment": 'rep_notes: "Seg: Mid-Market"',
        "products": ('C1 [00:17:15] "So Pro is what we\'re planning around." | '
                     'C2 [00:13:42] "Yeah, 120. Same number I gave Alex on the first call." | '
                     'C2 [00:28:58] "Okay, implementation services, in."'),
        "seat_count": ('C1 [00:08:20] "…it\'s about 120 engineers who\'d need access." | '
                       'C2 [00:13:42] "Yeah, 120. Same number I gave Alex on the first call."'),
        "term_months": 'C2 [00:29:31] "Two years. I don\'t want to re-paper this every twelve months…"',
        "start_date": 'C2 [00:26:37] "…Subscription starts November 1."',
        "payment_terms": 'C2 [00:31:03] "Net 30 is fine."',
        "requested_discount_pct": 'C2 [00:31:57] "I\'d like to see something around 12 percent off list."',
        "contacts": ('C1 [header] "Dana Whitfield, Director of Platform Engineering, Retool" | '
                     'C2 [header] "Marcus Oyelaran, VP Engineering, Retool" | '
                     'rep_notes: "Marcus O (VP Eng) = signer"'),
    },
    "conflicting-seats": {
        "account_domain": 'rep_notes: "Acct: Postman (postman.com)"',
        "company_name": 'rep_notes: "Acct: Postman (postman.com)"',
        "rep_stated_segment": 'rep_notes: "Seg: Mid-Market"',
        "products": 'C3 [00:04:57] "So, two-year term, Pro, which is what we talked about."',
        "term_months": 'C2 [00:42:02] "We\'d want a two-year term."',
        "start_date": 'C3 [00:08:44] "Still October 1. Top of the quarter."',
        "payment_terms": 'C3 [00:05:39] "Net 30 is fine, that\'s what we do."',
        "requested_discount_pct": 'C3 [00:06:02] "I\'d like to see 15 percent off."',
        "contacts": ('C1 [header] "Priya Raghunathan, VP Engineering, Postman" | '
                     'C2 [header] "Tom Abara, Staff Engineer, Postman"'),
    },
    "mis-segmented": {
        "account_domain": 'rep_notes: "Acct: MongoDB (mongodb.com)"',
        "company_name": 'rep_notes: "Acct: MongoDB (mongodb.com)"',
        "rep_stated_segment": 'rep_notes: "Seg: SMB"',
        "products": 'C2 [00:26:44] "Twelve months, Pro tier, 60 seats."',
        "seat_count": ('C1 [00:12:43] "So I was thinking 60 seats." | '
                       'C2 [00:05:14] "Pro, 60 seats. That\'s what we talked about."'),
        "term_months": 'C2 [00:09:40] "Twelve months to start."',
        "start_date": ('C2 [00:13:11] "…we start right after everyone\'s back from the break. '
                       'January 5."'),
        "payment_terms": 'C2 [00:32:36] "Net 30 is standard for us, that\'s fine."',
        "requested_discount_pct": 'C2 [00:06:36] "…if you could do 18 percent off…"',
        "contacts": ('C1 [header] "Sam Devarakonda, Engineering Manager, Platform, MongoDB" | '
                     'C2 [header] "Reena Kapoor, Procurement Analyst, MongoDB"'),
    },
    "aggressive-discount": {
        "account_domain": 'rep_notes: "Acct: Snowflake (snowflake.com)"',
        "company_name": 'rep_notes: "Acct: Snowflake (snowflake.com)"',
        "rep_stated_segment": 'rep_notes: "Seg: Enterprise"',
        "products": ('C2 [00:35:28] "Yes. Enterprise plus premium support." | '
                     'C2 [00:06:34] "That\'s where the 200 seats come from."'),
        "seat_count": 'C1 [00:13:00] "…we\'d want to start with 200 seats."',
        "term_months": 'C2 [00:26:36] "A three-year term, with price protection the whole way through."',
        "payment_terms": 'C3 [00:16:09] "We need net 60."',
        "requested_discount_pct": 'C3 [00:04:36] "Forty percent. Across the term."',
        "ramp": ('C2 [00:08:37] "…roughly double. Call it 400-ish in total by the time they\'re '
                 'fully on." | C2 [00:13:36] "200, then roughly double as the second unit comes '
                 'on, then around 600 once the third unit\'s in."'),
        "contacts": ('C1 [header] "Ellis Moreau, Director of Infrastructure, Snowflake" | '
                     'C1 [header] "Wen Li, Principal Engineer, Snowflake"'),
    },
}

QUESTION_CONTEXT = {
    ("conflicting-seats", "seat_count"): {
        "source_citation": None,
        "candidates": [
            {"value": 50, "source_citation":
                'C1 [00:10:27] "But it\'s roughly 50 engineers who\'d need access."'},
            {"value": 80, "source_citation":
                'C3 [00:09:11] "…so it\'s more like 80 people across platform and data."'},
        ],
    },
    ("aggressive-discount", "start_date"): {
        "source_citation": 'C3 [00:23:23] "As soon as we\'re through security review."'},
    ("aggressive-discount", "economic_buyer"): {
        "source_citation": 'rep_notes: "no EB met yet"'},
    ("mis-segmented", "economic_buyer"): {
        "source_citation": 'rep_notes: "procurement signs off over some threshold, Sam doesnt know what"'},
}

DOMAINS = {"clean-midmarket": "retool.com", "conflicting-seats": "postman.com",
           "mis-segmented": "mongodb.com", "aggressive-discount": "snowflake.com"}


def load_spec(name: str) -> dict:
    return yaml.safe_load((SPECS / f"{name}.yaml").read_text())


def source_files(name: str) -> list:
    return sorted(f"data/deals/{name}/{p.name}" for p in (DEALS / name).glob("*.md"))


def spec_document(name: str) -> dict:
    spec = load_spec(name)
    exp = spec["expected_extraction"]
    values = {
        "account_domain": spec["account_domain"],
        "company_name": COMPANY[name],
        "rep_stated_segment": spec["rep_stated_segment"],
        "company_headcount": exp.get("company_headcount"),
    }
    for field in ("products", "seat_count", "term_months", "start_date", "payment_terms",
                  "requested_discount_pct", "ramp", "contacts"):
        v = exp.get(field)
        values[field] = v.isoformat() if isinstance(v, date) else copy.deepcopy(v)
    doc = {"scenario": name, "source_files": source_files(name)}
    for field in FIELDS:
        v = values[field]
        doc[field] = {"value": v,
                      "source_citation": CITATIONS[name][field] if v is not None else None,
                      "confidence": ("medium" if field == "ramp" else "high")}
    questions = []
    for q in spec.get("expected_open_questions") or []:
        q = dict(q)
        q.update(QUESTION_CONTEXT.get((name, q["field"]), {}))
        questions.append(q)
    doc["open_questions"] = questions
    return doc
