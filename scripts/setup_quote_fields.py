"""Phase 0 setup: create Quote Copilot custom fields on Quote.

Creates (or updates) the eight custom fields, grants field-level security to
the System Administrator profile, and adds them to the Quote page layout in a
"Quote Copilot" section. Safe to re-run.

Run:  python scripts/setup_quote_fields.py
"""

import os
import sys

from dotenv import load_dotenv
from simple_salesforce import Salesforce

OBJECT = "Quote"
LAYOUT = "Quote-Quote Layout"
PROFILE = "Admin"  # API name of System Administrator
SECTION = "Quote Copilot"

SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]


def picklist(values):
    return {
        "valueSetDefinition": {
            "sorted": False,
            "value": [{"fullName": v, "label": v, "default": False} for v in values],
        }
    }


FIELDS = [
    {"fullName": "Rep_Segment__c", "label": "Rep Segment", "type": "Picklist",
     "valueSet": picklist(SEGMENTS)},
    {"fullName": "Verified_Segment__c", "label": "Verified Segment", "type": "Picklist",
     "valueSet": picklist(SEGMENTS + ["Unverified"])},
    {"fullName": "Segment_Mismatch__c", "label": "Segment Mismatch", "type": "Checkbox",
     "defaultValue": "false"},
    {"fullName": "Effective_Discount__c", "label": "Effective Discount", "type": "Percent",
     "precision": 5, "scale": 2},
    {"fullName": "Approval_Level_Required__c", "label": "Approval Level Required",
     "type": "Picklist", "valueSet": picklist(["Rep", "Manager", "VP", "CFO"])},
    {"fullName": "Preflight_Status__c", "label": "Preflight Status", "type": "Picklist",
     "valueSet": picklist(["Ready", "Needs Approval", "Blocked on Open Questions"])},
    {"fullName": "Open_Questions__c", "label": "Open Questions", "type": "LongTextArea",
     "length": 32768, "visibleLines": 5},
    {"fullName": "Source_Citations__c", "label": "Source Citations", "type": "LongTextArea",
     "length": 32768, "visibleLines": 5},
]


def apply(call, what, count=1):
    """simple_salesforce metadata calls raise on any error and return None."""
    try:
        call()
    except Exception as e:  # noqa: BLE001 - surface the Salesforce message
        print(f"FAIL  {what}: {e}")
        return False
    print(f"OK    {what}" + (f" ({count})" if count > 1 else ""))
    return True


def connect() -> Salesforce:
    load_dotenv(".env")
    return Salesforce(
        username=os.environ["SF_USERNAME"],
        password=os.environ["SF_PASSWORD"],
        security_token=os.environ["SF_SECURITY_TOKEN"],
        domain=os.getenv("SF_DOMAIN", "login"),
    )


def deploy_fields(sf, obj, field_defs, layouts, section=SECTION, profile=PROFILE) -> bool:
    """Upsert custom fields on obj, grant FLS to profile, place them on each layout."""
    md = sf.mdapi
    names = [f"{obj}.{f['fullName']}" for f in field_defs]

    # 1. Fields
    fields = [md.CustomField(**{**f, "fullName": n}) for f, n in zip(field_defs, names)]
    if not apply(lambda: md.CustomField.upsert(fields), "fields upserted", len(fields)):
        return False

    # 2. Field-level security (API-created fields are hidden from every profile)
    perms = [{"field": n, "readable": True, "editable": True} for n in names]
    if not apply(lambda: md.Profile.update(md.Profile(fullName=profile, fieldPermissions=perms)),
                 f"field-level security on {profile} profile"):
        return False

    # 3. Page layouts: add (or refresh) the section
    for layout_name in layouts:
        layout = md.Layout.read(layout_name)
        layout.layoutSections = [s for s in layout.layoutSections if s.label != section]
        placed = {i.field for s in layout.layoutSections for c in (s.layoutColumns or []) if c
                  for i in (c.layoutItems or []) if i and i.field}
        todo = [f["fullName"] for f in field_defs if f["fullName"] not in placed]
        half = (len(todo) + 1) // 2
        cols = [todo[:half], todo[half:]]
        layout.layoutSections.append(md.LayoutSection(
            label=section, style="TwoColumnsTopToBottom", editHeading=True,
            detailHeading=True, customLabel=True,
            layoutColumns=[md.LayoutColumn(layoutItems=[
                md.LayoutItem(field=f, behavior="Edit") for f in col]) for col in cols],
        ))
        if not apply(lambda: md.Layout.update(layout), f"layout '{layout_name}'"):
            return False

    # 4. Verify via describe
    sf_fields = {f["name"] for f in getattr(sf, obj).describe()["fields"]}
    missing = [f["fullName"] for f in field_defs if f["fullName"] not in sf_fields]
    if missing:
        print("FAIL  not visible via describe: " + ", ".join(missing))
        return False
    return True


def main() -> int:
    if not deploy_fields(connect(), OBJECT, FIELDS, [LAYOUT]):
        return 1
    print(f"\nPhase 0 Quote fields: PASSED ({len(FIELDS)} fields on layout '{LAYOUT}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
