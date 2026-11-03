from anvil import *
import anvil.js

from ._anvil_designer import PeriodCardTemplate
from ... import pp


def _d(iso):
    return pp.fmt_date(iso, "short") + " " + iso[:4]


class PeriodCard(PeriodCardTemplate):
    """An opening-hours period. item = a period view + _color. Raises x-edit / x-delete (period=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        anvil.js.get_dom_node(self).style.setProperty("--c", p["_color"])
        if not p.get("start") and not p.get("end"):
            self.range_label.text = "All year, every year"
        elif p.get("start") and p.get("end"):
            self.range_label.text = "%s – %s" % (_d(p["start"]), _d(p["end"]))
        else:
            self.range_label.text = ("From " + _d(p["start"])) if p.get("start") else ("Until " + _d(p["end"]))
        self.week_label.text = "\n".join("%s	%s" % (d, pp.hours_text(p["week"].get(str(i)) or [])) for i, d in enumerate(pp.DAYS3))

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.parent.raise_event("x-edit", period=self.item)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete", period=self.item)
