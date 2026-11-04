from anvil import *
import anvil.js

from ._anvil_designer import CalDayTemplate
from ... import pp


class CalDay(CalDayTemplate):
    """A day in the opening-hours calendar. item = a calendar cell (+ _color, _today, _past), or {"blank": True}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        if c.get("blank"):
            self.classes["blank"] = True
            return
        closed = not c["hours"]
        self.classes.update({"closed": closed, "today": c["_today"], "past": c["_past"]})
        anvil.js.get_dom_node(self).style.setProperty("--c", c["_color"])
        self.num.text = str(int(c["date"][8:]))
        self.hours_label.text = "Closed" if closed else "\n".join("%s–%s" % (a.replace(":00", ""), b.replace(":00", "")) for a, b in c["hours"])
        self.tooltip = "%s: %s (%s)" % (pp.fmt_date(c["date"]), pp.hours_text(c["hours"]), c.get("label") or "")

    def day_click(self, event):
        if not self.item.get("blank"):
            self.parent.raise_event("x-day", date=self.item["date"])
