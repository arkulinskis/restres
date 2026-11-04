from anvil import *

from ._anvil_designer import ApprovalCardTemplate
from ... import pp, state


class ApprovalCard(ApprovalCardTemplate):
    """A booking waiting for approval, with its numbers: how full the restaurant is with and without it, against the
    auto-approval limit, and how many other tables are free. item = a pending reservation view (+ analysis, guest)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        a = r.get("analysis") or {}
        self.when.text = "%s · %s–%s" % (pp.fmt_date(r["date"], "short"), r["time"], r["end"])
        self.name_label.text = r["name"]
        self.party_label.text = " · " + state.plural(r["party"], "guest")
        g = r.get("guest") or {}
        if g.get("visits"):
            self.guest_badge.visible = True
            self.guest_badge.text = "%s · %s" % ("VIP" if g.get("vip") else "Regular" if g.get("regular") else "Been before", state.plural(g["visits"], "visit"))
        self.why.text = r.get("review_reason") or "Needs a decision."
        with_, without, thr = min(100, a.get("pct_with") or 0), min(100, a.get("pct_without") or 0), a.get("threshold") or 80
        self.bar_with.style["width"] = "%d%%" % with_
        self.bar_without.style["width"] = "%d%%" % without
        self.bar_thr.style["left"] = "%d%%" % thr
        self.meter_label.text = "%d%% booked now · %d%% if you accept · limit %d%%" % (without, with_, thr)
        self.table_label.text = " + ".join(r.get("table_names") or []) or "No table"
        self.free_label.text = state.plural(a.get("free_units") or 0, "other table") + " free"
        self.phone_link.visible = bool(r.get("phone"))
        self.phone_label.text = r.get("phone") or ""
        state.set_attr(self.phone_link, "href", "tel:" + (r.get("phone") or ""))
        self.notes_label.visible = bool(r.get("notes"))
        self.notes_label.text = "“%s”" % (r.get("notes") or "")
        self.goto_button.visible = r["date"] != r.get("_day")

    @handle("approve_button", "click")
    def approve_button_click(self, **event_args):
        self.parent.raise_event("x-status", res=self.item, status="confirmed")

    @handle("decline_button", "click")
    def decline_button_click(self, **event_args):
        self.parent.raise_event("x-status", res=self.item, status="declined")

    @handle("details_button", "click")
    def details_button_click(self, **event_args):
        self.parent.raise_event("x-edit", res=self.item)

    @handle("goto_button", "click")
    def goto_button_click(self, **event_args):
        self.parent.raise_event("x-goto", date=self.item["date"])
