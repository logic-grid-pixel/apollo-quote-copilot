"""scripts/render_deal_brief.py: the internal deal brief (markdown).

Numbers asserted here are hand-calculated literals (see tests/test_pricing.py and
tests/test_preflight.py), not copied from code output.
"""

import json

import pytest

import render_deal_brief as rdb
from extraction_fixtures import spec_document
from output_fixtures import COMPARABLES, write_outputs


def brief(tmp_path, name, **kw):
    folder = write_outputs(tmp_path, name, **kw)
    return folder, rdb.render(folder)


def test_clean_midmarket_ready_with_pricing(tmp_path):
    _, md = brief(tmp_path, "clean-midmarket")
    assert md.startswith("# Deal brief: Retool (clean-midmarket)")
    assert "**Status: Ready**" in md
    for s in ["$223,000.00", "$196,240.00", "$87,120.00", "$26,760.00", "12.00%"]:
        assert s in md, s
    assert "Approval level required: Rep" in md
    assert "Thresholds breached: None" in md
    assert "Mismatch: no" in md
    assert "Comparables: not available (comparables.json missing)" in md
    assert "## Open questions\nNone" in md


def test_mis_segmented_explains_mismatch_and_signals(tmp_path):
    _, md = brief(tmp_path, "mis-segmented")
    assert "**Status: Needs Approval**" in md
    assert "Mismatch: yes" in md
    # rep said SMB, Apollo says Enterprise with its employee count
    assert "rep tagged the account SMB" in md
    assert "Apollo reports 5,200 employees" in md and "Enterprise" in md
    assert "On the rep's SMB segment this would need Manager approval" in md
    assert "Company headcount: not stated in the calls" in md
    # enterprise buying-process signals, cited
    assert "Procurement Analyst" in md and "Procurement" in md
    assert "master agreement" in md.lower()
    assert 'C2 [00:29:39]' in md
    assert "$61,200.00" in md and "$50,184.00" in md


def test_conflicting_seats_blocked_open_question_with_candidates(tmp_path):
    _, md = brief(tmp_path, "conflicting-seats")
    assert "**Status: Blocked on Open Questions**" in md
    assert "Not priced: blocked on seat_count" in md
    assert "$" not in md.split("## Pricing", 1)[1].split("## ", 1)[0]
    assert "| seat_count | yes |" in md
    assert "50 at C1 [00:10:27]" in md and "80 at C3 [00:09:11]" in md
    assert "Approval level required: Manager" in md  # 15% requested, Mid-Market band


def test_aggressive_discount_breaches_alternative_and_comparables_counts(tmp_path):
    _, md = brief(tmp_path, "aggressive-discount", comparables=COMPARABLES)
    assert "**Status: Blocked on Open Questions**" in md
    assert "Approval level required: CFO" in md
    assert "Thresholds breached: discount_band, payment_terms" in md
    assert "Hold the discount at the Enterprise ceiling of 35%" in md
    # priced even though Blocked (start_date does not change numbers): ramp 200/400/600
    assert "$925,200.00" in md and "$555,120.00" in md and "$185,040.00" in md
    # comparables are counts, never a bare trend word
    assert "| >= 35.00% | 4 | 3 | 2 | 1 | 50.00% |" in md
    assert "| < 35.00% | 11 | 8 | 7 | 1 | 14.29% |" in md
    assert "Small sample" in md
    assert "| start_date | yes |" in md
    assert "As soon as we're through security review." in md
    assert "No Economic Buyer among the contacts" in md


def test_comparables_not_run_reason_when_discount_known_but_file_missing(tmp_path):
    _, md = brief(tmp_path, "aggressive-discount")
    assert "Comparables: not available (comparables.json missing)" in md


def test_comparables_error_is_reported_not_hidden(tmp_path):
    _, md = brief(tmp_path, "aggressive-discount", comparables={"error": "login failed"})
    assert "Comparables: not available (login failed)" in md


def test_numbers_copied_from_json(tmp_path):
    folder = write_outputs(tmp_path, "clean-midmarket")
    pr = json.loads((folder / "pricing.json").read_text())
    pr["totals"]["tcv"] = 111.11
    (folder / "pricing.json").write_text(json.dumps(pr))
    md = rdb.render(folder)
    assert "$111.11" in md and "$196,240.00" not in md


def test_sfdc_result_listed_when_present(tmp_path):
    folder = write_outputs(tmp_path, "clean-midmarket")
    (folder / "sfdc_result.json").write_text(json.dumps({
        "quote_id": "0Q0000000000001", "quote_name": "Retool quote", "line_ids": ["a", "b"],
        "content_document_id": "069x", "task_id": None, "task_owner_id": None}))
    md = rdb.render(folder)
    assert "Salesforce Quote: Retool quote (0Q0000000000001), 2 lines" in md


def test_cli_writes_deal_brief(tmp_path, capsys):
    folder = write_outputs(tmp_path, "clean-midmarket")
    assert rdb.main([str(folder)]) == 0
    assert (folder / "deal_brief.md").read_text().startswith("# Deal brief")
    assert json.loads(capsys.readouterr().out)["deal_brief"].endswith("deal_brief.md")


def test_cli_missing_preflight_errors(tmp_path, capsys):
    (tmp_path / "x").mkdir()
    assert rdb.main([str(tmp_path / "x")]) == 1
