import datetime

from anvil import *
import anvil.server

from ._anvil_designer import SpecialEditorTemplate
from ... import pp


class SpecialEditor(SpecialEditorTemplate):
    """A special day (or a range of them): closed, or its own hours. Closes with the Hours page's new data, or None."""

    def __init__(self, rid, data, special=None, date=None, **properties):
        super().__init__(**properties)
        self.rid, self.D, self.special = rid, data, special
        is_new = special is None
        s: dict = special or {"date": date or data["today"], "label": "", "closed": True, "hours": [["12:00", "22:00"]]}
        self.eyebrow.text = "Special day" if is_new else "Edit special day"
        self.title_label.text = pp.fmt_date(s["date"])
        self.date_picker.date = datetime.date.fromisoformat(s["date"])
        self.to_field.visible = is_new
        self.label_box.text = s.get("label") or ""
        self.closed = bool(s["closed"])
        self.no_online_box.checked = bool(s.get("no_online"))
        self.ivs_panel.items = [{"open": a, "close": b} for a, b in (s.get("hours") or [["12:00", "22:00"]])]
        self.ivs_panel.add_event_handler("x-remove", self._remove)
        self._mode()

    def _mode(self):
        self.mode_closed.classes["on"] = self.closed
        self.mode_open.classes["on"] = not self.closed
        self.ivs_box.visible = not self.closed
        self.no_online_box.visible = not self.closed

    def mode_click(self, event):
        self.closed = event.currentTarget.getAttribute("data-mode") == "closed"
        self._mode()

    def _remove(self, item, **event_args):
        if len(list(self.ivs_panel.items)) > 1:
            self.ivs_panel.items = [iv for iv in self.ivs_panel.items if iv is not item]

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self.ivs_panel.items = list(self.ivs_panel.items) + [{"open": "18:00", "close": "22:00"}]

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        ivs = [[iv["open"][:5], iv["close"][:5]] for iv in self.ivs_panel.items]
        if not self.closed and any(b != "00:00" and b <= a for a, b in ivs):
            self.message.visible, self.message.text = True, "Each closing time must be after its opening time (use 00:00 for midnight)."
            return
        if not self.date_picker.date:
            self.message.visible, self.message.text = True, "Pick a date."
            return
        data = {"id": self.special["id"] if self.special else None, "date": self.date_picker.date.isoformat(),
                "to": self.to_picker.date.isoformat() if self.special is None and self.to_picker.date else None,
                "label": self.label_box.text or "", "closed": self.closed, "hours": ivs,
                "no_online": bool(self.no_online_box.checked) and not self.closed}
        r = anvil.server.call("save_special", self.rid, data, self.D["month"])
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)
