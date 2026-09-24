"""scripts/render_order_form.py: customer-facing order form (HTML -> PDF).

Totals are hand-calculated literals (see tests/test_pricing.py):
  clean-midmarket, Mid-Market book, 120 seats, 24 months, 12%:
    list TCV 223,000; TCV 196,240; ACV 87,120; discount amount 26,760
  mis-segmented, Enterprise book, Pro + 60 seats, 12 months, 18%:
    list 32,400 + 60*480 = 61,200; net 50,184; discount 11,016
"""

import io
import json
import re

import pytest
from pypdf import PdfReader

import render_order_form as rof
from output_fixtures import write_outputs

# Internal-only vocabulary that must never reach the customer document.
DENY_CI = [r"approv", r"threshold", r"pre-?flight", r"mismatch", r"comparable", r"churn",
           r"open question", r"deal desk", r"segment", r"citation", r"confidence",
           r"internal", r"rep_notes", r"price book", r"blocked", r"needs approval",
           r"unverified", r"blended", r"assumption", r"suggested", r"apollo", r"employees",
           r"candidate", r"economic buyer", r"source"]
DENY_CS = [r"\bCFO\b", r"\bVP\b", r"\bManager\b", r"\bRep\b", r"Mid-Market", r"\bSMB\b",
           r"\bC[0-9]+ \[", r"\bready\b"]


def internal_terms(text: str) -> list:
    hits = [p for p in DENY_CI if re.search(p, text, re.I)]
    return hits + [p for p in DENY_CS if re.search(p, text)]


def html_for(tmp_path, name, **kw):
    folder = write_outputs(tmp_path, name, **kw)
    return folder, rof.render_html(rof.build_context(folder))


def test_clean_midmarket_totals_and_terms(tmp_path):
    _, html = html_for(tmp_path, "clean-midmarket")
    for s in ["Retool", "223,000.00", "196,240.00", "87,120.00", "26,760.00",
              "2026-11-01", "Net 30", "24 months", "Platform Pro", "Additional Seats",
              "Implementation Services", "Year 1", "Year 2", "USD"]:
        assert s in html, s
    # per-year seat line: 120 seats at 540.00 list
    assert "540.00" in html and "64,800.00" in html


def test_numbers_are_copied_from_pricing_json_not_recomputed(tmp_path):
    folder = write_outputs(tmp_path, "clean-midmarket")
    pr = json.loads((folder / "pricing.json").read_text())
    pr["totals"]["tcv"] = 123.45  # a renderer that recomputes would not show this
    pr["years"][0]["net_total"] = 678.9
    (folder / "pricing.json").write_text(json.dumps(pr))
    html = rof.render_html(rof.build_context(folder))
    assert "123.45" in html and "678.90" in html
    assert "196,240.00" not in html


@pytest.mark.parametrize("name", ["clean-midmarket", "mis-segmented"])
def test_no_internal_terms(tmp_path, name):
    _, html = html_for(tmp_path, name)
    assert internal_terms(html) == []


def test_mis_segmented_shows_enterprise_book_prices_but_not_the_segment(tmp_path):
    _, html = html_for(tmp_path, "mis-segmented")
    assert "61,200.00" in html and "50,184.00" in html and "11,016.00" in html
    assert "Enterprise" not in html  # the price-book name is internal
    assert "2027-01-05" in html and "12 months" in html


def test_context_has_only_customer_safe_keys(tmp_path):
    folder = write_outputs(tmp_path, "clean-midmarket")
    ctx = rof.build_context(folder)
    assert set(ctx) == rof.CONTEXT_KEYS
    flat = json.dumps(ctx)
    assert internal_terms(flat) == []


@pytest.mark.parametrize("name", ["conflicting-seats", "aggressive-discount"])
def test_blocked_refuses_and_writes_no_pdf(tmp_path, name, capsys):
    folder = write_outputs(tmp_path, name)
    stale = folder / "order_form.pdf"
    stale.write_bytes(b"%PDF-1.4 stale")
    assert rof.main([str(folder)]) != 0
    err = capsys.readouterr().err
    assert "Blocked on Open Questions" in err and "not rendered" in err
    assert not stale.exists()
    with pytest.raises(rof.OrderFormRefused):
        rof.build_context(folder)


def test_refuses_when_pricing_and_preflight_disagree_on_price_book(tmp_path):
    folder = write_outputs(tmp_path, "clean-midmarket")
    pr = json.loads((folder / "pricing.json").read_text())
    pr["segment"] = "Enterprise"
    (folder / "pricing.json").write_text(json.dumps(pr))
    with pytest.raises(rof.OrderFormRefused):
        rof.build_context(folder)


def test_missing_files_refused(tmp_path, capsys):
    (tmp_path / "x").mkdir()
    assert rof.main([str(tmp_path / "x")]) != 0
    assert "preflight.json" in capsys.readouterr().err


def test_renders_real_pdf_with_totals(tmp_path, capsys):
    folder = write_outputs(tmp_path, "clean-midmarket")
    assert rof.main([str(folder)]) == 0
    data = (folder / "order_form.pdf").read_bytes()
    assert data.startswith(b"%PDF-")
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    for s in ["Retool", "196,240.00", "223,000.00", "87,120.00", "Net 30"]:
        assert s in text, s
    assert internal_terms(text) == []
    out = json.loads(capsys.readouterr().out)
    assert out["pdf"].endswith("order_form.pdf") and out["engine"] in ("weasyprint",
                                                                        "xhtml2pdf")
