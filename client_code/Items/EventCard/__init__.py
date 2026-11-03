from anvil import *

from ._anvil_designer import EventCardTemplate
from ... import pp, state


class EventCard(EventCardTemplate):
    """An event in the Events list. item = an event view + _past. Raises x-edit / x-delete / x-setup (event=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        self.day_label.text = str(int(e["date"][8:]))
        self.mon_label.text = pp.MONTHS[int(e["date"][5:7]) - 1][:3]
        kind = ("Private" + (", online booking closed" if e.get("blocks") else "")) if e["kind"] == "private" else ("Public" + (", on your website" if e.get("on_site") else ""))
        bits = ["%s · %s–%s" % (pp.DAYS[pp.weekday(e["date"])], e["start"], e["end"]), kind]
        if e.get("guests"):
            bits.append("%d expected" % e["guests"])
        if e.get("has_setup"):
            bits.append("room set up")
        self.meta_label.text = " · ".join(bits)
        self.desc_label.visible = bool(e.get("description"))
        self.desc_label.text = e.get("description") or ""
        clash = not e["_past"] and e["kind"] == "private" and e.get("bookings")
        self.warn_label.visible = bool(clash)
        if clash:
            self.warn_label.text = "%s (%s) already overlap this event. Move them or let the guests know." % (
                state.plural(e["bookings"], "booking"), state.plural(e.get("covers") or 0, "guest"))
        src = pp.thumb(e.get("photo"))
        self.img.visible = bool(src)
        if src:
            state.set_attr(self.img, "src", src)
        self.setup_button.visible = not e["_past"]
        self.setup_button.text = "Room" if e.get("has_setup") else "Set up the room"

    @handle("setup_button", "click")
    def setup_button_click(self, **event_args):
        self.parent.raise_event("x-setup", event=self.item)

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.parent.raise_event("x-edit", event=self.item)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete", event=self.item)
