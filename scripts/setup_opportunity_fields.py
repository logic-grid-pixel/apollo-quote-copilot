"""Phase 0 setup: create Quote Copilot custom fields on Opportunity.

Same approach as setup_quote_fields.py: upsert fields, grant FLS to System
Administrator, add a "Quote Copilot" section to every Opportunity layout. Also
adds the fields to the Quote_Copilot_User permission set so demo users see them.
Safe to re-run.

Run:  python scripts/setup_opportunity_fields.py
"""

import sys

from setup_quote_fields import SEGMENTS, apply, connect, deploy_fields, picklist
import setup_quote_fields

OBJECT = "Opportunity"
LAYOUTS = [
    "Opportunity-Opportunity Layout",
    "Opportunity-Opportunity %28Sales%29 Layout",
    "Opportunity-Opportunity %28Marketing%29 Layout",
    "Opportunity-Opportunity %28Support%29 Layout",
]
PERMSET = "Quote_Copilot_User"

FIELDS = [
    {"fullName": "Segment__c", "label": "Segment", "type": "Picklist",
     "valueSet": picklist(SEGMENTS)},
    {"fullName": "Effective_Discount__c", "label": "Effective Discount", "type": "Percent",
     "precision": 5, "scale": 2},
    {"fullName": "Product_Mix__c", "label": "Product Mix", "type": "Text", "length": 255},
    {"fullName": "Approver_Level__c", "label": "Approver Level", "type": "Picklist",
     "valueSet": picklist(["Rep", "Manager", "VP", "CFO"])},
    {"fullName": "Renewal_Outcome__c", "label": "Renewal Outcome", "type": "Picklist",
     "valueSet": picklist(["Renewed", "Expanded", "Churned", "Too Early"])},
    {"fullName": "Employee_Band__c", "label": "Employee Band", "type": "Picklist",
     "valueSet": picklist(["<200", "200-2000", ">2000"])},
    {"fullName": "Seed_Key__c", "label": "Seed Key", "type": "Text", "length": 50,
     "externalId": True, "unique": True, "caseSensitive": False},
    # Set by the "Request Quote Copilot" quick action (setup_quote_copilot_action.py).
    {"fullName": "Quote_Copilot_Requested__c", "label": "Quote Copilot Requested",
     "type": "Checkbox", "defaultValue": "false",
     "description": "Checked by the Request Quote Copilot button. Visual stub: nothing acts on it yet."},
]


def main() -> int:
    sf = connect()
    if not deploy_fields(sf, OBJECT, FIELDS, LAYOUTS):
        return 1

    # Demo users (Standard User profile) get field access via the permission set.
    md = sf.mdapi
    perms = [{"field": f"{obj}.{f['fullName']}", "readable": True, "editable": True}
             for obj, defs in [("Quote", setup_quote_fields.FIELDS), (OBJECT, FIELDS)]
             for f in defs]
    if not apply(lambda: md.PermissionSet.update(
            md.PermissionSet(fullName=PERMSET, label="Quote Copilot User",
                             fieldPermissions=perms)),
                 f"permission set {PERMSET}"):
        return 1

    print(f"\nPhase 0 Opportunity fields: PASSED ({len(FIELDS)} fields on "
          f"{len(LAYOUTS)} layouts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
