"""Render the internal deal brief (markdown) from the JSON in output/<scenario>/.

Sections: status and reasons; segment (rep vs Apollo-verified, mismatch
explained); pricing summary; approval (level, breached thresholds, suggested
alternative); comparables with counts (never a bare trend word; small samples
flagged); open questions with citations and conflict candidates; signals
(contacts / buying roles, headcount, buying-process mentions in the deal files);
Salesforce records.

Every number is copied from the JSON files (pricing.json, preflight.json,
apollo.json, comparables.json, sfdc_result.json) and only formatted here.
Required: preflight.json and extraction.json; everything else is optional and
reported as missing when absent.

CLI:  python scripts/render_deal_brief.py output/<scenario> [--deal-dir data/deals/<scenario>]
      writes output/<scenario>/deal_brief.md, prints {"deal_brief": <path>}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import output_files
from output_files import money, pct, value

ROOT = Path(__file__).resolve().parent.parent
DEALS = ROOT / "data" / "deals"
BRIEF_NAME = "deal_brief.md"
BLOCKED = "Blocked on Open Questions"
TURN_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")
# Buying-process language that tends to mark a larger organisation. Context for
# Deal Desk only: Apollo headcount stays the segment authority.
PROCESS_PHRASES = ["master agreement", "vendor onboarding", "supplier", "security review",
                   "procurement", "legal review", "MSA", "DPA"]
EXCERPT_MAX = 180


def _usd(x) -> str:
    return "n/a" if x is None else f"${money(x)}"


def _cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _yes(b) -> str:
    return "yes" if b else "no"


# --- sections ---------------------------------------------------------------------------

def _status(pf) -> list:
    reasons = pf.get("reasons") or []
    out = [f"**Status: {pf.get('preflight_status')}**", ""]
    out += [f"- {r}" for r in reasons] or ["- None"]
    return out


def _segment(pf, apollo, ext) -> list:
    rep, verified = pf.get("rep_segment"), pf.get("verified_segment")
    employees = (apollo or {}).get("employees")
    emp = "n/a" if employees is None else f"{employees:,}"
    out = ["## Segment", "",
           f"- Rep-stated: {rep or 'not stated'}",
           f"- Verified (Apollo): {verified} ({emp} employees, source: "
           f"{(apollo or {}).get('source') or 'n/a'})",
           f"- Mismatch: {_yes(pf.get('segment_mismatch'))}",
           f"- Price book and bands used: {pf.get('band_segment') or 'n/a'}"]
    if pf.get("segment_mismatch"):
        out.append(f"- Why it matters: the rep tagged the account {rep}; Apollo reports "
                   f"{emp} employees, which is {verified}. The price book and discount bands "
                   f"use {pf.get('band_segment')}.")
        if pf.get("approval_level_on_rep_segment"):
            out.append(f"- On the rep's {rep} segment this would need "
                       f"{pf['approval_level_on_rep_segment']} approval; on "
                       f"{pf.get('band_segment')} it needs "
                       f"{pf.get('approval_level_required') or 'n/a'}.")
    elif verified == "Unverified":
        out.append("- Apollo has no employee count: bands use the rep's segment; Deal Desk to "
                   "confirm headcount.")
    hc = (ext or {}).get("company_headcount") or {}
    if hc.get("value") is None:
        out.append("- Company headcount: not stated in the calls (a team or buying-group size "
                   "is not company size); Apollo is the authority.")
    else:
        out.append(f"- Company headcount stated in the calls: {hc['value']:,} "
                   f"({hc.get('source_citation')})")
    return out


def _pricing(pr) -> list:
    out = ["## Pricing", ""]
    if not pr:
        return out + ["Not priced: pricing.json missing."]
    if pr.get("status") != "priced":
        fields = ", ".join(pr.get("blocked_fields") or []) or "unknown"
        out.append(f"Not priced: blocked on {fields}.")
        out += [f"- {r}" for r in pr.get("reasons") or []]
        return out
    t = pr["totals"]
    out += [f"{pr['segment']} price book, {pr['term_months']} months, "
            f"{pr.get('currency') or 'USD'}{' (ramped)' if pr.get('ramped') else ''}.", "",
            "| List TCV | TCV | ACV | Discount amount | Blended discount |",
            "|---|---|---|---|---|",
            f"| {_usd(t['list_tcv'])} | {_usd(t['tcv'])} | {_usd(t['acv'])} | "
            f"{_usd(t['discount_amount'])} | {pct(t['blended_discount_pct'])} |", "",
            "| Year | Months | List | Net |", "|---|---|---|---|"]
    out += [f"| {y['year']} | {y['months']} | {_usd(y['list_total'])} | {_usd(y['net_total'])} |"
            for y in pr["years"]]
    out += ["", "| Year | Product | Qty | Unit list | Discount | List | Net |",
            "|---|---|---|---|---|---|---|"]
    for y in pr["years"]:
        for ln in y["lines"]:
            out.append(f"| {ln['year']} | {ln['product']} | {ln['quantity']} | "
                       f"{_usd(ln['unit_list_price'])} | {pct(ln['discount_pct'])} | "
                       f"{_usd(ln['list_total'])} | {_usd(ln['net_total'])} |")
    out += ["", "Assumptions: " + ("; ".join(pr.get("assumptions") or []) or "None")]
    return out


def _approval(pf) -> list:
    alt = pf.get("suggested_alternative") or {}
    src = pf.get("effective_discount_source")
    out = ["## Approval", "",
           f"- Effective discount: {pct(pf.get('effective_discount_pct'))}"
           + (f" ({src})" if src else ""),
           f"- Approval level required: {pf.get('approval_level_required') or 'n/a (discount unknown)'}",
           "- Thresholds breached: " + (", ".join(pf.get("thresholds_breached") or []) or "None")]
    if pf.get("segment_mismatch"):
        out.append(f"- On the rep's segment this would need: "
                   f"{pf.get('approval_level_on_rep_segment') or 'n/a'}")
    out.append(f"- Suggested alternative: {alt.get('summary') or 'None'}")
    if alt.get("approval_level_if_all_applied"):
        out.append(f"- Approval level if all suggestions applied: "
                   f"{alt['approval_level_if_all_applied']}")
    return out


def _comparables(pf, comps) -> list:
    out = ["## Comparables", ""]
    if pf.get("effective_discount_pct") is None:
        return out + ["Comparables: not run (no effective discount)."]
    if comps is None:
        return out + ["Comparables: not available (comparables.json missing)."]
    if comps.get("error"):
        return out + [f"Comparables: not available ({comps['error']})."]
    out += [f"{comps.get('segment')}, {comps.get('tier') or 'all tiers'}; proposed discount "
            f"{pct(comps.get('proposed_discount_pct'))}.", "", comps.get("finding") or "", "",
            "| Cohort | Deals | Won | Matured | Churned | Churn rate |",
            "|---|---|---|---|---|---|"]
    for key in ("near_proposed", "lower_discount"):
        c = comps.get(key) or {}
        out.append(f"| {_cell(c.get('discount_range'))} | {c.get('count')} | {c.get('won')} | "
                   f"{c.get('matured')} | {c.get('churned')} | {pct(c.get('churn_rate_pct'))} |")
    if comps.get("small_sample"):
        out += ["", "Small sample: treat the churn rates as indicative only (see counts)."]
    return out


def _question_text(q) -> str:
    text = q.get("text") or ""
    cands = q.get("candidates") or []
    if cands:
        text += " (candidates: " + "; ".join(
            f"{json.dumps(c.get('value')) if isinstance(c.get('value'), (list, dict)) else c.get('value')}"
            f" at {c.get('source_citation')}" for c in cands) + ")"
    return text


def _open_questions(ext, pf) -> list:
    qs = (ext or {}).get("open_questions") or pf.get("open_questions") or []
    covered = {q.get("field") for q in qs if q.get("blocking")}
    missing = [f for f in pf.get("blocked_fields") or [] if f not in covered]
    out = ["## Open questions"]
    if not qs and not missing:
        return out + ["None"]
    out += ["", "| Field | Blocking | Question | Source |", "|---|---|---|---|"]
    for q in qs:
        out.append(f"| {q.get('field')} | {_yes(q.get('blocking'))} | {_cell(_question_text(q))} "
                   f"| {_cell(q.get('source_citation') or '-')} |")
    for f in missing:
        out.append(f"| {f} | yes | Not stated or unresolved; no open question was raised | - |")
    return out


def _deal_files(deal_dir: Path) -> list:
    if not deal_dir or not deal_dir.is_dir():
        return []
    calls = sorted(deal_dir.glob("C*_*.md"), key=lambda p: int(re.match(r"C(\d+)", p.name)[1]))
    notes = [deal_dir / "rep_notes.md"] if (deal_dir / "rep_notes.md").exists() else []
    return calls + notes


def _process_mentions(deal_dir: Path) -> list:
    """First mention of each buying-process phrase, as a citation."""
    found = []
    files = _deal_files(deal_dir)
    for phrase in PROCESS_PHRASES:
        pat = re.compile(r"\b" + re.escape(phrase) + r"\b",
                         0 if phrase.isupper() else re.I)
        hit = None
        for f in files:
            call = None if f.name == "rep_notes.md" else f.name.split("_", 1)[0]
            for line in f.read_text(encoding="utf-8").splitlines():
                m = TURN_RE.match(line) if call else None
                if call and not m:
                    continue
                text = m.group(2) if m else line.strip(" -*")
                if not pat.search(text):
                    continue
                excerpt = text if len(text) <= EXCERPT_MAX else text[:EXCERPT_MAX - 1] + "…"
                excerpt = excerpt.replace('"', "'")
                hit = (f'{call} [{m.group(1)}] "{excerpt}"' if call
                       else f'rep_notes: "{excerpt}"')
                break
            if hit:
                break
        if hit:
            found.append((phrase, hit))
    return found


def _signals(ext, deal_dir) -> list:
    contacts = value(ext, "contacts") or []
    out = ["## Signals", "", "| Contact | Title | Buying role |", "|---|---|---|"]
    out += [f"| {_cell(c.get('name') or '-')} | {_cell(c.get('title'))} | {c.get('buying_role')} |"
            for c in contacts] or ["| - | none recorded | - |"]
    out.append("")
    roles = {c.get("buying_role") for c in contacts}
    if "Economic Buyer" not in roles:
        out.append("- No Economic Buyer among the contacts.")
    for c in contacts:
        if c.get("buying_role") == "Procurement":
            out.append(f"- Procurement is involved: {c.get('title')}"
                       + (f" ({c['name']})" if c.get("name") else "")
                       + ". A formal procurement step often indicates a larger organisation.")
    mentions = _process_mentions(deal_dir)
    if mentions:
        out += ["- Buying-process mentions in the deal files (keyword scan; context only, "
                "Apollo headcount stays the segment authority):"]
        out += [f"  - {phrase}: {cite}" for phrase, cite in mentions]
    else:
        out.append("- Buying-process mentions: none found"
                   + ("" if deal_dir and deal_dir.is_dir() else " (deal files not available)"))
    return out


def _salesforce(folder) -> list:
    opp = output_files.load(folder, "opportunity.json", required=False)
    res = output_files.load(folder, "sfdc_result.json", required=False)
    plan = output_files.load(folder, "sfdc_plan.json", required=False)
    out = ["## Salesforce", ""]
    if opp:
        out.append(f"- Opportunity: {opp.get('name') or 'n/a'} "
                   f"({opp.get('opportunity_id') or opp.get('error') or 'n/a'})")
    if res and res.get("quote_id"):
        out.append(f"- Salesforce Quote: {res.get('quote_name')} ({res['quote_id']}), "
                   f"{len(res.get('line_ids') or [])} lines")
        out.append(f"- PDF: {res.get('content_document_id') or 'not attached'}")
        out.append(f"- Task: {res['task_id']} owned by {res.get('task_owner_id')}"
                   if res.get("task_id") else "- Task: none")
    elif plan:
        out.append(f"- Dry run only: {len(plan.get('lines') or [])} planned quote lines on the "
                   f"{plan.get('price_book')} price book; nothing written.")
    else:
        out.append("- Not created yet.")
    return out


# --- document -----------------------------------------------------------------------------

def render(folder, deal_dir: Path = None) -> str:
    folder = Path(folder)
    pf = output_files.load(folder, "preflight.json")
    ext = output_files.load(folder, "extraction.json")
    apollo = output_files.load(folder, "apollo.json", required=False) or pf.get("apollo") or {}
    pr = output_files.load(folder, "pricing.json", required=False) or pf.get("pricing")
    comps = output_files.load(folder, "comparables.json", required=False)
    validation = output_files.load(folder, "validation.json", required=False)
    scenario = ext.get("scenario") or folder.name
    if deal_dir is None:
        deal_dir = DEALS / scenario
    name = value(ext, "company_name") or apollo.get("name") or scenario

    lines = [f"# Deal brief: {name} ({scenario})", "",
             "Internal: not for the customer. Every number is copied from the step JSON in "
             f"output/{scenario}/.", ""]
    lines += _status(pf)
    if validation is not None:
        errs = validation.get("errors") or []
        lines += ["", f"Extraction validation: {'valid' if validation.get('valid') else 'INVALID'}"
                  + (f" ({len(errs)} errors)" if errs else "")]
    for section in (_segment(pf, apollo, ext), _pricing(pr), _approval(pf),
                    _comparables(pf, comps), _open_questions(ext, pf),
                    _signals(ext, deal_dir), _salesforce(folder)):
        lines += [""] + section
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render output/<scenario>/deal_brief.md")
    parser.add_argument("folder", type=Path, help="output/<scenario> folder")
    parser.add_argument("--deal-dir", type=Path, default=None,
                        help="deal files for the buying-process scan (default data/deals/<scenario>)")
    args = parser.parse_args(argv)
    try:
        md = render(args.folder, args.deal_dir)
    except output_files.MissingOutput as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    out = args.folder / BRIEF_NAME
    out.write_text(md, encoding="utf-8")
    print(json.dumps({"deal_brief": str(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
