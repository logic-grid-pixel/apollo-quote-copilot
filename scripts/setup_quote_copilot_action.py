"""Phase 0 setup: "Request Quote Copilot" button on Opportunity (visual stub).

An Update-a-Record quick action that checks Quote_Copilot_Requested__c and
shows "Quote Copilot requested." Nothing listens to the flag yet; it only
demonstrates where a rep would trigger the skill from inside Salesforce.

Needs the flag field first: run setup_opportunity_fields.py (which defines it).
Adds the action first in the Lightning action bar on every Opportunity layout.
Safe to re-run.

Run:  python scripts/setup_quote_copilot_action.py
"""

import sys

from setup_opportunity_fields import LAYOUTS
from setup_quote_fields import apply
from sf_session import connect

ACTION = "Request_Quote_Copilot"
FLAG = "Quote_Copilot_Requested__c"
SUCCESS_MESSAGE = "Quote Copilot requested."


def action_metadata(md):
    return md.QuickAction(
        fullName=f"Opportunity.{ACTION}",
        label="Request Quote Copilot",
        type="Update",
        description="Visual stub: flags the Opportunity for Quote Copilot.",
        successMessage=SUCCESS_MESSAGE,
        optionsCreateFeedItem=False,
        # Update actions reject literalValue for a checkbox; a formula is accepted.
        fieldOverrides=[{"field": FLAG, "formula": "TRUE"}],
        quickActionLayout={"layoutSectionStyle": "TwoColumnsLeftToRight",
                           "quickActionLayoutColumns": [{}, {}]},
    )


def add_to_layout(md, layout_name) -> bool:
    """Put the action first in the layout's Lightning action bar."""
    layout = md.Layout.read(layout_name)
    name = f"Opportunity.{ACTION}"
    items = [i for i in layout.platformActionList.platformActionListItems
             if i.actionName != name]
    items.insert(0, md.PlatformActionListItem(actionName=name, actionType="QuickAction",
                                              sortOrder=0))
    for n, item in enumerate(items):
        item.sortOrder = n
    layout.platformActionList.platformActionListItems = items
    return apply(lambda: md.Layout.update(layout), f"action on layout '{layout_name}'")


def main() -> int:
    sf = connect()
    md = sf.mdapi
    if FLAG not in {f["name"] for f in sf.Opportunity.describe()["fields"]}:
        print(f"FAIL  {FLAG} missing. Run scripts/setup_opportunity_fields.py first.")
        return 1
    if not apply(lambda: md.QuickAction.upsert([action_metadata(md)]),
                 f"quick action Opportunity.{ACTION}"):
        return 1
    if not all(add_to_layout(md, name) for name in LAYOUTS):
        return 1
    print(f"\nPhase 0 Quote Copilot button: PASSED (on {len(LAYOUTS)} layouts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
