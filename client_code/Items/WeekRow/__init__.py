from anvil import *

from ._anvil_designer import WeekRowTemplate
from ... import pp, state


class WeekRow(WeekRowTemplate):
    """A day in Today -> The week ahead. item = {date, hours, label, events, bookings, covers, seats, quiet} + _today,
    _max, _manage. A quiet day (open, under 40% of the seats booked) gets the Quiet chip and, for managers, "Fill it",
    which raises x-fill(date=) on the RepeatingPanel (Dialogs/FillNight)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        w = self.item
        self.classes["today"] = w["_today"]
        self.day_label.text = "Today" if w["_today"] else pp.fmt_date(w["date"], "short")
        bits = [pp.hours_text(w["hours"])]
        if w.get("label"):
            bits.append(w["label"])
        if w.get("events"):
            bits.append("★ " + ", ".join(w["events"]))
        self.hours_label.text = " · ".join(bits)
        self.bar.style["width"] = "%d%%" % round(100.0 * w["covers"] / max(1, w["_max"]))
        self.count_label.text = "%d · %s" % (w["bookings"], state.plural(w["covers"], "guest"))
        quiet = bool(w.get("quiet"))
        self.classes["quiet"] = quiet
        self.quiet_badge.visible = quiet
        if quiet and w.get("seats"):
            self.quiet_badge.tooltip = "%d of %d seats booked" % (w["covers"], w["seats"])
        self.fill_button.visible = quiet and bool(w.get("_manage"))
        state.set_control_attr(self.fill_button, "aria-label", "Fill %s: a story to share" % self.day_label.text)

    @handle("fill_button", "click")
    def fill_button_click(self, **event_args):
        self.parent.raise_event("x-fill", date=self.item["date"])
