"""Phase 0 setup: Deal Desk roles, demo users, Task queue and Quote list views.

  Roles:  Deal Desk Manager > Deal Desk Analyst > Account Executive
  Users:  one demo user per free Salesforce license (ae.demo@, dealdesk.demo@,
          ddmanager.demo@ in that order); the running admin takes Deal Desk
          Manager if it has no role and ddmanager.demo@ could not be created.
  Queue:  Deal Desk (Task), members = demo users + admin
  Views:  Quote "Deal Desk Queue" and "Escalations"

Safe to re-run: existing records are found by name and reused.
Run:  python scripts/setup_deal_desk.py
"""

import os
import sys

from dotenv import load_dotenv
from simple_salesforce import Salesforce

import setup_quote_fields

USER_DOMAIN = "quotecopilot.demo"  # usernames must be unique across all of Salesforce
PERMSET = "Quote_Copilot_User"
QUEUE = "Deal_Desk"
UI_API_VERSION = "67.0"

ROLES = [  # (name, developer name, parent developer name)
    ("Deal Desk Manager", "Deal_Desk_Manager", None),
    ("Deal Desk Analyst", "Deal_Desk_Analyst", "Deal_Desk_Manager"),
    ("Account Executive", "Account_Executive", "Deal_Desk_Analyst"),
]

USERS = [  # (username prefix, first, last, alias, role developer name)
    ("ae.demo", "Alex", "AE (Demo)", "aedemo", "Account_Executive"),
    ("dealdesk.demo", "Dana", "Deal Desk (Demo)", "dddemo", "Deal_Desk_Analyst"),
    ("ddmanager.demo", "Morgan", "DD Manager (Demo)", "ddmgr", "Deal_Desk_Manager"),
]

LIST_COLUMNS = ["QUOTE.NAME", "OPPORTUNITY.NAME", "Rep_Segment__c", "Verified_Segment__c",
                "Effective_Discount__c", "Approval_Level_Required__c", "Preflight_Status__c"]

LIST_VIEWS = [
    {"fullName": "Quote.Deal_Desk_Queue", "label": "Deal Desk Queue",
     "filters": [{"field": "Preflight_Status__c", "operation": "equals",
                  "value": "Needs Approval"}],
     "sort": ("Effective_Discount__c", False)},
    {"fullName": "Quote.Escalations", "label": "Escalations",
     "filters": [{"field": "Approval_Level_Required__c", "operation": "equals",
                  "value": "VP,CFO"}],
     "sort": None},
]


def first(sf, soql):
    recs = sf.query(soql)["records"]
    return recs[0] if recs else None


def ensure(sf, sobject, soql, data, label):
    rec = first(sf, soql)
    if rec:
        print(f"OK    {label} (exists)")
        return rec["Id"]
    new_id = getattr(sf, sobject).create(data)["id"]
    print(f"OK    {label} (created)")
    return new_id


