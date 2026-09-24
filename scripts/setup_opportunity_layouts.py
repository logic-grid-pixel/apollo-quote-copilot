"""Make every Opportunity page layout section two-column.

One-column sections (on these layouts, Description Information) become
TwoColumnsTopToBottom: existing fields stay in the left column, the right
column starts empty. Custom Links sections are a separate type and are left
alone. Safe to re-run.

Run:  python scripts/setup_opportunity_layouts.py
"""

import sys

from setup_opportunity_fields import LAYOUTS
from setup_quote_fields import apply
from sf_session import connect

TWO_COLUMN = "TwoColumnsTopToBottom"


def make_two_column(md, layout) -> list:
    """Convert one-column sections in place; return the labels changed."""
    changed = []
    for section in layout.layoutSections:
        if section.style == "CustomLinks" or section.style.startswith("TwoColumns"):
            continue
        cols = [c for c in (section.layoutColumns or []) if c]
        left = cols[0] if cols else md.LayoutColumn()
        section.style = TWO_COLUMN
        section.layoutColumns = [left, md.LayoutColumn()]
        changed.append(section.label)
    return changed


def main() -> int:
    md = connect().mdapi
    for name in LAYOUTS:
        layout = md.Layout.read(name)
        changed = make_two_column(md, layout)
        if not changed:
            print(f"OK    {name}: already two-column")
            continue
        if not apply(lambda: md.Layout.update(layout),
                     f"{name}: two-column {', '.join(changed)}"):
            return 1
    print(f"\nOpportunity layouts: PASSED ({len(LAYOUTS)} layouts two-column)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
