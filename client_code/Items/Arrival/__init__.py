from anvil import *

from ._anvil_designer import ArrivalTemplate
from ... import state


class Arrival(ArrivalTemplate):
    """A guest due today (Today -> Who's coming). item = {id, time, name, party, tables, seated, due, status}.
    The button is the one-tap next step: Seat a confirmed booking, Finish a seated one; it raises
    x-status(res=, status=) on the RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        a = self.item
        self.time_label.text = a["time"]
        self.name_label.text = "%s · %s%s" % (a["name"], state.plural(a["party"], "guest"), (" · " + " + ".join(a["tables"])) if a.get("tables") else "")
        self._next = None
        if a.get("seated"):
            self.badge.text, self.badge.role, self._next = "Here now", ["badge", "badge-good"], "done"
        elif a.get("status") == "pending":
            self.badge.text, self.badge.role = "Awaiting approval", ["badge", "badge-warn"]
        else:
            self.badge.text, self._next = "Due now" if a.get("due") else "Expected", "seated"
            if a.get("due"):
                self.badge.role = ["badge", "badge-brand"]
        self.act_button.visible = bool(self._next)
        self.act_button.text = "Finish" if self._next == "done" else "Seat"
        state.set_control_attr(self.act_button, "aria-label", "%s %s, %s" % (self.act_button.text, a["name"], a["time"]))

    @handle("act_button", "click")
    def act_button_click(self, **event_args):
        if self._next:
            self.parent.raise_event("x-status", res=self.item, status=self._next)
