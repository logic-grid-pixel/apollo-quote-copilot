"""SKILL.md must describe the scripts that actually exist, with flags they accept."""

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
PHASE5_MARK = "(added in Phase 5)"
PHASE5_SCRIPTS = {"scripts/render_order_form.py", "scripts/render_deal_brief.py"}
SCRIPT_RE = re.compile(r"scripts/[A-Za-z0-9_]+\.py")
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")


def text():
    return SKILL.read_text(encoding="utf-8")


def frontmatter():
    m = re.match(r"^---\n(.*?)\n---\n", text(), re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    return yaml.safe_load(m.group(1))


def body():
    return re.sub(r"^---\n.*?\n---\n", "", text(), count=1, flags=re.S)


@lru_cache(maxsize=None)
def help_text(script: str) -> str:
    out = subprocess.run([sys.executable, str(ROOT / script), "--help"], cwd=ROOT,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"{script} --help failed: {out.stderr[-500:]}"
    return out.stdout


def mentioned_scripts():
    return sorted(set(SCRIPT_RE.findall(body())))


def test_frontmatter_has_name_and_description():
    fm = frontmatter()
    assert fm["name"] == "quote-copilot"
    desc = fm["description"]
    assert isinstance(desc, str) and 100 <= len(desc) <= 1024
    assert "transcript" in desc.lower() and "quote" in desc.lower()
    assert re.search(r"\bnot\b", desc, re.I), "description should say when NOT to trigger"


def test_every_mentioned_script_exists_or_is_marked_phase5():
    for script in mentioned_scripts():
        if (ROOT / script).exists():
            continue
        assert script in PHASE5_SCRIPTS, f"{script} is mentioned but does not exist"
        for line in body().splitlines():
            if script in line:
                assert PHASE5_MARK in line, f"{script} not marked {PHASE5_MARK}: {line!r}"


def test_phase5_scripts_are_referenced():
    b = body()
    for script in PHASE5_SCRIPTS:
        assert script in b
        if not (ROOT / script).exists():
            assert PHASE5_MARK in b


def _command_lines():
    """Lines of SKILL.md that invoke a script (in code blocks or inline code)."""
    for line in body().splitlines():
        for script in set(SCRIPT_RE.findall(line)):
            yield script, line


def test_flags_shown_exist_in_script_help():
    checked = 0
    for script, line in _command_lines():
        if not (ROOT / script).exists():
            continue
        # only flags that follow this script's name on the line belong to it
        tail = line.split(script, 1)[1]
        nxt = SCRIPT_RE.search(tail)
        if nxt:
            tail = tail[:nxt.start()]
        for flag in FLAG_RE.findall(tail):
            assert flag in help_text(script), f"{script} has no {flag} (line: {line.strip()})"
            checked += 1
    assert checked >= 6, "expected SKILL.md to show the scripts' flags"


@pytest.mark.parametrize("step,scripts", [
    ("Extract", ["scripts/validate_extraction.py"]),
    ("Verify account", ["scripts/apollo_client.py"]),
    ("Price", ["scripts/pricing.py"]),
    ("Pre-flight", ["scripts/preflight.py", "scripts/comparables.py"]),
    ("Outputs", ["scripts/sfdc_client.py", "scripts/render_order_form.py",
                 "scripts/render_deal_brief.py"]),
])
def test_five_steps_present_with_their_commands(step, scripts):
    b = body()
    headings = re.findall(r"^###\s+Step\s+(\d)\s*[-—:.]\s*(.+)$", b, re.M)
    numbers = [n for n, _ in headings]
    assert numbers == ["1", "2", "3", "4", "5"], headings
    idx = [i for i, (_, title) in enumerate(headings) if title.startswith(step)]
    assert idx, f"no step titled {step!r}: {headings}"
    n = idx[0] + 1
    section = re.split(r"^###\s+Step\s+\d", b, flags=re.M)[n]
    for script in scripts:
        assert script in section, f"step {n} ({step}) does not run {script}"


def test_hard_rules_and_output_template_present():
    b = body().lower()
    assert "never computes" in b or "never compute" in b
    assert "blocked on open questions" in b
    assert "schemas/deal_extraction.json" in b
    assert "output/<scenario>/extraction.json" in b
    assert "tell your system" in b  # the injection example
    assert "## final reply" in b
