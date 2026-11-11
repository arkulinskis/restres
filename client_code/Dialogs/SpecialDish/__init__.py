import datetime

from anvil import *
import anvil.server

from ._anvil_designer import SpecialDishTemplate
from ... import pp


class SpecialDish(SpecialDishTemplate):
    """A dish of the day or the week: today only, between dates, or ongoing, optionally on chosen weekdays.
    Closes with the Today page's new data, or None."""

    def __init__(self, rid, data, special=None, **properties):
        super().__init__(**properties)
        self.rid, self.special = rid, special
        today = data["today"]
        s: dict = special or {"title": "", "price": "", "description": "", "photo": None, "start": today, "end": today, "days": [], "active": True}
        if s.get("start") and s.get("end") and s["start"] == s["end"]:
            self.when = "today" if s["start"] == today else "dates"
        else:
            self.when = "always" if not s.get("start") and not s.get("end") else "dates"
        self.title_label.text = s["title"] if special else "Add a special"
        self.name_box.text, self.price_box.text, self.desc_box.text = s["title"], s.get("price") or "", s.get("description") or ""
        self.photo_field.rid = rid
        self.photo_field.photo = s.get("photo")
        self.start_picker.date = datetime.date.fromisoformat(s.get("start") or today)
        self.end_picker.date = datetime.date.fromisoformat(s["end"]) if s.get("end") else None
        self.days = list(s.get("days") or [])
        self.days_panel.add_event_handler("x-chip", self._day)
        self.delete_button.visible = special is not None
        self._draw()

    def _draw(self):
        for name, el in (("today", self.w_today), ("dates", self.w_dates), ("always", self.w_always)):
            el.classes["on"] = self.when == name
        self.dates_part.visible = self.when == "dates"
        self.days_part.visible = self.when != "today"
        self.days_panel.items = [{"label": d, "value": i, "on": i in self.days} for i, d in enumerate(pp.DAYS3)]

    def when_click(self, event):
        self.when = event.currentTarget.getAttribute("data-w")
        self._draw()

    def _day(self, value, **event_args):
        self.days = [d for d in self.days if d != value] if value in self.days else self.days + [value]
        self._draw()

    def _done(self, r):
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        photo = self.photo_field.photo
        self._done(anvil.server.call("save_dish_special", self.rid, {
            "id": self.special["id"] if self.special else None, "title": self.name_box.text or "", "price": self.price_box.text or "",
            "description": self.desc_box.text or "", "photo": photo["key"] if photo else None, "when": self.when,
            "start": self.start_picker.date.isoformat() if self.start_picker.date else None,
            "end": self.end_picker.date.isoformat() if self.end_picker.date else None,
            "days": [] if self.when == "today" else sorted(self.days),
            "active": (self.special or {}).get("active", True) is not False}))

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("It disappears from your website.", title="Delete this special?", buttons=[("Keep it", False), ("Delete", True)]):
            self._done(anvil.server.call("delete_dish_special", self.rid, (self.special or {}).get("id")))
