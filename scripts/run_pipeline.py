"""Run SKILL.md steps 2-5 on output/<scenario>/extraction.json.

  validate -> apollo -> pricing -> preflight -> comparables -> find_opportunity
  -> sfdc plan -> order form (only when not Blocked) -> [live: create quote]
  -> deal brief

Every step writes the same JSON the individual CLIs write, into
output/<scenario>/ (see SKILL.md, Output layout). The numbers all come from the
scripts; this runner only passes files between them.

Modes
  default    dry run: reads Apollo (cache) and Salesforce (Opportunity lookup,
             comparables), writes sfdc_plan.json; never writes to Salesforce.
  --offline  dry run without any Salesforce call (no opportunity.json;
             comparables.json records that it was not run).
  --live     also creates the Draft Quote (lines, order-form PDF when not
             Blocked, Task) and writes sfdc_result.json.

Duplicate guard (--live): a Quote on the scenario's demo Opportunity whose
Description starts with "Quote Copilot draft" was created by this tool. If one
exists the run REFUSES (exit 2) before writing anything, listing the Ids.
--replace deletes those quotes first (with their Tasks and attached PDF
documents; Salesforce keeps them in the recycle bin), then creates the new one.
Quotes made by people are never touched.

Exit codes: 0 ok, 1 invalid/missing input or step error, 2 duplicate refused.

CLI:  python scripts/run_pipeline.py <scenario> [--live [--replace]] [--offline]
          [--output-root output] [--deal-dir data/deals/<scenario>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import apollo_client
import comparables
import find_opportunity
import preflight
import pricing
import render_deal_brief
import render_order_form
import sfdc_client
import validate_extraction
from sf_session import connect

ROOT = Path(__file__).resolve().parent.parent
TOOL_DESCRIPTION_PREFIX = "Quote Copilot draft"
SCENARIO_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TIERS = comparables.TIERS


class PipelineError(RuntimeError):
    pass


class DuplicateQuote(RuntimeError):
    pass


def _write(folder: Path, name: str, data) -> Path:
    path = folder / name
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def _remove(path: Path):
    if path.exists():
        path.unlink()


# --- Salesforce duplicate guard -------------------------------------------------------------

def tool_quotes(sf, opportunity_id: str) -> list:
    """Quotes on the Opportunity that this tool created (Description prefix)."""
    if not sfdc_client.OPP_ID_RE.match(opportunity_id or ""):
        raise PipelineError(f"not an Opportunity Id: {opportunity_id!r}")
    rows = sf.query("SELECT Id, Name, Description, Preflight_Status__c FROM Quote "
                    f"WHERE OpportunityId = '{opportunity_id}'")["records"]
    return [r for r in rows
            if (r.get("Description") or "").startswith(TOOL_DESCRIPTION_PREFIX)]


def delete_tool_quote(sf, quote: dict, opportunity_id: str) -> list:
    """Delete one tool quote with its Tasks and attached documents; returns errors."""
    qid = quote["Id"]
    tasks = sf.query(f"SELECT Id, WhatId, Subject FROM Task WHERE WhatId IN "
                     f"('{qid}', '{opportunity_id}')")["records"]
    task_ids = [t["Id"] for t in tasks
                if t.get("WhatId") == qid
                or (quote.get("Name") and (t.get("Subject") or "").endswith(quote["Name"]))]
    docs = sf.query("SELECT ContentDocumentId FROM ContentDocumentLink "
                    f"WHERE LinkedEntityId = '{qid}'")["records"]
    errors = []
    targets = [("Task", t) for t in task_ids] + \
              [("ContentDocument", d["ContentDocumentId"]) for d in docs] + [("Quote", qid)]
    for sobject, rid in targets:
        try:
            getattr(sf, sobject).delete(rid)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sobject} {rid}: {e}")
    return errors


# --- the steps --------------------------------------------------------------------------------

def _platform_tier(extraction: dict):
    for p in pricing.field_value(extraction, "products") or []:
        if p.get("name") in TIERS:
            return p["name"]
    return None


def run(scenario: str, output_root: Path, deal_dir: Path = None, live: bool = False,
        replace: bool = False, offline: bool = False, log=print) -> dict:
    if not SCENARIO_RE.match(scenario):
        raise PipelineError(f"bad scenario name {scenario!r}")
    folder = Path(output_root) / scenario
    deal_dir = Path(deal_dir) if deal_dir else ROOT / "data" / "deals" / scenario
    ext_path = folder / "extraction.json"
    if not ext_path.exists():
        raise PipelineError(f"{ext_path} not found: write the extraction first (SKILL.md step 1)")
    extraction = json.loads(ext_path.read_text(encoding="utf-8"))
    files = []

    # Step 1 check: validate (schema, conflicts, citations against the deal files)
    errors = validate_extraction.validate(extraction, deal_dir if deal_dir.is_dir() else None)
    files.append(_write(folder, "validation.json",
                        {"valid": not errors, "errors": errors, "file": str(ext_path)}))
    if errors:
        raise PipelineError(f"extraction failed validation ({len(errors)} errors, see "
                            f"{folder / 'validation.json'}); fix it before pricing")

    # Step 2: Apollo (cache; never refreshed here)
    domain = pricing.field_value(extraction, "account_domain")
    if domain:
        try:
            apollo = apollo_client.organization_summary(domain)
        except (apollo_client.ApolloError, ValueError) as e:
            apollo = {"domain": domain, "error": str(e), "verified_segment": None}
    else:
        apollo = {"domain": None, "error": "no account_domain in the extraction",
                  "verified_segment": None}
    files.append(_write(folder, "apollo.json", apollo))

    # Step 3: price on the band segment (verified, else the rep's)
    rep = pricing.field_value(extraction, "rep_stated_segment")
    band = apollo.get("verified_segment") or (rep if rep in pricing.SEGMENTS else None)
    if band:
        priced = pricing.price_extraction(extraction, band)
    else:
        priced = {"status": "blocked", "segment": None, "blocked_fields": ["segment"],
                  "reasons": ["segment: neither Apollo nor the rep gives a segment"]}
    files.append(_write(folder, "pricing.json", priced))

    # Step 4: pre-flight (same as preflight.run, reusing the Apollo lookup above)
    pf = preflight.preflight_extraction(extraction, apollo.get("verified_segment"))
    pf["apollo"] = apollo
    files.append(_write(folder, "preflight.json", pf))
    status = pf["preflight_status"]

    sf = None if offline else connect()
    comps_path = folder / "comparables.json"
    if pf.get("effective_discount_pct") is None:
        _remove(comps_path)
    elif offline:
        files.append(_write(folder, "comparables.json", {"error": "not run (--offline)"}))
    else:
        try:
            comps = comparables.comparables(sf, pf["band_segment"], pf["effective_discount_pct"],
                                            _platform_tier(extraction))
        except Exception as e:  # noqa: BLE001 - reported in the brief, not fatal
            comps = {"error": f"comparables failed: {e}"}
        files.append(_write(folder, "comparables.json", comps))

    # Step 5: Opportunity, plan, order form, [create], brief
    opp_id = None
    if not offline:
        try:
            opp = find_opportunity.find(sf, scenario)
        except (LookupError, ValueError) as e:
            opp = {"scenario": scenario, "error": str(e)}
        files.append(_write(folder, "opportunity.json", opp))
        opp_id = opp.get("opportunity_id")
        if live and not opp_id:
            raise PipelineError(f"no Opportunity for {scenario}: {opp.get('error')}")

    pdf_path = folder / render_order_form.PDF_NAME
    order_form = None
    if status == preflight.BLOCKED:
        _remove(pdf_path)
    else:
        order_form = render_order_form.render(folder)
        files.append(pdf_path)
    pdf_bytes = pdf_path.read_bytes() if order_form else None

    pr = pf.get("pricing")
    if opp_id:
        sfdc_client.validate_inputs(opp_id, pf, pr, pdf_bytes)
    plan = sfdc_client.plan_quote(pf, pr, extraction, opp_id, pdf_bytes=pdf_bytes)
    files.append(_write(folder, "sfdc_plan.json",
                        {**plan, "preflight": {k: v for k, v in pf.items() if k != "pricing"}}))

    result = None
    if live:
        existing = tool_quotes(sf, opp_id)
        if existing and not replace:
            ids = ", ".join(q["Id"] for q in existing)
            raise DuplicateQuote(f"Opportunity {opp_id} already has Quote Copilot quote(s) {ids}; "
                                 "re-run with --replace to delete and recreate, or delete them "
                                 "yourself")
        replaced = []
        for q in existing:
            errs = delete_tool_quote(sf, q, opp_id)
            if errs:
                raise PipelineError("could not delete previous quote: " + "; ".join(errs))
            replaced.append(q["Id"])
            log(f"deleted previous Quote Copilot quote {q['Id']} ({q.get('Name')})")
        result = sfdc_client.create_quote(sf, opp_id, pf, pr, extraction, pdf_bytes)
        result["replaced_quote_ids"] = replaced
        files.append(_write(folder, "sfdc_result.json", result))

    brief = folder / render_deal_brief.BRIEF_NAME
    brief.write_text(render_deal_brief.render(folder, deal_dir), encoding="utf-8")
    files.append(brief)

    return {"scenario": scenario, "mode": "live" if live else "dry-run",
            "offline": offline, "preflight_status": status,
            "pricing_status": priced.get("status"),
            "order_form": str(pdf_path) if order_form else None,
            "opportunity_id": opp_id,
            "quote_id": (result or {}).get("quote_id"),
            "files": [str(f) for f in files]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run SKILL.md steps 2-5 on output/<scenario>/extraction.json "
                    "(dry run unless --live)")
    parser.add_argument("scenario", help="deal folder name, e.g. clean-midmarket")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true",
                      help="create the Draft Quote, lines, PDF and Task in Salesforce")
    mode.add_argument("--offline", action="store_true",
                      help="no Salesforce calls at all (no Opportunity lookup, no comparables)")
    parser.add_argument("--replace", action="store_true",
                        help="with --live: delete this tool's earlier quote(s) on the "
                             "Opportunity first (default: refuse)")
    parser.add_argument("--output-root", type=Path, default=ROOT / "output")
    parser.add_argument("--deal-dir", type=Path, default=None,
                        help="default data/deals/<scenario>")
    args = parser.parse_args(argv)
    if args.replace and not args.live:
        parser.error("--replace only applies with --live")
    log = lambda msg: print(msg, file=sys.stderr)  # noqa: E731 - stdout is JSON only
    try:
        summary = run(args.scenario, args.output_root, args.deal_dir, live=args.live,
                      replace=args.replace, offline=args.offline, log=log)
    except DuplicateQuote as e:
        print(f"REFUSED  {e}", file=sys.stderr)
        return 2
    except (PipelineError, sfdc_client.QuoteInputError, render_order_form.OrderFormRefused,
            FileNotFoundError, ValueError) as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
