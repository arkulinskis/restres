from anvil import *

from ._anvil_designer import GuestRowTemplate
from ... import pp


class GuestRow(GuestRowTemplate):
    """A guest in the guest book. item = Guests.index() entry. Raises x-open(guest=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        g = self.item
        self.name_label.text = g["name"] + (" ★" if g.get("vip") else "")
        self.contact_label.text = " · ".join(x for x in [g.get("email"), g.get("phone")] if x)
        self.visits_label.text = str(g["visits"]) + (" · %d no-show" % g["no_shows"] if g.get("no_shows") else "")
        self.last_label.text = pp.fmt_date(g["last"], "short") if g.get("last") else "—"
        self.next_label.text = pp.fmt_date(g["next"], "short") if g.get("next") else "—"
        tags = list(g.get("tags") or [])
        if g.get("regular") and "Regular" not in tags:
            tags.insert(0, "Regular")
        self.tags_label.text = " · ".join(tags)

    def row_click(self, event):
        self.parent.raise_event("x-open", guest=self.item)
