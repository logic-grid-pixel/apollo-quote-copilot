"""Every Opportunity page layout section is two-column (integration only).

Custom Links sections are a separate section type and are left alone.
"""

import pytest

from setup_opportunity_fields import LAYOUTS
from sf_session import connect

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def sf():
    return connect()


@pytest.mark.parametrize("layout_name", LAYOUTS)
def test_all_sections_two_column(sf, layout_name):
    layout = sf.mdapi.Layout.read(layout_name)
    one_col = [s.label for s in layout.layoutSections
               if s.style != "CustomLinks" and not s.style.startswith("TwoColumns")]
    assert one_col == [], f"{layout_name}: one-column sections {one_col}"


@pytest.mark.parametrize("layout_name", LAYOUTS)
def test_description_field_kept(sf, layout_name):
    layout = sf.mdapi.Layout.read(layout_name)
    fields = {i.field for s in layout.layoutSections for c in (s.layoutColumns or []) if c
              for i in (c.layoutItems or []) if i and i.field}
    assert "Description" in fields
