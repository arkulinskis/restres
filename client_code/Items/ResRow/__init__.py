from anvil import *

from ._anvil_designer import ResRowTemplate
from ... import pp, state

# status -> (button text, the status one tap moves it to, extra button role)
NEXT = {"pending": ("Approve", "confirmed", "btn-good"), "confirmed": ("Seat", "seated", None), "seated": ("Finish", "done", None)}


class ResRow(ResRowTemplate):
    """A booking in the Reservations list (and a guest's history). item = a reservation view.
    Tapping the row raises x-edit(res=). With item["_act"] the row also gets the one-tap next step for the host
    stand: Approve a request, Seat a confirmed booking (today's only: item["_today"]), Finish a seated table;
    it raises x-status(res=, status=). item["_show_date"] puts the date before the time (Upcoming, guest history)."""

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
        self.notes_label.text = "“%s”" % r["notes"] if r.get("notes") else ""
        self.staff_label.visible = bool(r.get("staff_note"))
        self.staff_label.text = "Staff: " + (r.get("staff_note") or "")
        self.party_label.text = str(r["party"])
        state.set_attr(self.party_label, "aria-label", state.plural(r["party"], "guest"))
        self.table_label.text = " + ".join(r.get("table_names") or []) or "—"
        self.status_badge.text = pp.STATUS.get(r["status"], r["status"])
        step = NEXT.get(r["status"]) if r.get("_act") else None
        if step and r["status"] == "confirmed" and not r.get("_today"):
            step = None  # nobody is seated days ahead
        self._next = step[1] if step else None
        self.act_button.visible = bool(step)
        if step:
            self.act_button.text = step[0]
            self.act_button.role = ["btn", "btn-sm"] + ([step[2]] if step[2] else [])
            state.set_control_attr(self.act_button, "aria-label", "%s %s, %s" % (step[0], r["name"], r["time"]))
        # on a phone the button says where the booking stands, so the badge makes room for it
        self.status_badge.role = ["badge", pp.STATUS_ROLE.get(r["status"], "badge")] + (["pp-hide-m"] if step else [])
        self.source_label.text = pp.SOURCE.get(r.get("source"), r.get("source") or "")

    def row_click(self, event):
        self.parent.raise_event("x-edit", res=self.item)

    @handle("act_button", "click")
    def act_button_click(self, **event_args):
        if self._next:
            self.parent.raise_event("x-status", res=self.item, status=self._next)
