from anvil import *

from ._anvil_designer import ArrivalTemplate
from ... import state


class Arrival(ArrivalTemplate):
    """A guest due today (Today -> Who's coming). item = {time, name, party, tables, seated, status}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        a = self.item
        self.time_label.text = a["time"]
        self.name_label.text = "%s · %s%s" % (a["name"], state.plural(a["party"], "guest"), (" · " + " + ".join(a["tables"])) if a.get("tables") else "")
        if a.get("seated"):
            self.badge.text, self.badge.role = "Here now", ["badge", "badge-good"]
        elif a.get("status") == "pending":
            self.badge.text, self.badge.role = "Awaiting approval", ["badge", "badge-warn"]
        else:
            self.badge.text = "Expected"
