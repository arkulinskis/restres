from anvil import *
import anvil.js

from ._anvil_designer import PickDayTemplate
from ... import pp, state


class PickDay(PickDayTemplate):
    """A day in the guest's booking calendar. item = {date, day, open, on, today} | {"blank": True} | {"head": "Mo"}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        node = anvil.js.get_dom_node(self)
        if i.get("head"):
            self.classes["wd"] = True
            self.num.text = i["head"]
            setattr(node, "disabled", True)
            node.setAttribute("aria-hidden", "true")  # each day button already says its weekday
            return
        if i.get("blank"):
            self.classes["out"] = True
            setattr(node, "disabled", True)
            node.setAttribute("aria-hidden", "true")
            return
        self.num.text = str(i["day"])
        self.classes.update({"on": bool(i["on"]), "today": bool(i["today"]), "shut": not i["open"]})
        setattr(node, "disabled", not i["open"])
        node.setAttribute("aria-label", pp.fmt_date(i["date"]))
        node.setAttribute("aria-pressed", "true" if i["on"] else "false")
        node.setAttribute("data-key", i["date"])
        if i["today"]:
            node.setAttribute("aria-current", "date")

    def day_click(self, event):
        i = self.item
        if i.get("open"):
            panel = self.parent
            panel.raise_event("x-day", date=i["date"])
            state.refocus(panel, i["date"])  # the calendar redraws: keep the keyboard on the chosen day