def main() -> int:
    load_dotenv(".env")
    sf = Salesforce(
        username=os.environ["SF_USERNAME"],
        password=os.environ["SF_PASSWORD"],
        security_token=os.environ["SF_SECURITY_TOKEN"],
        domain=os.getenv("SF_DOMAIN", "login"),
    )

    # 1. Roles
    role_ids = {}
    for name, dev, parent in ROLES:
        role_ids[dev] = ensure(
            sf, "UserRole", f"SELECT Id FROM UserRole WHERE DeveloperName = '{dev}'",
            {"Name": name, "DeveloperName": dev,
             "ParentRoleId": role_ids.get(parent)}, f"role {name}")

    # 2. Permission set for the Quote Copilot fields (profiles other than Admin).
    #    Quote object access itself comes from the Standard User profile.
    field_names = [f"Quote.{f['fullName']}" for f in setup_quote_fields.FIELDS]
    sf.mdapi.PermissionSet.upsert([sf.mdapi.PermissionSet(
        fullName=PERMSET, label="Quote Copilot User",
        description="Read/edit the Quote Copilot fields on Quote",
        fieldPermissions=[{"field": n, "readable": True, "editable": True}
                          for n in field_names])])
    permset_id = first(sf, f"SELECT Id FROM PermissionSet WHERE Name = '{PERMSET}'")["Id"]
    print(f"OK    permission set {PERMSET}")

    # 3. Users, one per free Salesforce license
    me = first(sf, "SELECT Id, Email, UserRoleId, TimeZoneSidKey, LocaleSidKey, "
                   "LanguageLocaleKey, EmailEncodingKey FROM User "
                   f"WHERE Username = '{os.environ['SF_USERNAME']}'")
    lic = first(sf, "SELECT UsedLicenses, TotalLicenses FROM UserLicense "
                    "WHERE Name = 'Salesforce'")
    free = lic["TotalLicenses"] - lic["UsedLicenses"]
    profile_id = first(sf, "SELECT Id FROM Profile WHERE Name = 'Standard User'")["Id"]
    member_ids, made_manager = [me["Id"]], False
    for prefix, fn, ln, alias, role in USERS:
        username = f"{prefix}@{USER_DOMAIN}"
        existing = first(sf, f"SELECT Id FROM User WHERE Username = '{username}'")
        if existing:
            user_id = existing["Id"]
            print(f"OK    user {username} (exists)")
        elif free > 0:
            user_id = sf.User.create({
                "Username": username, "Email": me["Email"], "FirstName": fn,
                "LastName": ln, "Alias": alias, "ProfileId": profile_id,
                "UserRoleId": role_ids[role], "TimeZoneSidKey": me["TimeZoneSidKey"],
                "LocaleSidKey": me["LocaleSidKey"], "EmailEncodingKey": me["EmailEncodingKey"],
                "LanguageLocaleKey": me["LanguageLocaleKey"]})["id"]
            free -= 1
            print(f"OK    user {username} (created, role {role})")
        else:
            print(f"SKIP  user {username}: no free Salesforce licenses")
            continue
        member_ids.append(user_id)
        made_manager = made_manager or role == "Deal_Desk_Manager"
        if not first(sf, "SELECT Id FROM PermissionSetAssignment "
                         f"WHERE AssigneeId = '{user_id}' AND PermissionSetId = '{permset_id}'"):
            sf.PermissionSetAssignment.create({"AssigneeId": user_id,
                                               "PermissionSetId": permset_id})

    if not made_manager and not me["UserRoleId"]:
        sf.User.update(me["Id"], {"UserRoleId": role_ids["Deal_Desk_Manager"]})
        print("OK    admin user given role Deal Desk Manager")

    # 4. Deal Desk queue for Tasks
    queue_id = ensure(sf, "Group", f"SELECT Id FROM Group WHERE Type = 'Queue' "
                                   f"AND DeveloperName = '{QUEUE}'",
                      {"Name": "Deal Desk", "DeveloperName": QUEUE, "Type": "Queue",
                       "DoesSendEmailToMembers": False}, "queue Deal Desk")
    ensure(sf, "QueueSobject", f"SELECT Id FROM QueueSobject WHERE QueueId = '{queue_id}' "
                               "AND SobjectType = 'Task'",
           {"QueueId": queue_id, "SobjectType": "Task"}, "queue supports Task")
    have = {m["UserOrGroupId"] for m in sf.query(
        f"SELECT UserOrGroupId FROM GroupMember WHERE GroupId = '{queue_id}'")["records"]}
    for uid in member_ids:
        if uid not in have:
            sf.GroupMember.create({"GroupId": queue_id, "UserOrGroupId": uid})
    print(f"OK    queue members: {len(member_ids)}")

    # 5. Quote list views (visible to all users)
    sf.mdapi.ListView.upsert([sf.mdapi.ListView(
        fullName=v["fullName"], label=v["label"], filterScope="Everything",
        columns=LIST_COLUMNS, filters=v["filters"]) for v in LIST_VIEWS])
    print("OK    list views: " + ", ".join(v["label"] for v in LIST_VIEWS))

    # Sort order is a per-user list preference in Lightning; set it for the admin.
    # list-preferences is not available on simple_salesforce's default API (59.0).
    ui_api = f"https://{sf.sf_instance}/services/data/v{UI_API_VERSION}/ui-api"
    for v in LIST_VIEWS:
        if v["sort"]:
            field, asc = v["sort"]
            api_name = v["fullName"].split(".")[1]
            sf.session.patch(
                f"{ui_api}/list-preferences/Quote/{api_name}", headers=sf.headers,
                json={"orderedBy": [{"fieldApiName": field, "isAscending": asc}]},
            ).raise_for_status()
            print(f"OK    {v['label']} sorted by {field} "
                  f"{'asc' if asc else 'desc'} (admin's view)")

    print("\nPhase 0 Deal Desk setup: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
