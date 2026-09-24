"""Render the customer-facing order form PDF for a priced, non-Blocked quote.

Reads output/<scenario>/ pricing.json, preflight.json, extraction.json (and
apollo.json for the company name fallback) and writes order_form.pdf there.

Customer-safe by construction: build_context() copies an allow-list of fields
(customer name, products, quantities, per-year lines, list/net prices, term,
start date, payment terms, totals) into the template; nothing internal
(approval level, thresholds, pre-flight status, segment, comparables, open
questions, notes, citations, confidence) is ever passed to it. Every number is
copied from pricing.json and only formatted here.

Refuses (exit 2, no PDF; a stale order_form.pdf is removed) when the pre-flight
status is Blocked on Open Questions, pricing is not priced, or pricing.json and
preflight.json disagree on the price book.

PDF engine: WeasyPrint when it loads (needs Pango), otherwise xhtml2pdf.

CLI:  python scripts/render_order_form.py output/<scenario>
      prints {"pdf": <path>, "engine": <weasyprint|xhtml2pdf>, "bytes": N}
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

import output_files
from output_files import money, pct, value

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
POLICY = ROOT / "reference" / "approval_policy.yaml"
PDF_NAME = "order_form.pdf"
BLOCKED = "Blocked on Open Questions"
CONTEXT_KEYS = {"customer_name", "quote_date", "currency", "term_months", "start_date",
                "payment_terms", "products", "years", "totals"}
NET_RE = re.compile(r"^\s*net\s*-?\s*(\d+)\s*(days?)?\s*$", re.I)


class OrderFormRefused(RuntimeError):
    """The quote may not go to the customer (Blocked, not priced, inconsistent)."""


def _payment_terms(terms) -> str:
    if terms is None:
        import yaml
        standard = yaml.safe_load(POLICY.read_text())["payment_terms"]["standard"]
        return f"{_payment_terms(standard)} (standard)"
    m = NET_RE.match(str(terms))
    return f"Net {m.group(1)}" if m else str(terms)


def build_context(folder) -> dict:
    """The only data the template sees. Raises OrderFormRefused / MissingOutput."""
    folder = Path(folder)
    pf = output_files.load(folder, "preflight.json")
    status = pf.get("preflight_status")
    if status == BLOCKED:
        fields = ", ".join(pf.get("blocked_fields") or []) or "open questions"
        raise OrderFormRefused(f"pre-flight status is {BLOCKED} ({fields}): order form not "
                               "rendered; resolve the open questions first")
    if status not in ("Ready", "Needs Approval"):
        raise OrderFormRefused(f"unknown pre-flight status {status!r}: order form not rendered")
    pr = output_files.load(folder, "pricing.json")
    if pr.get("status") != "priced":
        raise OrderFormRefused("pricing.json is not priced "
                               f"({', '.join(pr.get('blocked_fields') or [])}): "
                               "order form not rendered")
    if pr.get("segment") != pf.get("band_segment"):
        raise OrderFormRefused(f"pricing.json price book {pr.get('segment')!r} differs from the "
                               f"pre-flight's {pf.get('band_segment')!r}: order form not "
                               "rendered; re-run pricing")
    ext = output_files.load(folder, "extraction.json")
    apollo = output_files.load(folder, "apollo.json", required=False) or {}
    name = value(ext, "company_name") or apollo.get("name")
    if not name:
        raise OrderFormRefused("no customer name in extraction.json or apollo.json")

    years = []
    for y in pr["years"]:
        lines = []
        for ln in y["lines"]:
            note = "one-time" if ln.get("billing") == "one_time" else (
                f"{ln['months']} months" if ln.get("months") and ln["months"] < 12 else None)
            lines.append({"product": ln["product"], "quantity": ln["quantity"],
                          "unit_list_price": money(ln["unit_list_price"]),
                          "discount_pct": pct(ln["discount_pct"]),
                          "list_total": money(ln["list_total"]),
                          "net_total": money(ln["net_total"]), "note": note})
        years.append({"year": y["year"], "months": y["months"], "lines": lines,
                      "list_total": money(y["list_total"]), "net_total": money(y["net_total"])})
    first = pr["years"][0]["lines"]
    t = pr["totals"]
    return {
        "customer_name": name,
        "quote_date": date.today().isoformat(),
        "currency": pr.get("currency") or "USD",
        "term_months": pr["term_months"],
        "start_date": value(ext, "start_date") or "To be agreed",
        "payment_terms": _payment_terms(value(ext, "payment_terms")),
        "products": [{"name": ln["product"], "quantity": ln["quantity"]} for ln in first],
        "years": years,
        "totals": {"list_tcv": money(t["list_tcv"]), "discount_amount": money(t["discount_amount"]),
                   "tcv": money(t["tcv"]), "acv": money(t["acv"])},
    }


def render_html(context: dict) -> str:
    if set(context) != CONTEXT_KEYS:
        raise ValueError(f"context keys {sorted(context)} != allow-list {sorted(CONTEXT_KEYS)}")
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined,
                      autoescape=select_autoescape(["html"]))
    return env.get_template("order_form.html").render(**context)


def _weasyprint():
    # WeasyPrint prints a long install hint when Pango is missing; keep stdout JSON-only.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import weasyprint  # noqa: WPS433
    return weasyprint


def html_to_pdf(html: str):
    """(pdf bytes, engine name)."""
    try:
        return _weasyprint().HTML(string=html, base_url=str(TEMPLATES)).write_pdf(), "weasyprint"
    except Exception:  # noqa: BLE001 - OSError when the Pango libraries are missing
        pass
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    result = pisa.CreatePDF(html, dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"xhtml2pdf failed with {result.err} error(s)")
    return buf.getvalue(), "xhtml2pdf"


def render(folder) -> dict:
    folder = Path(folder)
    html = render_html(build_context(folder))
    pdf, engine = html_to_pdf(html)
    if not pdf.startswith(b"%PDF-"):
        raise RuntimeError(f"{engine} did not produce a PDF")
    out = folder / PDF_NAME
    tmp = out.with_suffix(".pdf.tmp")
    tmp.write_bytes(pdf)
    tmp.replace(out)
    return {"pdf": str(out), "engine": engine, "bytes": len(pdf)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Render output/<scenario>/order_form.pdf (refuses when Blocked)")
    parser.add_argument("folder", type=Path, help="output/<scenario> folder")
    args = parser.parse_args(argv)
    try:
        result = render(args.folder)
    except OrderFormRefused as e:
        stale = args.folder / PDF_NAME
        if stale.exists():
            stale.unlink()  # never leave an order form for a quote that may not go out
            print(f"removed stale {stale}", file=sys.stderr)
        print(f"REFUSED  {e}", file=sys.stderr)
        return 2
    except output_files.MissingOutput as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
