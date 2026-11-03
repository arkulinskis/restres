from anvil import *

from ._anvil_designer import SpecialRowTemplate
from ... import pp


class SpecialRow(SpecialRowTemplate):
    """A special day (holiday, closure, different hours). Raises x-edit / x-delete (special=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        self.date_label.text = pp.fmt_date(s["date"], "short") + " " + s["date"][:4]
        self.label_label.text = s.get("label") or "Special day"
        self.hours_label.text = "Closed" if s["closed"] else pp.hours_text(s.get("hours") or [])

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.parent.raise_event("x-edit", special=self.item)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete", special=self.item)
