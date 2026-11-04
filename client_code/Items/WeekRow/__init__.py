from anvil import *

from ._anvil_designer import WeekRowTemplate
from ... import pp, state


class WeekRow(WeekRowTemplate):
    """A day in Today -> The week ahead. item = {date, hours, label, events, bookings, covers} + _today, _max."""

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
