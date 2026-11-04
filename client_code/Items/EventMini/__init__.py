from anvil import *

from ._anvil_designer import EventMiniTemplate
from ... import pp


class EventMini(EventMiniTemplate):
    """An upcoming event (Today -> Coming up). item = an event view."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        self.day_label.text = str(int(e["date"][8:]))
        self.mon_label.text = pp.MONTHS[int(e["date"][5:7]) - 1][:3]
        self.title_label.text = e["title"]
        kind = ("Private" + (", online booking closed" if e.get("blocks") else "")) if e.get("kind") == "private" else ("Public" + (", on your website" if e.get("on_site") else ""))
        self.meta_label.text = "%s–%s · %s%s" % (e["start"], e["end"], kind, " · room set up" if e.get("has_setup") else "")
