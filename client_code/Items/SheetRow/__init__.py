from anvil import *

from ._anvil_designer import SheetRowTemplate


class SheetRow(SheetRowTemplate):
    """A booking on the printable day sheet. item = a reservation view."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        g = r.get("guest") or {}
        self.table_label.text = " + ".join(r.get("table_names") or []) or "—"
        self.name_label.text = r["name"] + (" ★" if g.get("vip") or g.get("regular") else "") + (" (to approve)" if r["status"] == "pending" else "")
        self.party_label.text = str(r["party"])
        self.notes_label.text = " · ".join(x for x in [r.get("notes") or "", r.get("staff_note") or "", g.get("note") or ""] if x)
        self.phone_label.text = r.get("phone") or ""
