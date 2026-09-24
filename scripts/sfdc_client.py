"""Write a pre-flighted, priced quote into Salesforce.

create_quote() makes, in order:
  1. a Draft Quote on the Opportunity with the band segment's price book and the
     eight Quote Copilot fields filled from the pre-flight
  2. QuoteLineItems: UnitPrice = list, Discount = line discount %, one line per
     product per year of the term (so the Quote total equals pricing.py's TCV;
     ramped deals carry each year's seat count), one-time lines once in year 1
  3. the quote PDF as a ContentVersion published to the Quote (bytes supplied
     by the caller; scripts/render_order_form.py renders it)
  4. a Task: Needs Approval -> owned by the Deal Desk queue; Blocked -> owned by
     the Opportunity owner, listing the open questions. WhatId is the Quote,
     falling back to the Opportunity if Salesforce refuses it. Ready -> no task.

All inputs are validated, and every lookup (Opportunity, price book, entries,
queue) is done, before the first write. If a write fails, everything created so
far is deleted again.

CLI:  python scripts/sfdc_client.py <extraction.json> --opportunity 006... --dry-run
      python scripts/sfdc_client.py <extraction.json> --opportunity 006... [--pdf quote.pdf]
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import preflight
import pricing
from sf_session import connect

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")
VERIFIED_VALUES = SEGMENTS + ("Unverified",)
LEVELS = ("Rep", "Manager", "VP", "CFO")
STATUSES = (preflight.READY, preflight.NEEDS_APPROVAL, preflight.BLOCKED)
QUEUE_DEVELOPER_NAME = "Deal_Desk"
OPP_ID_RE = re.compile(r"^006[A-Za-z0-9]{12}([A-Za-z0-9]{3})?$")
MAX_PDF_BYTES = 25 * 1024 * 1024
QUOTE_VALID_DAYS = 30
TASK_DUE_DAYS = 2
LONG_TEXT_MAX = 32768
TASK_DESCRIPTION_MAX = 32000


class QuoteInputError(ValueError):
    """Inputs are invalid or the org is missing something; nothing was written."""


# --- validation ------------------------------------------------------------------------

def validate_inputs(opportunity_id, pf: dict, pricing_result: dict, pdf_bytes=None,
                    quote_name=None):
    problems = []
    if not isinstance(opportunity_id, str) or not OPP_ID_RE.match(opportunity_id):
        problems.append(f"opportunity_id {opportunity_id!r} is not an Opportunity Id")
    if not isinstance(pf, dict):
        raise QuoteInputError("preflight result is required")
    checks = [("preflight_status", STATUSES, False), ("approval_level_required", LEVELS, True),
              ("verified_segment", VERIFIED_VALUES, False), ("rep_segment", SEGMENTS, True),
              ("band_segment", SEGMENTS, False)]
    for field, allowed, nullable in checks:
        v = pf.get(field)
        if not (v in allowed or (nullable and v is None)):
            problems.append(f"preflight {field}={v!r} not in {allowed}")
    if not isinstance(pf.get("segment_mismatch"), bool):
        problems.append("preflight segment_mismatch must be true/false")
    d = pf.get("effective_discount_pct")
    if d is not None and (isinstance(d, bool) or not isinstance(d, (int, float))
                          or not 0 <= d <= 100):
        problems.append(f"preflight effective_discount_pct={d!r} must be 0-100 or null")

    status = (pricing_result or {}).get("status")
    if status not in ("priced", "blocked"):
        problems.append("pricing result missing or has no status")
    elif status == "priced":
        if pricing_result.get("segment") != pf.get("band_segment"):
            problems.append(f"priced on {pricing_result.get('segment')!r} but pre-flight "
                            f"bands use {pf.get('band_segment')!r}")
    elif pf.get("preflight_status") != preflight.BLOCKED:
        problems.append("only a Blocked quote may be created without priced lines")

    if pdf_bytes is not None:
        if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes.startswith(b"%PDF-"):
            problems.append("pdf_bytes must be PDF bytes (starting with %PDF-)")
        elif len(pdf_bytes) > MAX_PDF_BYTES:
            problems.append("pdf_bytes larger than 25 MB")
    if quote_name is not None and (not quote_name.strip() or len(quote_name) > 255):
        problems.append("quote_name must be 1-255 characters")
    if problems:
        raise QuoteInputError("; ".join(problems))


# --- readable text for the long text fields ------------------------------------------------

def _candidate_text(c: dict) -> str:
    value = c.get("value")
    shown = _short(value) if isinstance(value, (list, dict)) else str(value)
    cite = c.get("source_citation")
    return f"{shown} ({cite})" if cite else shown


def open_questions_text(pf: dict):
    """One line per question: tag, field, text, then every candidate value with its
    citation and the question's own source citation, so nothing the extraction
    surfaced is lost on the Quote or in the Task."""
    rows, covered = [], set()
    for q in pf.get("open_questions") or []:
        tag = "BLOCKING" if q.get("blocking") else "non-blocking"
        row = f"[{tag}] {q.get('field')}: {q.get('text')}"
        if q.get("candidates"):
            row += " | candidates: " + "; ".join(_candidate_text(c) for c in q["candidates"])
        if q.get("source_citation"):
            row += f" | source: {q['source_citation']}"
        rows.append(row)
        if q.get("blocking"):
            covered.add(q.get("field"))
    for f in pf.get("blocked_fields") or []:
        if f not in covered:
            rows.append(f"[BLOCKING] {f}: not stated or unresolved in the calls")
    return "\n".join(rows)[:LONG_TEXT_MAX] or None


def _short(value) -> str:
    if isinstance(value, list) and value and isinstance(value[0], dict) and "name" in value[0]:
        return ", ".join(f"{p['name']} x{p.get('quantity') if p.get('quantity') is not None else '?'}"
                         for p in value)
    if isinstance(value, (list, dict)):
        text = json.dumps(value)
    else:
        text = str(value)
    return text if len(text) <= 200 else text[:197] + "..."


def source_citations_text(extraction: dict):
    if not extraction:
        return None
    rows = []
    for field, f in extraction.items():
        if field == "open_questions" or not isinstance(f, dict) or "value" not in f:
            continue
        cite = f.get("source_citation")
        value = "null" if f.get("value") is None else _short(f["value"])
        rows.append(f"{field}: {value} | source: {cite or 'none'} | "
                    f"confidence: {f.get('confidence') or 'n/a'}")
    return "\n".join(rows)[:LONG_TEXT_MAX] or None


# --- plan (pure) ------------------------------------------------------------------------------

def _service_date(start, year: int):
    if not start:
        return None
    try:
        d = date.fromisoformat(str(start))
    except ValueError:
        return None
    y = d.year + year - 1
    try:
        return d.replace(year=y).isoformat()
    except ValueError:  # 29 Feb
        return d.replace(year=y, day=28).isoformat()


def plan_lines(pricing_result: dict, start_date=None) -> list:
    if not pricing_result or pricing_result.get("status") != "priced":
        return []
    n = len(pricing_result["years"])
    out, sort = [], 0
    for y in pricing_result["years"]:
        for ln in y["lines"]:
            sort += 1
            unit = Fraction(str(ln["unit_list_price"]))
            desc = f"Year {ln['year']} of {n} - {ln['product']}"
            if ln["billing"] == "one_time":
                desc += " (one-time)"
            elif ln["months"] < 12:
                unit = unit * Fraction(ln["months"], 12)
                desc += f" ({ln['months']} months, list prorated)"
            row = {"product": ln["product"], "product_code": ln["product_code"],
                   "year": ln["year"], "Quantity": ln["quantity"],
                   "UnitPrice": pricing.money(unit), "Discount": ln["discount_pct"],
                   "Description": desc, "SortOrder": sort}
            sd = _service_date(start_date, ln["year"])
            if sd:
                row["ServiceDate"] = sd
            out.append(row)
    return out


def _quote_description(pf, pr) -> str:
    if pr and pr.get("status") == "priced":
        t = pr["totals"]
        return (f"Quote Copilot draft on the {pr['segment']} price book, {pr['term_months']} "
                f"months. TCV ${t['tcv']:,.2f}; ACV ${t['acv']:,.2f}; list TCV "
                f"${t['list_tcv']:,.2f}; blended discount {t['blended_discount_pct']:.2f}%. "
                "All figures computed by pricing.py.")
    return ("Quote Copilot draft, NOT PRICED: blocked on " +
            ", ".join(pf.get("blocked_fields") or ["open questions"]) + ".")


def _task_plan(pf: dict, quote_name: str, today: date):
    status = pf["preflight_status"]
    if status == preflight.READY:
        return None
    alt = (pf.get("suggested_alternative") or {}).get("summary")
    reasons = "\n".join(f"- {r}" for r in pf.get("reasons") or [])
    if status == preflight.BLOCKED:
        questions = open_questions_text(pf) or ""
        body = ("Open questions to resolve before this quote can be priced or sent:\n"
                + "\n".join(f"- {q}" for q in questions.splitlines())
                + f"\n\nPre-flight:\n{reasons}")
        if alt:
            body += f"\n\nSuggested: {alt}"
        return {"assign_to": "opportunity_owner",
                "Subject": f"Resolve open questions: {quote_name}"[:255],
                "Description": body[:TASK_DESCRIPTION_MAX], "Priority": "High",
                "Status": "Not Started",
                "ActivityDate": (today + timedelta(days=TASK_DUE_DAYS)).isoformat()}
    level = pf.get("approval_level_required") or "unknown"
    breaches = ", ".join(pf.get("thresholds_breached") or []) or "none"
    body = (f"Approval required: {level}\nThresholds breached: {breaches}\n"
            f"Rep segment: {pf.get('rep_segment')}; verified segment: "
            f"{pf.get('verified_segment')}; mismatch: {pf.get('segment_mismatch')}\n"
            f"Effective discount: {pf.get('effective_discount_pct')}%\n\nReasons:\n{reasons}")
    if alt:
        body += f"\n\nSuggested alternative: {alt}"
    return {"assign_to": "deal_desk_queue",
            "Subject": f"Deal Desk review ({level}): {quote_name}"[:255],
            "Description": body[:TASK_DESCRIPTION_MAX],
            "Priority": "High" if level in ("VP", "CFO") else "Normal",
            "Status": "Not Started",
            "ActivityDate": (today + timedelta(days=TASK_DUE_DAYS)).isoformat()}


def plan_quote(pf: dict, pricing_result: dict, extraction: dict = None,
               opportunity_id: str = None, quote_name: str = None,
               opportunity_name: str = None, pdf_bytes=None, today: date = None) -> dict:
    """Every record create_quote() would write, without Salesforce Ids resolved."""
    today = today or date.today()
    segment = pf["band_segment"]
    name = quote_name or (f"{opportunity_name or 'Opportunity'} - {segment} quote "
                          f"{today.isoformat()}")[:255]
    start = pricing.field_value(extraction or {}, "start_date")
    quote = {
        "Name": name, "OpportunityId": opportunity_id, "Status": "Draft",
        "ExpirationDate": (today + timedelta(days=QUOTE_VALID_DAYS)).isoformat(),
        "Description": _quote_description(pf, pricing_result),
        "Rep_Segment__c": pf.get("rep_segment"),
        "Verified_Segment__c": pf["verified_segment"],
        "Segment_Mismatch__c": pf["segment_mismatch"],
        "Effective_Discount__c": pf.get("effective_discount_pct"),
        "Approval_Level_Required__c": pf.get("approval_level_required"),
        "Preflight_Status__c": pf["preflight_status"],
        "Open_Questions__c": open_questions_text(pf),
        "Source_Citations__c": source_citations_text(extraction),
    }
    pdf = None
    if pdf_bytes is not None:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:120] or "quote"
        pdf = {"Title": name, "PathOnClient": f"{safe}.pdf", "bytes": len(pdf_bytes)}
    return {"price_book": segment, "quote": quote,
            "lines": plan_lines(pricing_result, start),
            "pdf": pdf, "task": _task_plan(pf, name, today)}


# --- execution ---------------------------------------------------------------------------------

def _q(sf, soql):
    return sf.query(soql)["records"]


def _resolve(sf, opportunity_id, plan):
    opp = _q(sf, "SELECT Id, Name, OwnerId, Pricebook2Id, AccountId FROM Opportunity "
                 f"WHERE Id = '{opportunity_id}'")
    if not opp:
        raise QuoteInputError(f"Opportunity {opportunity_id} not found")
    book = _q(sf, "SELECT Id, Name FROM Pricebook2 WHERE IsActive = true AND IsStandard = false "
                  f"AND Name = '{plan['price_book']}'")
    if not book:
        raise QuoteInputError(f"no active '{plan['price_book']}' price book")
    entries = {}
    if plan["lines"]:
        for e in _q(sf, "SELECT Id, Product2Id, UnitPrice, Product2.ProductCode FROM "
                        f"PricebookEntry WHERE Pricebook2Id = '{book[0]['Id']}' "
                        "AND IsActive = true"):
            entries[e["Product2"]["ProductCode"]] = e["Id"]
        missing = sorted({ln["product_code"] for ln in plan["lines"]} - set(entries))
        if missing:
            raise QuoteInputError(f"no active price book entry in {plan['price_book']} for "
                                  + ", ".join(missing))
    queue_id = None
    if plan["task"] and plan["task"]["assign_to"] == "deal_desk_queue":
        queue = _q(sf, "SELECT Id FROM Group WHERE Type = 'Queue' "
                       f"AND DeveloperName = '{QUEUE_DEVELOPER_NAME}'")
        if not queue:
            raise QuoteInputError(f"queue {QUEUE_DEVELOPER_NAME} not found")
        queue_id = queue[0]["Id"]
    return opp[0], book[0]["Id"], entries, queue_id


def delete_created(sf, created: dict):
    """Delete what create_quote made (Task, PDF document, Quote and its lines)."""
    errors = []
    steps = [("Task", created.get("task_id")),
             ("ContentDocument", created.get("content_document_id")),
             ("Quote", created.get("quote_id"))]
    for sobject, rid in steps:
        if rid:
            try:
                getattr(sf, sobject).delete(rid)
            except Exception as e:  # noqa: BLE001 - keep cleaning up
                errors.append(f"{sobject} {rid}: {e}")
    return errors


def create_quote(sf, opportunity_id: str, pf: dict, pricing_result: dict,
                 extraction: dict = None, pdf_bytes=None, quote_name: str = None) -> dict:
    validate_inputs(opportunity_id, pf, pricing_result, pdf_bytes, quote_name)
    plan = plan_quote(pf, pricing_result, extraction, opportunity_id, quote_name,
                      pdf_bytes=pdf_bytes)
    opp, book_id, entries, queue_id = _resolve(sf, opportunity_id, plan)
    if quote_name is None:
        plan = plan_quote(pf, pricing_result, extraction, opportunity_id,
                          opportunity_name=opp["Name"], pdf_bytes=pdf_bytes)

    created = {"quote_id": None, "quote_name": plan["quote"]["Name"], "price_book_id": book_id,
               "line_ids": [], "content_version_id": None, "content_document_id": None,
               "task_id": None, "task_what_id": None, "task_owner_id": None,
               "task_what_fallback_reason": None}
    try:
        created["quote_id"] = sf.Quote.create({**plan["quote"],
                                               "Pricebook2Id": book_id})["id"]
        for ln in plan["lines"]:
            data = {k: v for k, v in ln.items() if k[0].isupper()}
            data.update(QuoteId=created["quote_id"],
                        PricebookEntryId=entries[ln["product_code"]])
            created["line_ids"].append(sf.QuoteLineItem.create(data)["id"])
        if pdf_bytes is not None:
            cv = sf.ContentVersion.create({
                "Title": plan["pdf"]["Title"], "PathOnClient": plan["pdf"]["PathOnClient"],
                "VersionData": base64.b64encode(bytes(pdf_bytes)).decode("ascii"),
                "FirstPublishLocationId": created["quote_id"]})
            created["content_version_id"] = cv["id"]
            doc = _q(sf, "SELECT ContentDocumentId FROM ContentVersion "
                         f"WHERE Id = '{cv['id']}'")
            created["content_document_id"] = doc[0]["ContentDocumentId"] if doc else None
        if plan["task"]:
            t = {k: v for k, v in plan["task"].items() if k != "assign_to"}
            owner = queue_id if plan["task"]["assign_to"] == "deal_desk_queue" \
                else opp["OwnerId"]
            t["OwnerId"] = owner
            try:
                created["task_id"] = sf.Task.create({**t, "WhatId": created["quote_id"]})["id"]
                created["task_what_id"] = created["quote_id"]
            except Exception as e:  # noqa: BLE001 - org may not allow activities on Quote
                created["task_what_fallback_reason"] = str(e)[:300]
                created["task_id"] = sf.Task.create({**t, "WhatId": opportunity_id})["id"]
                created["task_what_id"] = opportunity_id
            created["task_owner_id"] = owner
    except Exception:
        leftovers = delete_created(sf, created)
        for msg in leftovers:
            print(f"ROLLBACK FAILED  {msg}", file=sys.stderr)
        raise
    return created


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a Draft Quote from an extraction")
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--opportunity", required=True, help="Opportunity Id (006...)")
    parser.add_argument("--pdf", type=Path, default=None, help="quote PDF to attach")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the planned records; no Salesforce calls")
    args = parser.parse_args(argv)

    extraction = json.loads(args.extraction.read_text())
    pf = preflight.run(extraction)
    pdf = args.pdf.read_bytes() if args.pdf else None
    pr = pf.get("pricing")
    if args.dry_run:
        validate_inputs(args.opportunity, pf, pr, pdf)
        plan = plan_quote(pf, pr, extraction, args.opportunity, pdf_bytes=pdf)
        print(json.dumps({**plan, "preflight": {k: v for k, v in pf.items() if k != "pricing"}},
                         indent=2, default=str))
        return 0
    result = create_quote(connect(), args.opportunity, pf, pr, extraction, pdf)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
