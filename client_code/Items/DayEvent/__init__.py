from anvil import *

from ._anvil_designer import DayEventTemplate
from ... import router, state


class DayEvent(DayEventTemplate):
    """An event on the day shown in Reservations. item = {title, start, end, kind, blocks, guests, setup, rid, manager}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        bits = ["%s · %s–%s" % (e["title"], e["start"], e["end"])]
        bits.append(("Private" + (", online booking closed" if e.get("blocks") else "")) if e.get("kind") == "private" else "Public event")
        if e.get("guests"):
            bits.append("%d guests" % e["guests"])
        if e.get("setup"):
            bits.append("its own room set-up applies")
        self.text_label.text = " · ".join(bits)
        self.events_link.visible = bool(e.get("manager"))
        state.set_attr(self.events_link, "href", router.href("events", e["rid"]))
