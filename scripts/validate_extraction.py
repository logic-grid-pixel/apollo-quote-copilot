"""Validate an extraction against schemas/deal_extraction.json, and its citations
against the deal's source files.

Checks, in order:
  1. JSON Schema (draft 2020-12, with date format checking)
  2. an open question with conflict candidates -> that field's value is null
     (the model must not pick between conflicting statements)
  3. with --deal-dir: every citation points at a real file / turn and every
     excerpt fragment (split on '…' or '...') appears in that turn / line

Prints {"valid": bool, "errors": [{"path", "message"}], "file"}; exit 0 if valid, else 1.

CLI:  python scripts/validate_extraction.py output/<scenario>/extraction.json
          [--deal-dir data/deals/<scenario>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import jsonschema

SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "deal_extraction.json"
CITE_RE = re.compile(r'(?:(C[1-9][0-9]*) \[([0-9]{2}:[0-9]{2}:[0-9]{2}|header)\]|(rep_notes):) '
                     r'"([^"]+)"')
TURN_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]", re.M)
ELLIPSIS_RE = re.compile(r"…|\.\.\.")


def load_schema(path: Path = SCHEMA) -> dict:
    return json.loads(Path(path).read_text())


def _path(parts) -> str:
    return ".".join(str(p) for p in parts) or "(root)"


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"') \
         .replace("”", '"').replace('"', "'")
    return re.sub(r"\s+", " ", s).strip().lower()


# --- citation checking ------------------------------------------------------------------

class _Sources:
    def __init__(self, deal_dir: Path):
        self.dir = Path(deal_dir)
        self._cache = {}

    def _file(self, source: str):
        if source == "rep_notes":
            matches = [self.dir / "rep_notes.md"]
            matches = [m for m in matches if m.exists()]
        else:
            matches = sorted(self.dir.glob(f"{source}_*.md"))
        return matches[0] if len(matches) == 1 else None

    def target(self, source: str, locator):
        """Text a citation's excerpt must come from, or (None, reason)."""
        f = self._file(source)
        if f is None:
            return None, f"no source file for {source} in {self.dir}"
        text = self._cache.setdefault(f, f.read_text(encoding="utf-8"))
        if source == "rep_notes":
            return text, None
        first_turn = TURN_RE.search(text)
        if locator == "header":
            return (text[:first_turn.start()] if first_turn else text), None
        for line in text.splitlines():
            if line.startswith(f"[{locator}]"):
                return line, None
        return None, f"{source} has no turn at [{locator}] ({f.name})"


def check_citation(citation: str, sources: _Sources) -> list:
    problems = []
    for m in CITE_RE.finditer(citation):
        call, locator, notes, excerpt = m.groups()
        source = call or notes
        target, why = sources.target(source, locator)
        if target is None:
            problems.append(why)
            continue
        hay = _norm(target)
        for frag in ELLIPSIS_RE.split(excerpt):
            frag = _norm(frag).strip(" ,.;:-—")
            if frag and frag not in hay:
                where = f"{source} [{locator}]" if locator else source
                problems.append(f"excerpt {frag!r} not found in {where}")
    return problems


def _citations(doc: dict):
    """(path, citation) for every citation in the document."""
    for field, f in doc.items():
        if isinstance(f, dict) and isinstance(f.get("source_citation"), str):
            yield f"{field}.source_citation", f["source_citation"]
    for i, q in enumerate(doc.get("open_questions") or []):
        if not isinstance(q, dict):
            continue
        if isinstance(q.get("source_citation"), str):
            yield f"open_questions.{i}.source_citation", q["source_citation"]
        for j, c in enumerate(q.get("candidates") or []):
            if isinstance(c, dict) and isinstance(c.get("source_citation"), str):
                yield f"open_questions.{i}.candidates.{j}.source_citation", c["source_citation"]


# --- validation ------------------------------------------------------------------------------

def validate(doc, deal_dir=None, schema: dict = None) -> list:
    schema = schema or load_schema()
    validator = jsonschema.Draft202012Validator(schema,
                                                format_checker=jsonschema.FormatChecker())
    errors = [{"path": _path(e.absolute_path), "message": e.message}
              for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))]
    if not isinstance(doc, dict):
        return errors

    for q in doc.get("open_questions") or []:
        if not isinstance(q, dict) or not q.get("candidates"):
            continue
        field = q.get("field")
        f = doc.get(field)
        if isinstance(f, dict) and f.get("value") is not None:
            errors.append({"path": f"{field}.value",
                           "message": "has conflict candidates in open_questions, so the value "
                                      "must be null (do not pick between conflicting statements)"})

    if deal_dir is not None:
        sources = _Sources(deal_dir)
        for path, citation in _citations(doc):
            for problem in check_citation(citation, sources):
                errors.append({"path": path, "message": problem})
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an extraction JSON against schemas/deal_extraction.json")
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--deal-dir", type=Path, default=None,
                        help="deal folder (data/deals/<scenario>) to check citations against")
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.extraction.read_text())
    except (OSError, ValueError) as e:
        errors = [{"path": "(file)", "message": f"cannot read JSON: {e}"}]
    else:
        errors = validate(doc, args.deal_dir)
    print(json.dumps({"valid": not errors, "errors": errors, "file": str(args.extraction)},
                     indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
