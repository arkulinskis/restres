from anvil import *
import anvil.server

from ._anvil_designer import RemindersTemplate
from ... import state


class Reminders(RemindersTemplate):
    """The no-show shield's reminder list for one day (Today -> "Remind tomorrow's guests", Reservations -> Remind).
    day = "YYYY-MM-DD", or None for tomorrow / the next open day. Every confirmed booking with its message in the
    guest's language and WhatsApp / SMS / Email / Copy (Items/RemindRow). Opens at once; the list loads right after.
    Closes with True when something was reminded (the page reloads its numbers), else False."""

    def __init__(self, rid, day=None, **properties):
        super().__init__(**properties)
        self.rid, self.day = rid, day
        self.D: dict = {}
        self.changed = False
        self._loaded = False
        self.list_box.visible = self.empty_box.visible = False
        self.rows_panel.add_event_handler("x-sent", self._sent)

    @handle("", "show")
    def form_show(self, **event_args):
        if not self._loaded:
            self._loaded = True
            self._load()

    def _load(self):
        try:
            r = anvil.server.call_s("get_reminders", self.rid, self.day)
        except Exception:
            r = {"ok": False, "error": "The list didn't load. Check the connection and try again."}
        self.loading_label.visible = False
        if not r or not r.get("ok"):
            self.message.visible = True
            self.message.text = (r or {}).get("error") or "Something went wrong."
            return
        self.D = r
        self._draw()

    def _draw(self):
        D = self.D
        items: list = list(D.get("items") or [])
        self.title_label.text = D.get("title") or "Remind your guests"
        self._count()
        self.list_box.visible = bool(items)
        self.empty_box.visible = not items
        self.empty_label.text = "No confirmed bookings for %s yet. New bookings show up here by themselves." % D.get("word", "that day")
        self.pending_label.visible = bool(D.get("pending"))
        self.pending_label.text = "%s for that day still %s for your approval: approve first, then remind." % (
            state.plural(D.get("pending") or 0, "request"), "waits" if D.get("pending") == 1 else "wait")
        self.rows_panel.items = [dict(i, _rid=self.rid) for i in items]

    def _count(self):
        items: list = list(self.rows_panel.items or self.D.get("items") or [])
        done = len([i for i in items if i.get("reminded")])
        coming = len([i for i in items if i.get("coming")])
        self.count_badge.visible = bool(items)
        self.count_badge.text = "%d of %d reminded%s" % (done, len(items), " · %d coming" % coming if coming else "")
        self.count_badge.role = ["badge", "badge-good"] if items and done == len(items) else ["badge"]

    def _sent(self, item, reminded, **event_args):
        self.changed = True
        self._count()

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=self.changed)
