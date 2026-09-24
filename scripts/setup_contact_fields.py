"""Phase 0 setup: create Quote Copilot custom fields on Contact.

Same approach as setup_account_fields.py. Safe to re-run.

Run:  python scripts/setup_contact_fields.py
"""

import sys

from setup_quote_fields import apply, connect, deploy_fields, picklist
import setup_account_fields
import setup_opportunity_fields
import setup_quote_fields

OBJECT = "Contact"
LAYOUTS = [
    "Contact-Contact Layout",
    "Contact-Contact %28Sales%29 Layout",
    "Contact-Contact %28Marketing%29 Layout",
    "Contact-Contact %28Support%29 Layout",
]
PERMSET = "Quote_Copilot_User"

FIELDS = [
    {"fullName": "Seed_Key__c", "label": "Seed Key", "type": "Text", "length": 50,
     "externalId": True},
    {"fullName": "Buying_Role__c", "label": "Buying Role", "type": "Picklist",
     "valueSet": picklist(["Economic Buyer", "Champion", "Technical Evaluator",
                           "Procurement", "End User"])},
]


def main() -> int:
    sf = connect()
    if not deploy_fields(sf, OBJECT, FIELDS, LAYOUTS):
        return 1

    # Demo users (Standard User profile) get field access via the permission set.
    md = sf.mdapi
    perms = [{"field": f"{obj}.{f['fullName']}", "readable": True, "editable": True}
             for obj, defs in [("Quote", setup_quote_fields.FIELDS),
                               ("Opportunity", setup_opportunity_fields.FIELDS),
                               ("Account", setup_account_fields.FIELDS),
                               (OBJECT, FIELDS)]
             for f in defs]
    if not apply(lambda: md.PermissionSet.update(
            md.PermissionSet(fullName=PERMSET, label="Quote Copilot User",
                             fieldPermissions=perms)),
                 f"permission set {PERMSET}"):
        return 1

    print(f"\nPhase 0 Contact fields: PASSED ({len(FIELDS)} fields on "
          f"{len(LAYOUTS)} layouts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
