from anvil import *
from anvil.js import window

from ._anvil_designer import DaySheetTemplate
from ... import pp, state

LIVE = ("pending", "confirmed", "seated", "done")


class DaySheet(DaySheetTemplate):
    """A printable list of the day's bookings for the host stand (Reservations -> Day sheet). day = Portal.get_day()."""

    def __init__(self, day, **properties):
        super().__init__(**properties)
        rows = sorted([r for r in day["reservations"] if r["status"] in LIVE], key=lambda r: r["start_min"])
        self.place_label.text = day["nav"]["restaurant"]["name"]
        self.title_label.text = pp.fmt_date(day["date"])
        s = day["summary"]
        self.summary.text = "%s · %s · %s" % (state.plural(s["bookings"], "booking"), state.plural(s["covers"], "guest"),
                                              (pp.hours_text(day["hours"]) if day["hours"] else "Closed"))
        self.rows_panel.items = rows
        self.empty_label.visible = not rows

    @handle("print_button", "click")
    def print_button_click(self, **event_args):
        pp.html_class("pp-printing", True)
        window.print()
        pp.html_class("pp-printing", False)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
