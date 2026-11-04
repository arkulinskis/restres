from anvil import *

from ._anvil_designer import ResRowTemplate
from ... import pp, state


class ResRow(ResRowTemplate):
    """A booking in the Reservations list (and a guest's history). item = a reservation view."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.classes["gone"] = r["status"] in ("cancelled", "declined", "no_show")
        self.time_label.text = r["time"] if not r.get("_show_date") else "%s %s" % (pp.fmt_date(r["date"], "short"), r["time"])
        self.name_label.text = r["name"]
        g = r.get("guest") or {}
        if g.get("vip") or g.get("regular") or g.get("no_shows"):
            self.guest_badge.visible = True
            self.guest_badge.text = "VIP" if g.get("vip") else "Regular" if g.get("regular") else "%d no-show" % g["no_shows"]
            if not g.get("vip") and not g.get("regular"):
                self.guest_badge.role = ["badge", "badge-bad"]
        self.notes_label.visible = bool(r.get("notes"))
        self.notes_label.text = r.get("notes") or ""
        self.staff_label.visible = bool(r.get("staff_note"))
        self.staff_label.text = "Staff: " + (r.get("staff_note") or "")
        self.party_label.text = str(r["party"])
        self.table_label.text = " + ".join(r.get("table_names") or []) or "—"
        self.status_badge.text = pp.STATUS.get(r["status"], r["status"])
        self.status_badge.role = ["badge", pp.STATUS_ROLE.get(r["status"], "badge")]
        self.source_label.text = pp.SOURCE.get(r.get("source"), r.get("source") or "")

    def row_click(self, event):
        self.parent.raise_event("x-edit", res=self.item)
