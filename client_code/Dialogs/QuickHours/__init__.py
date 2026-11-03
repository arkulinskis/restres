from anvil import *
import anvil.server

from ._anvil_designer import QuickHoursTemplate


class QuickHours(QuickHoursTemplate):
    """Today's hours only (a special day for today). Closes with the Today page's new data, or None."""

    def __init__(self, rid, data, **properties):
        super().__init__(**properties)
        self.rid = rid
        hours = data["status"]["hours"] or [["12:00", "22:00"]]
        self.ivs_panel.items = [{"open": a, "close": b} for a, b in hours]
        self.ivs_panel.add_event_handler("x-remove", self._remove)
        self.label_box.text = data["status"]["label"] if data["status"].get("kind") == "special" else ""

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
        if any(b != "00:00" and b <= a for a, b in ivs):
            self.message.visible, self.message.text = True, "Each closing time must be after its opening time (use 00:00 for midnight)."
            return
        r = anvil.server.call("quick_hours", self.rid, "hours", ivs, self.label_box.text or "")
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)
