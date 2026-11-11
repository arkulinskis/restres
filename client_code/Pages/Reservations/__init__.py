import datetime

from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import ReservationsTemplate
from ... import pp, router, state

ORDER = {"pending": 0, "confirmed": 0, "seated": 0, "done": 1, "no_show": 2, "declined": 2, "cancelled": 2}
VIEWS = ("timeline", "list", "upcoming")


class Reservations(ReservationsTemplate):
    """#reservations/<rid>[/<YYYY-MM-DD>]: one restaurant's day, and the screen that stays open at the host stand.
    Approvals first, then the day as a timeline or a list (one-tap Approve / Seat / Finish on each row), or every
    upcoming booking; the booking editor (Dialogs.BookingEditor), one-tap walk-ins (Dialogs.WalkIn) and a printable
    day sheet. While the page is open it asks the server every minute whether anything changed (live_timer),
    chimes for a new booking or request, and keeps the screen awake."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        state.set_control_attr(self.date_picker, "aria-label", "Day")
        state.live(self.live_status)
        self.rid = args[0]
        self.view = state.store_get("resView", "timeline")
        if self.view not in VIEWS:
            self.view = "timeline"
        self.chime = state.store_get("resChime", True) is not False
        self._dialogs = 0  # open dialogs: the page doesn't redraw underneath them
        self._ticks = 0
        self.U = None      # the Upcoming list (Portal.get_upcoming), loaded when that view is shown
        self._back = anvil.js.report_exceptions(self._on_back)
        self.D = anvil.server.call("get_day", self.rid, args[1] if len(args) > 1 else None)
        for panel in (self.approvals_panel, self.list_panel, self.upcoming_panel):
            panel.add_event_handler("x-status", self._status_event)
            panel.add_event_handler("x-edit", self._edit_event)
        self.approvals_panel.add_event_handler("x-goto", self._goto_event)
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
        view = self.view
        for name in VIEWS:
            getattr(self, "view_" + name).classes["on"] = view == name
            getattr(self, name + "_part").visible = view == name
        self.day_head.visible = view != "upcoming"
        self.upcoming_head.visible = view == "upcoming"
        self.print_button.visible = view != "upcoming"
        self.chime_button.text = "Chime on" if self.chime else "Chime off"
        state.set_control_attr(self.chime_button, "aria-pressed", "true" if self.chime else "false")
        if view == "timeline":
            self.timeline.draw(D)
        elif view == "list":
            today = D["date"] == D["today"]
            rows = sorted(D["reservations"], key=lambda r: (ORDER.get(r["status"], 3), r["start_min"]))
            self.list_card.visible = bool(rows)
            self.list_empty.visible = not rows
            self.list_panel.items = [dict(r, _act=True, _today=today) for r in rows]
        else:
            self._draw_upcoming()

    def _draw_upcoming(self):
        if self.U is None:
            self.U = state.call_quiet("get_upcoming", self.rid) or {"reservations": [], "today": self.D["today"], "more": False}
        U: dict = dict(self.U)
        found: list = list(U["reservations"])
        rows = [dict(r, _act=True, _show_date=True, _today=r["date"] == U["today"]) for r in found]
        self.upcoming_count.text = "%s · %s" % (state.plural(len(rows), "booking"),
                                               state.plural(sum(r["party"] for r in rows), "guest"))
        self.upcoming_card.visible = bool(rows)
        self.upcoming_empty.visible = not rows
        self.upcoming_more.visible = bool(U.get("more"))
        self.upcoming_panel.items = rows

    def _show(self, day):
        """New data for the day (from a dialog, a status change or the live check): redraw everything."""
        self.D = day
        self.U = None
        self._draw()
        self._bell()

    def load(self, day):
        self.D = anvil.server.call("get_day", self.rid, day)
        self.U = None
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
        self.U = None
        self._draw()

    # ---------------------------------------------------------------- bookings
    def _dialog(self, form, **kw):
        """alert() that the live check knows about, so the page isn't redrawn under an open dialog."""
        self._dialogs += 1
        try:
            return alert(form, buttons=[], large=True, dismissible=True, **kw)
        finally:
            self._dialogs -= 1

    def _editor(self, res=None, preset=None):
        from ...Dialogs.BookingEditor import BookingEditor
        out = self._dialog(BookingEditor(self.rid, self.D, res=res, preset=preset), role="app-dialog")
        if out:
            self._show(out)

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        self._editor()

    @handle("walkin_button", "click")
    def walkin_button_click(self, **event_args):
        from ...Dialogs.WalkIn import WalkIn
        out = self._dialog(WalkIn(self.rid), role="app-dialog")
        if out == "details":
            now = self.D.get("now_min")
            step = self.D["settings"]["slot_min"]
            t = pp.hm((now // step) * step) if now is not None else "19:00"
            self._editor(preset={"date": self.D["today"], "time": t, "source": "walk_in", "status": "seated", "name": "Walk-in"})
        elif out:
            tables = " + ".join(out.get("tables") or [])
            state.toast("Walk-in for %d seated %s" % (out["party"], "at " + tables if tables else "(no free table: open the booking to pick one)"), "ok")
            router.replace("reservations", self.rid, out["day"]["date"])
            self._show(out["day"])

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
        if self.view == "upcoming":
            self.view = "list"
        self.load(date)

    def _status_event(self, res, status, **event_args):
        self._dialogs += 1  # declining asks first
        try:
            day = change_status(self.rid, res, status, self.D["date"])
        finally:
            self._dialogs -= 1
        if day:
            self._show(day)

    def _bell(self):
        shell = getattr(self, "layout", None)
        if shell is not None and hasattr(shell, "refresh_alerts"):
            shell.refresh_alerts()

    @handle("print_button", "click")
    def print_button_click(self, **event_args):
        from ...Dialogs.DaySheet import DaySheet
        self._dialog(DaySheet(self.D), role=["app-dialog", "pp-print-dialog"])

    # ---------------------------------------------------------------- the host stand: live, awake, with a chime
    @handle("", "show")
    def form_show(self, **event_args):
        window.PP.wake(True)
        window.document.addEventListener("visibilitychange", self._back)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.PP.wake(False)
        window.document.removeEventListener("visibilitychange", self._back)

    def _on_back(self, event):
        """The tablet woke up, or someone came back to this tab: look for news now instead of waiting for the next minute."""
        if not window.document.hidden:
            self.check_live()

    @handle("chime_button", "click")
    def chime_button_click(self, **event_args):
        self.chime = not self.chime
        state.store_set("resChime", self.chime)
        self.chime_button.text = "Chime on" if self.chime else "Chime off"
        state.set_control_attr(self.chime_button, "aria-pressed", "true" if self.chime else "false")
        if self.chime:
            window.PP.chime()  # so they hear what it sounds like

    @handle("live_timer", "tick")
    def live_timer_tick(self, **event_args):
        self.check_live()

    def check_live(self):
        """Ask the server whether this day or the approvals changed; reload and chime when they did."""
        if window.document.hidden or self._dialogs > 0 or window.PP.dialogOpen():
            return
        self._ticks += 1
        try:
            stamp = anvil.server.call_s("get_day_stamp", self.rid, self.D["date"])
        except Exception:  # offline, or the server is restarting: the next tick tries again
            return
        old = self.D.get("stamp") or {}
        if stamp == old and self._ticks % 5:
            return  # every fifth minute it redraws anyway, so "now" on the timeline keeps moving
        try:
            day = anvil.server.call_s("get_day", self.rid, self.D["date"])
        except Exception:
            return
        if self._dialogs > 0 or window.PP.dialogOpen():
            return
        requests = int(stamp.get("pending") or 0) - int(old.get("pending") or 0)
        bookings = int(stamp.get("rows") or 0) - int(old.get("rows") or 0)
        self._show(day)
        if requests > 0 or bookings > 0:
            msg = "New request waiting for approval" if requests > 0 else "New booking"
            self.live_status.text = msg
            state.toast(msg)
            if self.chime:
                window.PP.chime()


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
