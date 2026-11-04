from anvil import *

from ._anvil_designer import AlertRowTemplate
from ... import pp


class AlertRow(AlertRowTemplate):
    """One booking waiting for approval in the header bell. item = {restaurant_id, restaurant, id, name, date, time, party}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.who.text = "%s · %s" % (i["name"], "%d guest%s" % (i["party"], "" if i["party"] == 1 else "s"))
        self.sub.text = "%s · %s at %s" % (i["restaurant"], pp.fmt_date(i["date"], "short"), i["time"])

    def row_click(self, event):
        self.parent.raise_event("x-open-alert", item=self.item)
