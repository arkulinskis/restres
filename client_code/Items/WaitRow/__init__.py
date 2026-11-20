from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import WaitRowTemplate
from ... import state


class WaitRow(WaitRowTemplate):
    """Someone on the day's waitlist (Reservations). item = Waitlist.view(): name, party, window (Lunch / Dinner /
    Any time), notes, `fits` = the first time a table is free in their window ("Table free at 19:30"), `join` = only
    with tables pushed together, links tel / wa / sms with a message in the guest's language.
    Book raises x-book(entry=) (the booking editor, pre-filled), Remove raises x-remove(entry=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        w = self.item
        self.name_label.text = w["name"]
        joined = ""
        if w.get("created"):
            at = anvil.js.new(window.Date, w["created"])
            joined = " · asked at %02d:%02d" % (at.getHours(), at.getMinutes())
        self.meta_label.text = "%s · %s%s" % (state.plural(w["party"], "guest"), w.get("window_label") or "Any time", joined)
        self.notes_label.visible = bool(w.get("notes"))
        self.notes_label.text = "“%s”" % (w.get("notes") or "")
        if w.get("fits") and not w.get("join"):
            self.fit_badge.text, self.fit_badge.role = "Table free at %s" % w["fits"], ["badge", "badge-good"]
        elif w.get("fits"):
            self.fit_badge.text, self.fit_badge.role = "Tables pushed together at %s" % w["fits"], ["badge", "badge-warn"]
        else:
            self.fit_badge.text, self.fit_badge.role = "Still full", ["badge"]
        self.classes["free"] = bool(w.get("fits"))
        self.call_link.visible = bool(w.get("tel"))
        state.set_attr(self.call_link, "href", w.get("tel") or "#")
        state.set_attr(self.call_link, "aria-label", "Call %s" % w["name"])
        msg = w.get("wa") or w.get("sms") or ""
        self.msg_link.visible = bool(msg)
        state.set_attr(self.msg_link, "href", msg or "#")
        if msg.startswith("sms:"):
            state.set_attr(self.msg_link, "target", None)
        state.set_attr(self.msg_link, "aria-label", "Message %s that a table is free" % w["name"])
        state.set_control_attr(self.book_button, "aria-label", "Book a table for %s" % w["name"])
        state.set_control_attr(self.remove_button, "aria-label", "Remove %s from the waitlist" % w["name"])
        self.book_button.role = ["btn", "btn-sm", "ic-plus"] + (["btn-primary"] if w.get("fits") else [])

    @handle("book_button", "click")
    def book_button_click(self, **event_args):
        self.parent.raise_event("x-book", entry=self.item)

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-remove", entry=self.item)
