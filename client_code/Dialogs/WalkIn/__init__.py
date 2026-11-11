from anvil import *
import anvil.server

from ._anvil_designer import WalkInTemplate
from ... import state


class WalkIn(WalkInTemplate):
    """A walk-in at the host stand: one tap on the party size seats them now at the best free table.
    Closes with the server's reply {day, tables, party} (Portal.quick_walk_in), "details" (open the full booking
    editor instead), or None."""

    def __init__(self, rid, **properties):
        super().__init__(**properties)
        self.rid = rid
        self.sizes_panel.items = [{"label": str(n), "value": n, "aria": state.plural(n, "guest")} for n in range(1, 13)]
        self.sizes_panel.add_event_handler("x-chip", self._pick)

    def _pick(self, value, **event_args):
        r = anvil.server.call("quick_walk_in", self.rid, value)
        if not r or not r.get("ok"):
            self.message.visible = True
            self.message.text = (r or {}).get("error") or "That didn't work. Try “Add a name or a note”."
            return
        self.raise_event("x-close-alert", value=dict(r, party=value))

    @handle("details_button", "click")
    def details_button_click(self, **event_args):
        self.raise_event("x-close-alert", value="details")

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
