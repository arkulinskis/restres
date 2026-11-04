import datetime

from anvil import *
import anvil.server

from ._anvil_designer import ReservationsTemplate
from ... import pp, router, state

ORDER = {"pending": 0, "confirmed": 0, "seated": 0, "done": 1, "no_show": 2, "declined": 2, "cancelled": 2}


class Reservations(ReservationsTemplate):
    """#reservations/<rid>[/<YYYY-MM-DD>]: one restaurant's day. Approvals first, then the day (timeline or list), the
    booking editor (Dialogs.BookingEditor), walk-ins and a printable day sheet."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        state.set_control_attr(self.date_picker, "aria-label", "Day")
        self.rid = args[0]
        self.view = state.store_get("resView", "timeline")
        self.D = anvil.server.call("get_day", self.rid, args[1] if len(args) > 1 else None)
        self.approvals_panel.add_event_handler("x-status", self._status_event)
        self.approvals_panel.add_event_handler("x-edit", self._edit_event)
        self.approvals_panel.add_event_handler("x-goto", self._goto_event)
        self.list_panel.add_event_handler("x-edit", self._edit_event)
        self._draw()

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        self.approvals.visible = bool(D["pending"])
        self.pending_count.text = str(len(D["pending"]))
        for p in D["pending"]:
            p["_day"] = D["date"]
        self.approvals_panel.items = D["pending"]
        self.day_title.text = pp.fmt_date(D["date"])
        self.today_button.visible = D["date"] != D["today"]
        self.date_picker.date = datetime.date.fromisoformat(D["date"])
        s = D["summary"]
        self.hours_label.text = (pp.hours_text(D["hours"]) if D["hours"] else "Closed") + " · " + D["hours_label"]
        self.count_label.text = state.plural(s["bookings"], "booking")
        self.covers_label.text = state.plural(s["covers"], "guest")
        self.peak_label.visible = bool(s["peak"]["time"])
        self.peak_label.text = "Busiest %d%% at %s" % (s["peak"]["pct"], s["peak"]["time"] or "")
        manager = pp.can(D["nav"]["restaurant"].get("role"), "manager")
        self.events_panel.items = [dict(e, rid=self.rid, manager=manager) for e in D.get("events") or []]
        self.view_timeline.classes["on"] = self.view == "timeline"
        self.view_list.classes["on"] = self.view == "list"
        self.timeline_part.visible = self.view == "timeline"
        self.list_part.visible = self.view == "list"
        if self.view == "timeline":
            self.timeline.draw(D)
        rows = sorted(D["reservations"], key=lambda r: (ORDER.get(r["status"], 3), r["start_min"]))
        self.list_card.visible = bool(rows)
        self.list_empty.visible = not rows
        self.list_panel.items = rows

    def load(self, day):
        self.D = anvil.server.call("get_day", self.rid, day)
        router.replace("reservations", self.rid, self.D["date"])
        self._draw()

    def _find(self, res_id):
        for r in self.D["reservations"] + self.D["pending"]:
            if r["id"] == res_id:
                return r
        return None

    # ---------------------------------------------------------------- the day bar
    @handle("prev_button", "click")
    def prev_button_click(self, **event_args):
        self.load(pp.add_days(self.D["date"], -1))

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        self.load(pp.add_days(self.D["date"], 1))

    @handle("today_button", "click")
    def today_button_click(self, **event_args):
        self.load(self.D["today"])

    @handle("date_picker", "change")
    def date_picker_change(self, **event_args):
        if self.date_picker.date:
            self.load(self.date_picker.date.isoformat())

    def view_click(self, event):
        self.view = event.currentTarget.getAttribute("data-v")
        state.store_set("resView", self.view)
        self._draw()

    # ---------------------------------------------------------------- bookings
    def _editor(self, res=None, preset=None):
        from ...Dialogs.BookingEditor import BookingEditor
        out = alert(BookingEditor(self.rid, self.D, res=res, preset=preset), buttons=[], role="app-dialog", large=True, dismissible=True)
        if out:
            self.D = out
            self._draw()
            self._bell()

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        self._editor()

    @handle("walkin_button", "click")
    def walkin_button_click(self, **event_args):
        now = self.D.get("now_min")
        step = self.D["settings"]["slot_min"]
        t = pp.hm((now // step) * step) if now is not None else "19:00"
        self._editor(preset={"time": t, "source": "walk_in", "status": "seated", "name": "Walk-in"})

    @handle("timeline", "edit")
    def timeline_edit(self, id, **event_args):
        r = self._find(id)
        if r:
            self._editor(r)

    @handle("timeline", "slot")
    def timeline_slot(self, time, table, **event_args):
        self._editor(preset={"time": time, "tables": [table] if table else []})

    def _edit_event(self, res, **event_args):
        self._editor(res)

    def _goto_event(self, date, **event_args):
        self.load(date)

    def _status_event(self, res, status, **event_args):
        day = change_status(self.rid, res, status, self.D["date"])
        if day:
            self.D = day
            self._draw()
            self._bell()

    def _bell(self):
        shell = getattr(self, "layout", None)
        if shell is not None and hasattr(shell, "refresh_alerts"):
            shell.refresh_alerts()

    @handle("print_button", "click")
    def print_button_click(self, **event_args):
        from ...Dialogs.DaySheet import DaySheet
        alert(DaySheet(self.D), buttons=[], role=["app-dialog", "pp-print-dialog"], large=True, dismissible=True)


def change_status(rid, res, status, day):
    """Approve / decline / cancel / seat / no-show, asking first for the ones that release the table.
    Returns the day's new data (Portal.get_day), or None when nothing changed."""
    if status in ("declined", "cancelled", "no_show"):
        title = {"declined": "Decline this request?", "cancelled": "Cancel this booking?", "no_show": "Mark as a no-show?"}[status]
        text = "%s, %s at %s. " % (res["name"], pp.fmt_date(res["date"], "short"), res["time"])
        text += "It counts in the guest book." if status == "no_show" else "The table is released for other guests."
        label = {"declined": "Decline", "cancelled": "Cancel booking", "no_show": "No-show"}[status]
        if not confirm(text, title=title, buttons=[("Keep it", False), (label, True)]):
            return None
    r = state.call("set_status", rid, res["id"], status, day)
    if not r:
        return None
    words = {"confirmed": "Approved" if res["status"] == "pending" else "Confirmed", "declined": "Declined", "cancelled": "Cancelled",
             "seated": "Seated", "done": "Finished", "no_show": "Marked as a no-show"}
    state.toast(words.get(status, "Updated"), "ok")
    return r["day"]
