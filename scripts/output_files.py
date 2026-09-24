"""Read the step JSON files in output/<scenario>/ (see SKILL.md, Output layout)."""

from __future__ import annotations

import json
from pathlib import Path


class MissingOutput(FileNotFoundError):
    pass


def load(folder, name: str, required: bool = True):
    """Parsed JSON of folder/name, or None when optional and absent."""
    path = Path(folder) / name
    if not path.exists():
        if required:
            raise MissingOutput(f"{path} not found (run the earlier SKILL.md steps first)")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def value(extraction: dict, field: str):
    f = (extraction or {}).get(field)
    return f.get("value") if isinstance(f, dict) else f


def money(x) -> str:
    """Format a number already computed by pricing.py; no arithmetic."""
    return "n/a" if x is None else f"{x:,.2f}"


def pct(x) -> str:
    return "n/a" if x is None else f"{x:.2f}%"
