"""The "Request Quote Copilot" quick action on Opportunity (visual stub).

Integration only: invokes the real action on a demo Opportunity through the
REST quickActions endpoint, checks it set the flag and returns the success
message, then resets the flag.
"""

import pytest

from setup_quote_copilot_action import ACTION, FLAG, LAYOUTS, SUCCESS_MESSAGE
from sf_session import connect

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def sf():
    return connect()


@pytest.fixture
def demo_opp(sf):
    opp = sf.query("SELECT Id FROM Opportunity "
                   "WHERE Seed_Key__c = 'DEMO-OPP-clean-midmarket'")["records"][0]
    sf.Opportunity.update(opp["Id"], {FLAG: False})
    yield opp["Id"]
    sf.Opportunity.update(opp["Id"], {FLAG: False})


def test_action_is_defined_with_success_message(sf):
    desc = sf.restful(f"sobjects/Opportunity/quickActions/{ACTION}/describe")
    assert desc["type"] == "Update"
    # The REST describe omits successMessage; the metadata definition has it.
    action = sf.mdapi.QuickAction.read(f"Opportunity.{ACTION}")
    assert action.successMessage == SUCCESS_MESSAGE
    assert action.optionsCreateFeedItem is False


def test_action_is_on_every_opportunity_layout(sf):
    for name in LAYOUTS:
        layout = sf.mdapi.Layout.read(name)
        actions = [i.actionName for i in layout.platformActionList.platformActionListItems]
        assert f"Opportunity.{ACTION}" in actions, name


def test_invoking_action_sets_flag(sf, demo_opp):
    result = sf.restful(f"sobjects/Opportunity/quickActions/{ACTION}", method="POST",
                        json={"contextId": demo_opp, "record": {}})
    assert result["success"] is True
    assert result.get("feedItemIds") in (None, [])  # no Chatter post
    flag = sf.query(f"SELECT {FLAG} FROM Opportunity WHERE Id = '{demo_opp}'")["records"][0]
    assert flag[FLAG] is True
