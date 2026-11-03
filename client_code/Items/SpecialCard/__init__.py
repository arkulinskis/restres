from anvil import *

from ._anvil_designer import SpecialCardTemplate
from ... import pp, state


def when_text(s, today):
    if s.get("start") and s.get("end") and s["start"] == s["end"]:
        return "Today only" if s["start"] == today else pp.fmt_date(s["start"], "short") + " only"
    bits = []
    if s.get("days"):
        bits.append(", ".join(pp.DAYS3[d] for d in s["days"]))
    if s.get("start") and s["start"] > today:
        bits.append("from " + pp.fmt_date(s["start"], "short"))
    if s.get("end"):
        bits.append("until " + pp.fmt_date(s["end"], "short"))
    return " · ".join(bits) or "Every day"


class SpecialCard(SpecialCardTemplate):
    """A dish special (Today). item = a special view + _today, _manage. Raises x-edit(special=), x-toggle(special=, active=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        self.classes["off"] = not s["active"]
        src = pp.thumb(s.get("photo"))
        self.img.visible = bool(src)
        if src:
            state.set_attr(self.img, "src", src)
        self.title_label.text = s["title"] + ((" · " + s["price"]) if s.get("price") else "")
        self.when_label.text = when_text(s, s["_today"]) + (" · on today" if s.get("today") and s["active"] else "")
        self.active_box.checked = s["active"]
        self.active_box.visible = self.edit_button.visible = s["_manage"]

    @handle("active_box", "change")
    def active_box_change(self, **event_args):
        self.parent.raise_event("x-toggle", special=self.item, active=self.active_box.checked)

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.parent.raise_event("x-edit", special=self.item)
